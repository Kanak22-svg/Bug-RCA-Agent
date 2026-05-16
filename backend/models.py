"""ORM models matching the data model in the spec."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    issue_key: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="CREATED")
    triggered_by: Mapped[str] = mapped_column(String, default="ui")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    snapshot: Mapped["BugSnapshot"] = relationship(back_populates="investigation", uselist=False, cascade="all, delete-orphan")
    artifacts: Mapped[list["ContextArtifact"]] = relationship(back_populates="investigation", cascade="all, delete-orphan")
    code_candidates: Mapped[list["CodeCandidate"]] = relationship(back_populates="investigation", cascade="all, delete-orphan")
    commit_candidates: Mapped[list["CommitCandidate"]] = relationship(back_populates="investigation", cascade="all, delete-orphan")
    report: Mapped["FinalReport"] = relationship(back_populates="investigation", uselist=False, cascade="all, delete-orphan")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="investigation", cascade="all, delete-orphan")


class BugSnapshot(Base):
    __tablename__ = "bug_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), unique=True)
    title: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    expected_behavior: Mapped[str] = mapped_column(Text, default="")
    actual_behavior: Mapped[str] = mapped_column(Text, default="")
    repro_status: Mapped[str] = mapped_column(String, default="uncertain")
    repro_notes: Mapped[str] = mapped_column(Text, default="")
    environment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    investigation: Mapped[Investigation] = relationship(back_populates="snapshot")


class ContextArtifact(Base):
    __tablename__ = "context_artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    source_type: Mapped[str] = mapped_column(String)  # jira | confluence | github
    source_id: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    investigation: Mapped[Investigation] = relationship(back_populates="artifacts")


class CodeCandidate(Base):
    __tablename__ = "code_candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    repo: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    symbol: Mapped[str] = mapped_column(String, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")

    investigation: Mapped[Investigation] = relationship(back_populates="code_candidates")


class CommitCandidate(Base):
    __tablename__ = "commit_candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    repo: Mapped[str] = mapped_column(String)
    commit_sha: Mapped[str] = mapped_column(String, default="")
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    classification: Mapped[str] = mapped_column(String, default="suspect")
    rationale: Mapped[str] = mapped_column(Text, default="")

    investigation: Mapped[Investigation] = relationship(back_populates="commit_candidates")


class FinalReport(Base):
    __tablename__ = "final_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), unique=True)
    summary_markdown: Mapped[str] = mapped_column(Text, default="")
    classification: Mapped[str] = mapped_column(String, default="UNCLEAR")
    recommendation: Mapped[str] = mapped_column(String, default="MANUAL_DEEP_DIVE_REQUIRED")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    investigation: Mapped[Investigation] = relationship(back_populates="report")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String, default="system")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    investigation: Mapped[Investigation] = relationship(back_populates="audit_logs")
