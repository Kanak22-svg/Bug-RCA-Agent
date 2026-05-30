"""Investigation Service.
Business logic for creating and managing investigations.
"""
import logging
from datetime import datetime, timezone
from dateutil import parser as dateparser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.investigation import (
    Investigation, InvestigationStatus, BugSnapshot, ContextArtifact,
    CodeCandidate, CommitCandidate, InvestigationReport, ProgressStep, AuditLog
)
from app.providers.mock_provider import MockIssueProvider, MockDocsProvider, MockCodeProvider
from app.engine.orchestrator import InvestigationOrchestrator, PIPELINE_STEPS

logger = logging.getLogger(__name__)


def get_providers():
    """Get provider instances based on configuration."""
    mode = settings.PROVIDER_MODE
    if mode == "mock":
        return MockIssueProvider(), MockDocsProvider(), MockCodeProvider()
    else:
        # Phase 2: MCP providers
        raise NotImplementedError(f"Provider mode '{mode}' not yet implemented. Use 'mock'.")


def _parse_dt(val):
    """Parse a date string or return None. Returns naive datetime for SQLite."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None)
    try:
        dt = dateparser.parse(str(val))
        return dt.replace(tzinfo=None) if dt else None
    except (ValueError, TypeError):
        return None


class InvestigationService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_investigation(self, issue_key: str, repo_override: str = None,
                                    additional_notes: str = None, scope: dict = None,
                                    triggered_by: str = "ui") -> Investigation:
        """Create a new investigation and run it."""
        # Create investigation record
        investigation = Investigation(
            issue_key=issue_key,
            status=InvestigationStatus.CREATED.value,
            triggered_by=triggered_by,
            repo_override=repo_override,
            additional_notes=additional_notes,
            scope_json=scope or {
                "search_jira": True,
                "search_confluence": True,
                "search_github": True,
                "deep_history": False,
            },
        )
        self.db.add(investigation)
        await self.db.flush()  # Ensure investigation.id is populated

        # Create progress steps
        for step in PIPELINE_STEPS:
            ps = ProgressStep(
                investigation_id=investigation.id,
                step_number=step["number"],
                step_name=step["name"],
                status="pending",
            )
            self.db.add(ps)

        # Audit log
        self.db.add(AuditLog(
            investigation_id=investigation.id,
            action="investigation_created",
            actor=triggered_by,
            details_json={"issue_key": issue_key},
        ))

        await self.db.commit()
        await self.db.refresh(investigation)

        return investigation

    async def run_investigation(self, investigation_id: str) -> Investigation:
        """Run the investigation pipeline."""
        investigation = await self._get_investigation(investigation_id)
        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found")

        try:
            issue_provider, docs_provider, code_provider = get_providers()
            orchestrator = InvestigationOrchestrator(issue_provider, docs_provider, code_provider)

            # Update status
            investigation.status = InvestigationStatus.FETCHING_CONTEXT.value
            await self.db.commit()

            # Define callbacks for progress tracking
            async def on_step_start(step_num: int):
                stmt = select(ProgressStep).where(
                    ProgressStep.investigation_id == investigation_id,
                    ProgressStep.step_number == step_num,
                )
                result = await self.db.execute(stmt)
                step = result.scalar_one_or_none()
                if step:
                    step.status = "running"
                    step.started_at = datetime.utcnow()
                    await self.db.commit()

                # Update investigation status based on step
                if step_num <= 4:
                    investigation.status = InvestigationStatus.FETCHING_CONTEXT.value
                elif step_num <= 7:
                    investigation.status = InvestigationStatus.ANALYZING.value
                else:
                    investigation.status = InvestigationStatus.GENERATING_REPORT.value
                await self.db.commit()

            async def on_step_complete(step_num: int, summary: str):
                stmt = select(ProgressStep).where(
                    ProgressStep.investigation_id == investigation_id,
                    ProgressStep.step_number == step_num,
                )
                result = await self.db.execute(stmt)
                step = result.scalar_one_or_none()
                if step:
                    step.status = "completed"
                    step.completed_at = datetime.utcnow()
                    if step.started_at:
                        delta = step.completed_at - step.started_at
                        step.duration_seconds = delta.total_seconds()
                    step.result_summary = summary
                    await self.db.commit()

            # Run the pipeline
            options = {
                "scope": investigation.scope_json or {},
                "repo_override": investigation.repo_override or "web-app",
                "additional_notes": investigation.additional_notes,
            }

            result = await orchestrator.run(
                investigation.issue_key,
                options=options,
                on_step_start=on_step_start,
                on_step_complete=on_step_complete,
            )

            # Save bug snapshot
            bug_data = result.get("bug_snapshot", {})
            snapshot = BugSnapshot(
                investigation_id=investigation_id,
                **bug_data,
            )
            self.db.add(snapshot)

            # Save context artifacts (related issues)
            for ri in result.get("related_issues", []):
                artifact = ContextArtifact(
                    investigation_id=investigation_id,
                    source_type="jira",
                    source_id=ri.get("key"),
                    title=ri.get("title"),
                    url=f"https://jira.example.com/browse/{ri.get('key', '')}",
                    relevance_score=0.5,
                    content_summary=ri.get("description", "")[:300],
                    relevance_tag=ri.get("relation_type", "RELATED"),
                    metadata_json={
                        "status": ri.get("status"),
                        "priority": ri.get("priority"),
                        "relation_type": ri.get("relation_type"),
                        "relation_reason": ri.get("relation_reason"),
                    },
                )
                self.db.add(artifact)

            # Save context artifacts (confluence docs)
            for doc in result.get("confluence_docs", []):
                artifact = ContextArtifact(
                    investigation_id=investigation_id,
                    source_type="confluence",
                    source_id=doc.get("id"),
                    title=doc.get("title"),
                    url=doc.get("url"),
                    relevance_score=0.7,
                    content_summary=doc.get("content_summary"),
                    key_excerpt=doc.get("key_excerpt"),
                    relevance_tag=doc.get("relevance_tag", "RELATED"),
                    metadata_json={
                        "space": doc.get("space"),
                        "last_updated": doc.get("last_updated"),
                        "author": doc.get("author"),
                    },
                )
                self.db.add(artifact)

            # Save code candidates
            for cc in result.get("code_candidates", []):
                candidate = CodeCandidate(
                    investigation_id=investigation_id,
                    rank=cc.get("rank"),
                    repo=cc.get("repo", ""),
                    file_path=cc.get("file_path", ""),
                    symbol=cc.get("symbol"),
                    confidence=cc.get("confidence", 0),
                    rationale=cc.get("rationale"),
                    code_snippet=cc.get("code_snippet"),
                    suspect_line=cc.get("suspect_line"),
                )
                self.db.add(candidate)

            # Save suspicious commits
            for sc in result.get("suspicious_commits", []):
                commit = CommitCandidate(
                    investigation_id=investigation_id,
                    repo=sc.get("repo", ""),
                    commit_sha=sc.get("commit_sha", ""),
                    pr_number=sc.get("pr_number"),
                    pr_title=sc.get("pr_title"),
                    author=sc.get("author"),
                    confidence=sc.get("confidence", 0),
                    suspicion_level=sc.get("suspicion_level"),
                    rationale=sc.get("rationale"),
                    commit_message=sc.get("commit_message"),
                    committed_at=_parse_dt(sc.get("committed_at")),
                    files_changed=sc.get("files_changed"),
                )
                self.db.add(commit)

            # Save report
            report_data = result.get("report", {})
            report = InvestigationReport(
                investigation_id=investigation_id,
                executive_summary=report_data.get("executive_summary"),
                classification=report_data.get("classification"),
                recommendation=report_data.get("recommendation"),
                recommendation_detail=report_data.get("recommendation_detail"),
                confidence_score=report_data.get("confidence_score"),
                key_findings_json=report_data.get("key_findings_json"),
                suggested_action=report_data.get("suggested_action"),
                suggested_code_direction=report_data.get("suggested_code_direction"),
                suggested_owner=report_data.get("suggested_owner"),
                evidence_timeline_json=report_data.get("evidence_timeline_json"),
            )
            self.db.add(report)

            # Update investigation status
            investigation.status = InvestigationStatus.COMPLETED.value
            investigation.updated_at = datetime.utcnow()

            self.db.add(AuditLog(
                investigation_id=investigation_id,
                action="investigation_completed",
                actor="system",
                details_json={"classification": report_data.get("classification")},
            ))

            await self.db.commit()

        except Exception as e:
            logger.error(f"Investigation {investigation_id} failed: {e}")
            investigation.status = InvestigationStatus.FAILED.value
            investigation.error_message = str(e)
            investigation.updated_at = datetime.utcnow()

            self.db.add(AuditLog(
                investigation_id=investigation_id,
                action="investigation_failed",
                actor="system",
                details_json={"error": str(e)},
            ))

            await self.db.commit()
            raise

        return await self._get_investigation_full(investigation_id)

    async def get_investigation(self, investigation_id: str) -> Investigation:
        """Get a full investigation with all related data."""
        return await self._get_investigation_full(investigation_id)

    async def list_investigations(self, page: int = 1, page_size: int = 20,
                                   classification_filter: str = None,
                                   search: str = None) -> dict:
        """List investigations with pagination and filtering."""
        query = select(Investigation).options(
            selectinload(Investigation.bug_snapshot),
            selectinload(Investigation.report),
        ).order_by(desc(Investigation.created_at))

        # Apply filters
        if classification_filter:
            query = query.join(Investigation.report).where(
                InvestigationReport.classification == classification_filter
            )

        if search:
            query = query.where(
                Investigation.issue_key.ilike(f"%{search}%")
            )

        # Count total
        count_query = select(func.count()).select_from(Investigation)
        if classification_filter:
            count_query = count_query.join(Investigation.report).where(
                InvestigationReport.classification == classification_filter
            )
        if search:
            count_query = count_query.where(
                Investigation.issue_key.ilike(f"%{search}%")
            )

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        investigations = result.scalars().all()

        items = []
        for inv in investigations:
            item = {
                "id": inv.id,
                "issue_key": inv.issue_key,
                "status": inv.status,
                "title": inv.bug_snapshot.title if inv.bug_snapshot else None,
                "classification": inv.report.classification if inv.report else None,
                "confidence_score": inv.report.confidence_score if inv.report else None,
                "priority": inv.bug_snapshot.priority if inv.bug_snapshot else None,
                "assignee": inv.bug_snapshot.assignee if inv.bug_snapshot else None,
                "is_pinned": bool(inv.is_pinned),
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
                "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
            }
            items.append(item)

        total_pages = (total + page_size - 1) // page_size

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    async def get_stats(self) -> dict:
        """Get dashboard statistics."""
        total = await self.db.execute(select(func.count()).select_from(Investigation))
        total_count = total.scalar() or 0

        # Count by classification
        regression = await self.db.execute(
            select(func.count()).select_from(InvestigationReport).where(
                InvestigationReport.classification == "LIKELY_REGRESSION"
            )
        )
        intentional = await self.db.execute(
            select(func.count()).select_from(InvestigationReport).where(
                InvestigationReport.classification == "LIKELY_INTENTIONAL"
            )
        )
        unclear = await self.db.execute(
            select(func.count()).select_from(InvestigationReport).where(
                InvestigationReport.classification == "UNCLEAR"
            )
        )
        pending = await self.db.execute(
            select(func.count()).select_from(Investigation).where(
                Investigation.status.in_([
                    InvestigationStatus.CREATED.value,
                    InvestigationStatus.FETCHING_CONTEXT.value,
                    InvestigationStatus.ANALYZING.value,
                    InvestigationStatus.GENERATING_REPORT.value,
                ])
            )
        )
        failed = await self.db.execute(
            select(func.count()).select_from(Investigation).where(
                Investigation.status == InvestigationStatus.FAILED.value
            )
        )

        return {
            "total": total_count,
            "regressions": regression.scalar() or 0,
            "intentional": intentional.scalar() or 0,
            "unclear": unclear.scalar() or 0,
            "pending": pending.scalar() or 0,
            "failed": failed.scalar() or 0,
        }

    async def toggle_pin(self, investigation_id: str) -> bool:
        """Toggle pinned status. Returns new pinned state."""
        inv = await self._get_investigation(investigation_id)
        if not inv:
            raise ValueError(f"Investigation {investigation_id} not found")
        inv.is_pinned = 0 if inv.is_pinned else 1
        await self.db.commit()
        return bool(inv.is_pinned)

    async def delete_investigation(self, investigation_id: str):
        """Soft delete an investigation."""
        inv = await self._get_investigation(investigation_id)
        if inv:
            await self.db.delete(inv)
            await self.db.commit()

    async def _get_investigation(self, investigation_id: str) -> Investigation:
        result = await self.db.execute(
            select(Investigation).where(Investigation.id == investigation_id)
        )
        return result.scalar_one_or_none()

    async def _get_investigation_full(self, investigation_id: str) -> Investigation:
        result = await self.db.execute(
            select(Investigation)
            .options(
                selectinload(Investigation.bug_snapshot),
                selectinload(Investigation.context_artifacts),
                selectinload(Investigation.code_candidates),
                selectinload(Investigation.commit_candidates),
                selectinload(Investigation.report),
                selectinload(Investigation.progress_steps),
                selectinload(Investigation.audit_logs),
            )
            .where(Investigation.id == investigation_id)
        )
        return result.scalar_one_or_none()
