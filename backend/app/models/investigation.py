import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ForeignKey, JSON, Enum as SAEnum
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import relationship
import enum
from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


def utcnow():
    return datetime.utcnow()


class InvestigationStatus(str, enum.Enum):
    CREATED = "CREATED"
    FETCHING_CONTEXT = "FETCHING_CONTEXT"
    ANALYZING = "ANALYZING"
    GENERATING_REPORT = "GENERATING_REPORT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Classification(str, enum.Enum):
    LIKELY_REGRESSION = "LIKELY_REGRESSION"
    LIKELY_INTENTIONAL = "LIKELY_INTENTIONAL"
    UNCLEAR = "UNCLEAR"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"


class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(String, primary_key=True, default=generate_uuid)
    issue_key = Column(String, nullable=False, index=True)
    status = Column(String, default=InvestigationStatus.CREATED.value)
    triggered_by = Column(String, nullable=True)
    repo_override = Column(String, nullable=True)
    additional_notes = Column(Text, nullable=True)
    scope_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
    is_pinned = Column(Integer, default=0)  # 0=false, 1=true for SQLite compat

    # Relationships
    bug_snapshot = relationship("BugSnapshot", back_populates="investigation", uselist=False, cascade="all, delete-orphan")
    context_artifacts = relationship("ContextArtifact", back_populates="investigation", cascade="all, delete-orphan")
    code_candidates = relationship("CodeCandidate", back_populates="investigation", cascade="all, delete-orphan")
    commit_candidates = relationship("CommitCandidate", back_populates="investigation", cascade="all, delete-orphan")
    report = relationship("InvestigationReport", back_populates="investigation", uselist=False, cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="investigation", cascade="all, delete-orphan")
    progress_steps = relationship("ProgressStep", back_populates="investigation", cascade="all, delete-orphan")


class BugSnapshot(Base):
    __tablename__ = "bug_snapshots"

    id = Column(String, primary_key=True, default=generate_uuid)
    investigation_id = Column(String, ForeignKey("investigations.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    expected_behavior = Column(Text, nullable=True)
    actual_behavior = Column(Text, nullable=True)
    environment_json = Column(JSON, nullable=True)
    priority = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    component = Column(String, nullable=True)
    labels_json = Column(JSON, nullable=True)
    assignee = Column(String, nullable=True)
    assigned_team = Column(String, nullable=True)
    reporter = Column(String, nullable=True)
    status = Column(String, nullable=True)
    linked_issues_json = Column(JSON, nullable=True)
    comments_json = Column(JSON, nullable=True)
    attachments_json = Column(JSON, nullable=True)

    investigation = relationship("Investigation", back_populates="bug_snapshot")


class ContextArtifact(Base):
    __tablename__ = "context_artifacts"

    id = Column(String, primary_key=True, default=generate_uuid)
    investigation_id = Column(String, ForeignKey("investigations.id"), nullable=False)
    source_type = Column(String, nullable=False)  # jira | confluence | github
    source_id = Column(String, nullable=True)
    title = Column(String, nullable=True)
    url = Column(String, nullable=True)
    relevance_score = Column(Float, nullable=True)
    content_summary = Column(Text, nullable=True)
    key_excerpt = Column(Text, nullable=True)
    relevance_tag = Column(String, nullable=True)  # CONTRADICTS | SUPPORTS | RELATED
    metadata_json = Column(JSON, nullable=True)

    investigation = relationship("Investigation", back_populates="context_artifacts")


class CodeCandidate(Base):
    __tablename__ = "code_candidates"

    id = Column(String, primary_key=True, default=generate_uuid)
    investigation_id = Column(String, ForeignKey("investigations.id"), nullable=False)
    rank = Column(Integer, nullable=True)
    repo = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    symbol = Column(String, nullable=True)  # function/class name
    confidence = Column(Float, nullable=False)
    rationale = Column(Text, nullable=True)
    code_snippet = Column(Text, nullable=True)
    suspect_line = Column(Integer, nullable=True)

    investigation = relationship("Investigation", back_populates="code_candidates")


class CommitCandidate(Base):
    __tablename__ = "commit_candidates"

    id = Column(String, primary_key=True, default=generate_uuid)
    investigation_id = Column(String, ForeignKey("investigations.id"), nullable=False)
    repo = Column(String, nullable=False)
    commit_sha = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=True)
    pr_title = Column(String, nullable=True)
    author = Column(String, nullable=True)
    confidence = Column(Float, nullable=False)
    suspicion_level = Column(String, nullable=True)  # high | medium | low
    classification = Column(String, nullable=True)
    rationale = Column(Text, nullable=True)
    commit_message = Column(Text, nullable=True)
    committed_at = Column(DateTime, nullable=True)
    files_changed = Column(JSON, nullable=True)

    investigation = relationship("Investigation", back_populates="commit_candidates")


class InvestigationReport(Base):
    __tablename__ = "investigation_reports"

    id = Column(String, primary_key=True, default=generate_uuid)
    investigation_id = Column(String, ForeignKey("investigations.id"), nullable=False)
    executive_summary = Column(Text, nullable=True)
    classification = Column(String, nullable=True)
    recommendation = Column(String, nullable=True)  # ASSIGN_TO_COMMIT_OWNER, etc.
    recommendation_detail = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    key_findings_json = Column(JSON, nullable=True)
    suggested_action = Column(Text, nullable=True)
    suggested_code_direction = Column(Text, nullable=True)
    suggested_owner = Column(String, nullable=True)
    evidence_timeline_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    investigation = relationship("Investigation", back_populates="report")


class ProgressStep(Base):
    __tablename__ = "progress_steps"

    id = Column(String, primary_key=True, default=generate_uuid)
    investigation_id = Column(String, ForeignKey("investigations.id"), nullable=False)
    step_number = Column(Integer, nullable=False)
    step_name = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending | running | completed | failed
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    result_summary = Column(String, nullable=True)

    investigation = relationship("Investigation", back_populates="progress_steps")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    investigation_id = Column(String, ForeignKey("investigations.id"), nullable=True)
    action = Column(String, nullable=False)
    actor = Column(String, nullable=True)
    timestamp = Column(DateTime, default=utcnow)
    details_json = Column(JSON, nullable=True)

    investigation = relationship("Investigation", back_populates="audit_logs")
