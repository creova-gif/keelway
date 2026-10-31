"""
SQLAlchemy ORM models for Kora AI Core.
"""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import (
    Boolean,
    Column,
    String,
    Float,
    Integer,
    DateTime,
    Enum as SAEnum,
    JSON,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship

from core.orchestration.state import TaskState

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TaskRecord(Base):
    __tablename__ = "kora_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    state = Column(SAEnum(TaskState), default=TaskState.CREATED, nullable=False, index=True)
    owner = Column(String(100), default="anonymous", nullable=False)
    budget_usd = Column(Float, default=0.50, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    payload = Column(JSON, default=dict, nullable=False)

    traces = relationship("TraceRecord", back_populates="task", cascade="all, delete-orphan")
    evidence = relationship("EvidenceRecord", back_populates="task", cascade="all, delete-orphan")


class TraceRecord(Base):
    __tablename__ = "kora_traces"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("kora_tasks.id", ondelete="CASCADE"), nullable=True, index=True)
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, default=0, nullable=False)
    completion_tokens = Column(Integer, default=0, nullable=False)
    latency_ms = Column(Float, default=0.0, nullable=False)
    cost_usd = Column(Float, default=0.0, nullable=False)
    status = Column(String(50), default="success", nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    task = relationship("TaskRecord", back_populates="traces")


class EvidenceRecord(Base):
    __tablename__ = "kora_evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    task_id = Column(String(36), ForeignKey("kora_tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    source_uri = Column(String(512), nullable=False)
    commit_sha = Column(String(40), nullable=True)
    classification = Column(String(50), default="UNVERIFIED", nullable=False)
    content_hash = Column(String(64), nullable=True)
    excerpt = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    task = relationship("TaskRecord", back_populates="evidence")


class MemoryRecord(Base):
    __tablename__ = "kora_memories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scope = Column(String(100), default="project", nullable=False, index=True)
    key = Column(String(255), nullable=False, index=True)
    content = Column(Text, nullable=False)
    provenance_uri = Column(String(512), nullable=True)
    vector_embedding = Column(JSON, nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ApiTokenRecord(Base):
    __tablename__ = "kora_api_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class AuditEventRecord(Base):
    """Append-only, hash-chained audit trail: entry_hash = sha256(prev_hash + canonical fields)."""

    __tablename__ = "kora_audit_events"

    seq = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(40), nullable=False, index=True)
    actor = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False)
    action = Column(String(100), nullable=False)
    resource = Column(String(512), nullable=False)
    allowed = Column(Boolean, nullable=False)
    prev_hash = Column(String(64), nullable=False, unique=True)
    entry_hash = Column(String(64), nullable=False, unique=True)
