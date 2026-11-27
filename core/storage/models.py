"""
SQLAlchemy ORM models for Keelway Core.
"""

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from sqlalchemy import (
    String,
    Float,
    Integer,
    DateTime,
    Enum as SAEnum,
    JSON,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from core.orchestration.state import TaskState


class Base(DeclarativeBase):
    pass


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskRecord(Base):
    __tablename__ = "keelway_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    state: Mapped[TaskState] = mapped_column(
        SAEnum(TaskState), default=TaskState.CREATED, index=True
    )
    owner: Mapped[str] = mapped_column(String(100), default="anonymous")
    budget_usd: Mapped[float] = mapped_column(Float, default=0.50)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    payload: Mapped[dict] = mapped_column(JSON, default=dict)

    traces: Mapped[List["TraceRecord"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    evidence: Mapped[List["EvidenceRecord"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class TraceRecord(Base):
    __tablename__ = "keelway_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("keelway_tasks.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(50), default="success")
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped[Optional["TaskRecord"]] = relationship(back_populates="traces")


class EvidenceRecord(Base):
    __tablename__ = "keelway_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("keelway_tasks.id", ondelete="SET NULL"), index=True
    )
    source_uri: Mapped[str] = mapped_column(String(512))
    commit_sha: Mapped[Optional[str]] = mapped_column(String(40))
    classification: Mapped[str] = mapped_column(String(50), default="UNVERIFIED")
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    excerpt: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    task: Mapped[Optional["TaskRecord"]] = relationship(back_populates="evidence")


class MemoryRecord(Base):
    __tablename__ = "keelway_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    scope: Mapped[str] = mapped_column(String(100), default="project", index=True)
    key: Mapped[str] = mapped_column(String(255), index=True)
    content: Mapped[str] = mapped_column(Text)
    provenance_uri: Mapped[Optional[str]] = mapped_column(String(512))
    vector_embedding: Mapped[Optional[list]] = mapped_column(JSON)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ApiTokenRecord(Base):
    __tablename__ = "keelway_api_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class PairingCodeRecord(Base):
    """Single-use code that a phone exchanges for a phone-role token; only its hash is stored."""
    __tablename__ = "keelway_pairing_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    token_id: Mapped[Optional[str]] = mapped_column(String(36))


class AuditEventRecord(Base):
    """Append-only, hash-chained audit trail: entry_hash = sha256(prev_hash + canonical fields)."""

    __tablename__ = "keelway_audit_events"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[str] = mapped_column(String(40), index=True)
    actor: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(100))
    resource: Mapped[str] = mapped_column(String(512))
    allowed: Mapped[bool] = mapped_column()
    prev_hash: Mapped[str] = mapped_column(String(64), unique=True)
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)


class AgentManifestRecord(Base):
    """Registered agent manifests with versioning and instant kill-switch."""

    __tablename__ = "keelway_agent_manifests"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # name@version
    name: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[str] = mapped_column(String(32))
    owner: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(500))
    digest: Mapped[str] = mapped_column(String(64), index=True)
    manifest_json: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ConversationRecord(Base):
    """Persisted AI workspace conversation with serialized turn history."""

    __tablename__ = "keelway_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(32), default="ask")
    provider: Mapped[str] = mapped_column(String(32), default="local")
    owner: Mapped[str] = mapped_column(String(100), default="anonymous", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    turns: Mapped[List[dict]] = mapped_column(JSON, default=list)
