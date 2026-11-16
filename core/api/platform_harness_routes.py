"""
FastAPI Universal Coding-Agent Co-Harness, Single-Use P-10 Tickets & Worktree CI Gate
Routes (`/v1/platform/harness/*`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import _enforce_workspace_permission, get_rbac_controller
from core.platform.agent_coharness import (
    AgentCoharnessValidationError,
    ApprovalTicketConflictError,
    ApprovalTicketNotFoundError,
    SQLiteAgentCoharnessEngine,
    agent_coharness_engine,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import Principal, current_principal

_ROLE_HEADER_ALIASES: Dict[str, str] = {"developer": "builder", "auditor": "viewer"}


def get_agent_coharness_engine() -> SQLiteAgentCoharnessEngine:
    return agent_coharness_engine


def _enforce_rbac(
    request: Request,
    principal: Principal,
    rbac: WorkspaceRbacController,
    workspace_id: str,
    permission: str,
) -> Dict[str, Any]:
    raw_role = request.headers.get("x-keelway-role", "").strip().lower()
    if raw_role in _ROLE_HEADER_ALIASES:
        mapped = _ROLE_HEADER_ALIASES[raw_role].encode("latin-1")
        headers = [(k, mapped if k.lower() == b"x-keelway-role" else v) for k, v in request.scope.get("headers", [])]
        request = Request({**request.scope, "headers": headers})
    return _enforce_workspace_permission(request, principal, rbac, workspace_id, permission)


platform_harness_router = APIRouter(
    prefix="/v1/platform/harness",
    tags=["Platform Coding-Agent Co-Harness & Worktree CI Gate"],
    dependencies=[Depends(current_principal)],
)
router = platform_harness_router


class RenderHookManifestRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    agent_host: Literal["claude_code", "cursor", "codex_cli"] = Field(default="claude_code")
    mode: Literal["enforce", "audit_only"] = Field(default="enforce")


class HarnessInterceptRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    agent_host: Literal["claude_code", "cursor", "codex_cli"] = Field(default="claude_code")
    tool_name: str = Field(default="Bash", max_length=128)
    command: str = Field(default="git push origin main", max_length=8192)
    ticket_id: Optional[str] = Field(default=None, max_length=128)


class DecideApprovalTicketRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    decision: Literal["APPROVED", "DENIED"]
    reviewer: str = Field(default="lead-engineer", max_length=128)
    reason: str = Field(default="Verified safe workspace scope", max_length=1024)


class WorktreeCandidateSpec(BaseModel):
    candidate_id: str = Field(..., min_length=1, max_length=128)
    worktree_branch: str = Field(..., min_length=1, max_length=256)
    model_id: str = Field(..., min_length=1, max_length=128)
    provider_tier: Literal["local_opencore", "frontier_byom"]
    tests_passed: bool
    eval_score: float = Field(..., ge=0.0, le=1.0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    diff_excerpt: str = Field(default="", max_length=4096)


class EvaluateWorktreeCiGateRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_name: str = Field(default="pr-worktree-arena", max_length=128)
    diff_summary: str = Field(default="Refactor retry backoff & add unit test in core/platform/", max_length=2048)
    min_eval_score: float = Field(default=0.85, ge=0.0, le=1.0)
    candidates: Optional[List[WorktreeCandidateSpec]] = Field(default=None)


@platform_harness_router.post("/hooks/render", response_model=None)
async def render_harness_hooks_route(
    request: Request,
    payload: RenderHookManifestRequest = Body(default_factory=RenderHookManifestRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteAgentCoharnessEngine = Depends(get_agent_coharness_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "read:all")
    try:
        return engine.render_hook_manifest(
            workspace_id=payload.workspace_id,
            agent_host=payload.agent_host,
            mode=payload.mode,
        )
    except (AgentCoharnessValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "agent_coharness_validation_error"})


@platform_harness_router.post("/intercept", response_model=None)
async def intercept_tool_call_route(
    request: Request,
    payload: HarnessInterceptRequest = Body(default_factory=HarnessInterceptRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteAgentCoharnessEngine = Depends(get_agent_coharness_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.intercept_tool_call(
            workspace_id=payload.workspace_id,
            agent_host=payload.agent_host,
            tool_name=payload.tool_name,
            command=payload.command,
            ticket_id=payload.ticket_id,
        )
    except (AgentCoharnessValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "agent_coharness_validation_error"})


@platform_harness_router.get("/tickets", response_model=None)
async def list_approval_tickets_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    ticket_status: Optional[str] = Query(default=None, alias="status"),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteAgentCoharnessEngine = Depends(get_agent_coharness_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_tickets(workspace_id=workspace_id, status=ticket_status, limit=limit)
    except (AgentCoharnessValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "agent_coharness_validation_error"})


@platform_harness_router.post("/tickets/{ticket_id}/decide", response_model=None)
async def decide_approval_ticket_route(
    ticket_id: str,
    payload: DecideApprovalTicketRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteAgentCoharnessEngine = Depends(get_agent_coharness_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.decide_ticket(
            workspace_id=payload.workspace_id,
            ticket_id=ticket_id,
            decision=payload.decision,
            reviewer=payload.reviewer,
            reason=payload.reason,
        )
    except ApprovalTicketNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.args[0] if exc.args else exc)) from exc
    except ApprovalTicketConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (AgentCoharnessValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "agent_coharness_validation_error"})


@platform_harness_router.post("/ci-gate/evaluate", response_model=None)
async def evaluate_worktree_ci_gate_route(
    request: Request,
    payload: EvaluateWorktreeCiGateRequest = Body(default_factory=EvaluateWorktreeCiGateRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteAgentCoharnessEngine = Depends(get_agent_coharness_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.evaluate_worktree_ci_gate(
            workspace_id=payload.workspace_id,
            workflow_name=payload.workflow_name,
            diff_summary=payload.diff_summary,
            min_eval_score=payload.min_eval_score,
            candidates=[c.model_dump() for c in payload.candidates] if payload.candidates is not None else None,
        )
    except (AgentCoharnessValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "agent_coharness_validation_error"})


@platform_harness_router.get("/ci-gate/runs", response_model=None)
async def list_worktree_ci_gate_runs_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteAgentCoharnessEngine = Depends(get_agent_coharness_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_worktree_ci_gate_runs(workspace_id=workspace_id, limit=limit)
    except (AgentCoharnessValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "agent_coharness_validation_error"})
