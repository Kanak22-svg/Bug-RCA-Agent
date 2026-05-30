from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.models.schemas import (
    CreateInvestigationRequest,
    InvestigationResponse,
    InvestigationListResponse,
    InvestigationStatusResponse,
    StatsResponse,
    BugSnapshotResponse,
    ContextArtifactResponse,
    CodeCandidateResponse,
    CommitCandidateResponse,
    ProgressStepResponse,
    InvestigationReportResponse,
    InvestigationListItem,
)
from app.services.investigation_service import InvestigationService

router = APIRouter(prefix="/investigations", tags=["investigations"])


def _to_response(inv) -> InvestigationResponse:
    """Convert SQLAlchemy Investigation to response schema."""
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return InvestigationResponse(
        id=inv.id,
        issue_key=inv.issue_key,
        status=inv.status,
        triggered_by=inv.triggered_by,
        repo_override=inv.repo_override,
        additional_notes=inv.additional_notes,
        scope_json=inv.scope_json,
        error_message=inv.error_message,
        is_pinned=bool(inv.is_pinned),
        created_at=inv.created_at,
        updated_at=inv.updated_at,
        bug_snapshot=BugSnapshotResponse.model_validate(inv.bug_snapshot) if inv.bug_snapshot else None,
        context_artifacts=[
            ContextArtifactResponse.model_validate(a) for a in (inv.context_artifacts or [])
        ],
        code_candidates=[
            CodeCandidateResponse.model_validate(c) for c in sorted(inv.code_candidates or [], key=lambda x: x.rank or 99)
        ],
        commit_candidates=[
            CommitCandidateResponse.model_validate(c) for c in sorted(inv.commit_candidates or [], key=lambda x: x.confidence or 0, reverse=True)
        ],
        report=InvestigationReportResponse.model_validate(inv.report) if inv.report else None,
        progress_steps=[
            ProgressStepResponse.model_validate(s) for s in sorted(inv.progress_steps or [], key=lambda x: x.step_number)
        ],
    )


@router.post("", response_model=InvestigationResponse)
async def create_investigation(
    request: CreateInvestigationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create and run a new bug investigation."""
    service = InvestigationService(db)

    # Create the investigation
    investigation = await service.create_investigation(
        issue_key=request.issue_key,
        repo_override=request.repo_override,
        additional_notes=request.additional_notes,
        scope=request.scope,
    )

    # Run the investigation (for MVP, run synchronously)
    # In Phase 2, this would be a background task with Redis queue
    try:
        investigation = await service.run_investigation(investigation.id)
    except Exception as e:
        # Investigation already marked as failed in service
        investigation = await service.get_investigation(investigation.id)

    return _to_response(investigation)


@router.get("", response_model=InvestigationListResponse)
async def list_investigations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    classification: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all investigations with pagination and filtering."""
    service = InvestigationService(db)
    result = await service.list_investigations(
        page=page,
        page_size=page_size,
        classification_filter=classification,
        search=search,
    )

    return InvestigationListResponse(
        items=[InvestigationListItem(**item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Get dashboard statistics."""
    service = InvestigationService(db)
    stats = await service.get_stats()
    return StatsResponse(**stats)


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a full investigation with all details."""
    service = InvestigationService(db)
    investigation = await service.get_investigation(investigation_id)
    return _to_response(investigation)


@router.get("/{investigation_id}/status", response_model=InvestigationStatusResponse)
async def get_investigation_status(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get investigation status and progress (for polling during analysis)."""
    service = InvestigationService(db)
    investigation = await service.get_investigation(investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return InvestigationStatusResponse(
        id=investigation.id,
        status=investigation.status,
        progress_steps=[
            ProgressStepResponse.model_validate(s)
            for s in sorted(investigation.progress_steps or [], key=lambda x: x.step_number)
        ],
        error_message=investigation.error_message,
    )


@router.post("/{investigation_id}/rerun", response_model=InvestigationResponse)
async def rerun_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Re-run an existing investigation."""
    service = InvestigationService(db)
    old = await service.get_investigation(investigation_id)
    if not old:
        raise HTTPException(status_code=404, detail="Investigation not found")

    # Create new investigation with same params
    new_inv = await service.create_investigation(
        issue_key=old.issue_key,
        repo_override=old.repo_override,
        additional_notes=old.additional_notes,
        scope=old.scope_json,
    )

    try:
        new_inv = await service.run_investigation(new_inv.id)
    except Exception:
        new_inv = await service.get_investigation(new_inv.id)

    return _to_response(new_inv)


@router.patch("/{investigation_id}/pin")
async def toggle_pin(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Toggle the pinned status of an investigation."""
    service = InvestigationService(db)
    try:
        pinned = await service.toggle_pin(investigation_id)
        return {"pinned": pinned}
    except ValueError:
        raise HTTPException(status_code=404, detail="Investigation not found")


@router.delete("/{investigation_id}")
async def delete_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete an investigation."""
    service = InvestigationService(db)
    await service.delete_investigation(investigation_id)
    return {"deleted": True}
