"""Keelway Core Data Models and Domain Schemas.
Conforms strictly to PRD-001 and API/Data Contracts specification.
"""
from __future__ import annotations

import enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class RunStatus(str, enum.Enum):
    CREATED = "created"
    POLICY_CHECK = "policy_check"
    EXECUTING = "executing"
    EVALUATING = "evaluating"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PR_READY = "pr_ready"
    DEPLOYED = "deployed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DecisionEnum(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class AgentKind(str, enum.Enum):
    CODING = "coding"
    TEST_GENERATION = "test_generation"
    REFACTOR = "refactor"


class RunManifest(BaseModel):
    schema_version: str = "1"
    run_id: str
    org_id: str
    project_id: str
    actor_id: str
    agent_kind: str = "coding"
    source_commit_sha: str
    policy_id: str
    model_route_id: str
    dataset_digest: str
    toolchain_digest: str
    status: RunStatus = RunStatus.CREATED
    created_at: str
    classification: str = "internal"
    budget_token_limit: int = 50000
    tokens_used: int = 0
    cost_cents_limit: int = 500
    cost_cents_used: int = 0


class AuditEvent(BaseModel):
    id: str
    run_id: str
    seq: int
    kind: str
    payload_digest: str
    prev_hash: str
    hash: str
    created_at: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class ToolAuthorizationRequest(BaseModel):
    run_id: str
    tool: str
    action_digest: str
    scope: Dict[str, Any]
    actor_id: str
    policy_version: str


class PolicyDecision(BaseModel):
    decision: DecisionEnum
    reason_code: str
    decision_id: str
    expires_at: str
    run_id: str
    action_digest: str
    signature: str


class ApprovalRequest(BaseModel):
    id: str
    run_id: str
    patch_hash: str
    diff_content: str
    eval_score: float
    eval_passed: bool
    estimated_cost_cents: int
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, EXPIRED, INVALIDATED
    requested_at: str
    expires_at: str
    approver_id: Optional[str] = None
    decision_signature: Optional[str] = None


class ApprovalDecision(BaseModel):
    approval_id: str
    decision: str  # APPROVED, REJECTED
    approver_id: str
    patch_hash: str  # Must match ApprovalRequest.patch_hash exactly
    actor_role: str = "Platform Engineer"


class EvalResult(BaseModel):
    eval_id: str
    run_id: str
    dataset_id: str
    dataset_digest: str
    baseline_score: float
    candidate_score: float
    score_delta: float
    threshold: float
    passed: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class PullRequestRequest(BaseModel):
    run_id: str
    approval_id: str
    title: str
    description: str


class PullRequestResult(BaseModel):
    pr_id: str
    pr_url: str
    branch: str
    head_sha: str
    status: str


class DeploymentRequest(BaseModel):
    run_id: str
    approval_id: str
    target_environment: str = "staging"


class DeploymentResult(BaseModel):
    deployment_id: str
    environment: str
    commit_sha: str
    status: str
    webhook_url: Optional[str] = None
    receipt_digest: str
