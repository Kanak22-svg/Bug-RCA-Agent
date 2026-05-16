"""HTTP routes for investigations."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..db import SessionLocal, get_session
from ..models import Investigation
from ..orchestrator.orchestrator import run_investigation
from ..providers.factory import build_providers
from ..schemas import (
    AnalyzeRequest,
    CodeCandidateOut,
    CommitCandidateOut,
    ContextArtifactOut,
    FinalReportOut,
    InvestigationDetail,
    InvestigationSummary,
)

router = APIRouter(prefix="/api", tags=["investigations"])


async def _run_job(investigation_id: str, issue_key: str, repos: list[str]) -> None:
    issue_p, docs_p, code_p = build_providers()
    await run_investigation(
        investigation_id=investigation_id,
        issue_key=issue_key,
        repos=repos,
        issue_provider=issue_p,
        docs_provider=docs_p,
        code_provider=code_p,
    )


@router.post("/investigations", response_model=InvestigationSummary)
async def create_investigation(req: AnalyzeRequest, background: BackgroundTasks) -> InvestigationSummary:
    if not req.issue_key.strip():
        raise HTTPException(400, "issue_key is required")
    async with SessionLocal() as s:
        inv = Investigation(issue_key=req.issue_key.strip(), triggered_by=req.triggered_by, status="CREATED")
        s.add(inv)
        await s.commit()
        await s.refresh(inv)
        inv_id = inv.id

    background.add_task(_run_job, inv_id, req.issue_key.strip(), req.repos)
    return InvestigationSummary(
        id=inv_id, issue_key=req.issue_key.strip(),
        status="CREATED", triggered_by=req.triggered_by,
        created_at=inv.created_at, updated_at=inv.updated_at,
    )


@router.get("/investigations", response_model=list[InvestigationSummary])
async def list_investigations(session: AsyncSession = Depends(get_session)) -> list[InvestigationSummary]:
    rows = (await session.execute(select(Investigation).order_by(Investigation.created_at.desc()).limit(50))).scalars().all()
    return [
        InvestigationSummary(
            id=r.id, issue_key=r.issue_key, status=r.status, triggered_by=r.triggered_by,
            created_at=r.created_at, updated_at=r.updated_at, error=r.error,
        )
        for r in rows
    ]


@router.get("/investigations/{inv_id}", response_model=InvestigationDetail)
async def get_investigation(inv_id: str, session: AsyncSession = Depends(get_session)) -> InvestigationDetail:
    stmt = (
        select(Investigation)
        .where(Investigation.id == inv_id)
        .options(
            selectinload(Investigation.snapshot),
            selectinload(Investigation.artifacts),
            selectinload(Investigation.code_candidates),
            selectinload(Investigation.commit_candidates),
            selectinload(Investigation.report),
        )
    )
    inv = (await session.execute(stmt)).scalar_one_or_none()
    if not inv:
        raise HTTPException(404, "Investigation not found")
    return InvestigationDetail(
        id=inv.id,
        issue_key=inv.issue_key,
        status=inv.status,
        triggered_by=inv.triggered_by,
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        error=inv.error,
        bug=(
            {
                "title": inv.snapshot.title,
                "description": inv.snapshot.description,
                "expected_behavior": inv.snapshot.expected_behavior,
                "actual_behavior": inv.snapshot.actual_behavior,
                "repro_status": inv.snapshot.repro_status,
                "repro_notes": inv.snapshot.repro_notes,
                "environment": inv.snapshot.environment_json,
            }
            if inv.snapshot else None
        ),
        artifacts=[
            ContextArtifactOut(
                source_type=a.source_type, source_id=a.source_id, title=a.title,
                url=a.url, relevance_score=a.relevance_score, metadata=a.metadata_json,
            )
            for a in inv.artifacts
        ],
        code_candidates=[
            CodeCandidateOut(
                repo=c.repo, file_path=c.file_path, symbol=c.symbol,
                confidence=c.confidence, rationale=c.rationale,
            )
            for c in inv.code_candidates
        ],
        commit_candidates=[
            CommitCandidateOut(
                repo=c.repo, commit_sha=c.commit_sha, pr_number=c.pr_number,
                confidence=c.confidence, classification=c.classification, rationale=c.rationale,
            )
            for c in inv.commit_candidates
        ],
        report=(
            FinalReportOut(
                summary_markdown=inv.report.summary_markdown,
                classification=inv.report.classification,  # type: ignore[arg-type]
                recommendation=inv.report.recommendation,  # type: ignore[arg-type]
                confidence=inv.report.confidence,
                payload=inv.report.payload_json,
            )
            if inv.report else None
        ),
    )
