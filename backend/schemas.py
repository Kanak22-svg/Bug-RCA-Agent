"""Pydantic schemas — internal types + API request/response models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ReproStatus = Literal["reproduced", "not_reproduced", "uncertain"]
Classification = Literal["LIKELY_INTENTIONAL", "LIKELY_REGRESSION", "UNCLEAR"]
Recommendation = Literal[
    "LEAD_REVIEW",
    "ASSIGN_TO_COMMIT_OWNER",
    "NEEDS_MORE_REPRO_DATA",
    "LIKELY_EXPECTED_BEHAVIOR",
    "LIKELY_REGRESSION",
    "MANUAL_DEEP_DIVE_REQUIRED",
]


# ---------- Provider domain models ----------

class JiraComment(BaseModel):
    author: str = ""
    body: str = ""
    created: str = ""


class JiraIssue(BaseModel):
    key: str
    title: str = ""
    description: str = ""
    expected_behavior: str = ""
    actual_behavior: str = ""
    repro_status: ReproStatus = "uncertain"
    repro_steps: list[str] = Field(default_factory=list)
    environment: dict[str, Any] = Field(default_factory=dict)
    failing_step: int | None = None
    repro_notes: str = ""
    priority: str = ""
    severity: str = ""
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    assignee: str = ""
    reporter: str = ""
    team: str = ""
    epic: str = ""
    linked_issue_keys: list[str] = Field(default_factory=list)
    comments: list[JiraComment] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    url: str = ""


class ConfluenceDoc(BaseModel):
    id: str
    title: str
    url: str = ""
    snippet: str = ""
    body: str = ""
    space: str = ""


class CommitInfo(BaseModel):
    sha: str
    message: str = ""
    author: str = ""
    date: str = ""
    files: list[str] = Field(default_factory=list)
    pr_number: int | None = None


class PullRequest(BaseModel):
    number: int
    title: str = ""
    body: str = ""
    author: str = ""
    merged_at: str | None = None
    files: list[str] = Field(default_factory=list)
    url: str = ""


class CodeHit(BaseModel):
    repo: str
    path: str
    snippet: str = ""
    score: float = 0.0
    symbol: str = ""


# ---------- Normalized bug ----------

class NormalizedBug(BaseModel):
    bug_id: str
    title: str
    expected_behavior: str = ""
    actual_behavior: str = ""
    reporter_steps: list[str] = Field(default_factory=list)
    manual_repro: dict[str, Any] = Field(default_factory=dict)
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


# ---------- API ----------

class AnalyzeRequest(BaseModel):
    issue_key: str
    repos: list[str] = Field(default_factory=list, description="Optional repo hints (owner/name).")
    triggered_by: str = "ui"


class InvestigationSummary(BaseModel):
    id: str
    issue_key: str
    status: str
    triggered_by: str
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class CodeCandidateOut(BaseModel):
    repo: str
    file_path: str
    symbol: str = ""
    confidence: float
    rationale: str = ""


class CommitCandidateOut(BaseModel):
    repo: str
    commit_sha: str
    pr_number: int | None = None
    confidence: float
    classification: str
    rationale: str = ""


class ContextArtifactOut(BaseModel):
    source_type: str
    source_id: str
    title: str
    url: str
    relevance_score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class FinalReportOut(BaseModel):
    summary_markdown: str
    classification: Classification
    recommendation: Recommendation
    confidence: float
    payload: dict[str, Any] = Field(default_factory=dict)


class InvestigationDetail(InvestigationSummary):
    bug: dict[str, Any] | None = None
    artifacts: list[ContextArtifactOut] = Field(default_factory=list)
    code_candidates: list[CodeCandidateOut] = Field(default_factory=list)
    commit_candidates: list[CommitCandidateOut] = Field(default_factory=list)
    report: FinalReportOut | None = None
