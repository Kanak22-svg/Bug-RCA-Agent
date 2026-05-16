"""Job orchestrator. Owns the state machine and persists results."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select

from ..db import SessionLocal
from ..engine.context_retriever import gather_context
from ..engine.intake import normalize
from ..engine.intent_analyzer import analyze_intent
from ..engine.localization import localize
from ..engine.regression_finder import find_regressions
from ..engine.report_generator import build_artifacts, build_report, recommend
from ..models import (
    AuditLog,
    BugSnapshot,
    CodeCandidate,
    CommitCandidate,
    ContextArtifact,
    FinalReport,
    Investigation,
)
from ..providers.base import CodeProvider, DocsProvider, IssueProvider

log = logging.getLogger(__name__)


STATES = [
    "CREATED",
    "FETCHING_CONTEXT",
    "PARSING_REPRO",
    "LOCALIZING_CODE",
    "ANALYZING_INTENT",
    "FINDING_REGRESSION",
    "GENERATING_REPORT",
    "COMPLETED",
    "FAILED",
]


async def _set_status(inv_id: str, status: str, *, error: str | None = None) -> None:
    async with SessionLocal() as s:
        inv = await s.get(Investigation, inv_id)
        if not inv:
            return
        inv.status = status
        inv.updated_at = datetime.utcnow()
        if error:
            inv.error = error
        s.add(AuditLog(investigation_id=inv_id, action=f"status:{status}", details_json={"error": error} if error else {}))
        await s.commit()


async def run_investigation(
    *,
    investigation_id: str,
    issue_key: str,
    repos: list[str],
    issue_provider: IssueProvider,
    docs_provider: DocsProvider,
    code_provider: CodeProvider,
) -> None:
    """Run the full pipeline for one investigation. Persists everything."""
    try:
        await _set_status(investigation_id, "FETCHING_CONTEXT")
        issue = await issue_provider.get_issue(issue_key)

        await _set_status(investigation_id, "PARSING_REPRO")
        bug = normalize(issue)

        # Persist bug snapshot.
        async with SessionLocal() as s:
            s.add(BugSnapshot(
                investigation_id=investigation_id,
                title=bug.title,
                description=issue.description,
                expected_behavior=bug.expected_behavior,
                actual_behavior=bug.actual_behavior,
                repro_status=(bug.manual_repro or {}).get("status", "uncertain"),
                repro_notes=(bug.manual_repro or {}).get("notes", ""),
                environment_json=(bug.manual_repro or {}).get("environment") or {},
                raw_json=issue.model_dump(),
            ))
            await s.commit()

        pack = await gather_context(
            bug=bug,
            issue=issue,
            repos=repos,
            issue_provider=issue_provider,
            docs_provider=docs_provider,
            code_provider=code_provider,
        )

        # Persist context artifacts.
        artifacts = build_artifacts(pack)
        async with SessionLocal() as s:
            for a in artifacts:
                s.add(ContextArtifact(
                    investigation_id=investigation_id,
                    source_type=a.source_type,
                    source_id=a.source_id,
                    title=a.title,
                    url=a.url,
                    relevance_score=a.relevance_score,
                    metadata_json=a.metadata,
                ))
            await s.commit()

        await _set_status(investigation_id, "LOCALIZING_CODE")
        code_candidates = localize(bug, pack)
        async with SessionLocal() as s:
            for c in code_candidates:
                s.add(CodeCandidate(
                    investigation_id=investigation_id,
                    repo=c.repo,
                    file_path=c.file_path,
                    symbol=c.symbol,
                    confidence=c.confidence,
                    rationale=c.rationale,
                ))
            await s.commit()

        await _set_status(investigation_id, "ANALYZING_INTENT")
        intent_payload = await analyze_intent(bug, pack)
        classification = intent_payload.get("classification", "UNCLEAR")

        await _set_status(investigation_id, "FINDING_REGRESSION")
        commit_candidates: list[Any] = []
        if classification != "LIKELY_INTENTIONAL":
            commit_candidates = await find_regressions(
                pack=pack, candidates=code_candidates, code_provider=code_provider
            )
        async with SessionLocal() as s:
            for cc in commit_candidates:
                s.add(CommitCandidate(
                    investigation_id=investigation_id,
                    repo=cc.repo,
                    commit_sha=cc.commit_sha,
                    pr_number=cc.pr_number,
                    confidence=cc.confidence,
                    classification=cc.classification,
                    rationale=cc.rationale,
                ))
            await s.commit()

        await _set_status(investigation_id, "GENERATING_REPORT")
        recommendation = recommend(
            bug=bug,
            classification=classification,
            code_candidates=code_candidates,
            commit_candidates=commit_candidates,
        )
        report = build_report(
            bug=bug,
            pack=pack,
            classification=classification,
            intent_payload=intent_payload,
            code_candidates=code_candidates,
            commit_candidates=commit_candidates,
            recommendation=recommendation,
        )
        async with SessionLocal() as s:
            s.add(FinalReport(
                investigation_id=investigation_id,
                summary_markdown=report["summary_markdown"],
                classification=report["classification"],
                recommendation=report["recommendation"],
                confidence=report["confidence"],
                payload_json=report["payload"],
            ))
            await s.commit()

        await _set_status(investigation_id, "COMPLETED")
    except Exception as e:
        log.exception("Investigation %s failed", investigation_id)
        await _set_status(investigation_id, "FAILED", error=str(e))
