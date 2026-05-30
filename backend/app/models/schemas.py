from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime


# === Request Schemas ===

class CreateInvestigationRequest(BaseModel):
    issue_key: str = Field(..., description="Jira issue key, e.g. PROJ-1234")
    repo_override: Optional[str] = Field(None, description="Override GitHub repo, e.g. org/repo-name")
    additional_notes: Optional[str] = Field(None, description="User's hunches or additional context")
    scope: Optional[dict] = Field(
        default={
            "search_jira": True,
            "search_confluence": True,
            "search_github": True,
            "deep_history": False,
        },
        description="Investigation scope toggles"
    )


class UpdateInvestigationRequest(BaseModel):
    is_pinned: Optional[bool] = None


class FeedbackRequest(BaseModel):
    helpful: bool
    comment: Optional[str] = None


# === Response Schemas ===

class BugSnapshotResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None
    environment_json: Optional[dict] = None
    priority: Optional[str] = None
    severity: Optional[str] = None
    component: Optional[str] = None
    labels_json: Optional[list] = None
    assignee: Optional[str] = None
    assigned_team: Optional[str] = None
    reporter: Optional[str] = None
    status: Optional[str] = None
    linked_issues_json: Optional[list] = None
    comments_json: Optional[list] = None
    attachments_json: Optional[list] = None

    class Config:
        from_attributes = True


class ContextArtifactResponse(BaseModel):
    id: str
    source_type: str
    source_id: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    relevance_score: Optional[float] = None
    content_summary: Optional[str] = None
    key_excerpt: Optional[str] = None
    relevance_tag: Optional[str] = None
    metadata_json: Optional[dict] = None

    class Config:
        from_attributes = True


class CodeCandidateResponse(BaseModel):
    id: str
    rank: Optional[int] = None
    repo: str
    file_path: str
    symbol: Optional[str] = None
    confidence: float
    rationale: Optional[str] = None
    code_snippet: Optional[str] = None
    suspect_line: Optional[int] = None

    class Config:
        from_attributes = True


class CommitCandidateResponse(BaseModel):
    id: str
    repo: str
    commit_sha: str
    pr_number: Optional[int] = None
    pr_title: Optional[str] = None
    author: Optional[str] = None
    confidence: float
    suspicion_level: Optional[str] = None
    classification: Optional[str] = None
    rationale: Optional[str] = None
    commit_message: Optional[str] = None
    committed_at: Optional[datetime] = None
    files_changed: Optional[list] = None

    class Config:
        from_attributes = True


class ProgressStepResponse(BaseModel):
    id: str
    step_number: int
    step_name: str
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result_summary: Optional[str] = None

    class Config:
        from_attributes = True


class InvestigationReportResponse(BaseModel):
    id: str
    executive_summary: Optional[str] = None
    classification: Optional[str] = None
    recommendation: Optional[str] = None
    recommendation_detail: Optional[str] = None
    confidence_score: Optional[float] = None
    key_findings_json: Optional[list] = None
    suggested_action: Optional[str] = None
    suggested_code_direction: Optional[str] = None
    suggested_owner: Optional[str] = None
    evidence_timeline_json: Optional[list] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InvestigationResponse(BaseModel):
    id: str
    issue_key: str
    status: str
    triggered_by: Optional[str] = None
    repo_override: Optional[str] = None
    additional_notes: Optional[str] = None
    scope_json: Optional[dict] = None
    error_message: Optional[str] = None
    is_pinned: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    bug_snapshot: Optional[BugSnapshotResponse] = None
    context_artifacts: list[ContextArtifactResponse] = []
    code_candidates: list[CodeCandidateResponse] = []
    commit_candidates: list[CommitCandidateResponse] = []
    report: Optional[InvestigationReportResponse] = None
    progress_steps: list[ProgressStepResponse] = []

    class Config:
        from_attributes = True


class InvestigationListItem(BaseModel):
    id: str
    issue_key: str
    status: str
    title: Optional[str] = None  # from bug_snapshot
    classification: Optional[str] = None  # from report
    confidence_score: Optional[float] = None  # from report
    priority: Optional[str] = None  # from bug_snapshot
    assignee: Optional[str] = None  # from bug_snapshot
    is_pinned: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InvestigationListResponse(BaseModel):
    items: list[InvestigationListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class InvestigationStatusResponse(BaseModel):
    id: str
    status: str
    progress_steps: list[ProgressStepResponse] = []
    error_message: Optional[str] = None


class StatsResponse(BaseModel):
    total: int
    regressions: int
    intentional: int
    unclear: int
    pending: int
    failed: int


class HealthResponse(BaseModel):
    status: str
    provider_mode: str
    database: str
    version: str


# === Log/Stack Trace Analysis Schemas ===

class AnalyzeLogsRequest(BaseModel):
    raw_input: str = Field(..., description="Raw log output, stack trace, or error message")
    title: Optional[str] = Field(None, description="Optional title/summary of the issue")
    source: Optional[str] = Field(None, description="Source system (e.g., 'production', 'staging', 'CI')")

class StackFrameResponse(BaseModel):
    language: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    function: Optional[str] = None

class ErrorResponse(BaseModel):
    type: str
    message: str

class LogAnalysisResponse(BaseModel):
    input_type: str
    errors: list[ErrorResponse] = []
    stack_frames: list[StackFrameResponse] = []
    http_errors: list[dict] = []
    timeouts: list[dict] = []
    oom_detected: bool = False
    connection_errors: list[dict] = []
    key_files: list[dict] = []
    root_cause_hints: list[str] = []
    severity: str
    summary: str
