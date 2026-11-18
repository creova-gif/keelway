"""
FastAPI Golden-Thread Studio, Bidirectional KFlow AST Sync, OS Sandbox Blast-Radius Radar
& Prompt Regression Gate Routes (`/v1/platform/studio`).

Exposes Phase 12A (`KEEL-STUDIO-019`) workspace-scoped static Python/TypeScript KFlow Code <-> Graph
synchronization, Seatbelt/air-gap blast-radius boundary receipts, and deterministic Prompt/Schema
Regression Gate evaluation enforced by 5-role RBAC.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import (
    _enforce_workspace_permission,
    get_rbac_controller,
)
from core.platform.kflow_bidirectional_sync import (
    KFlowBidirectionalSyncEngine,
    PayloadTooLargeError,
    kflow_bidirectional_sync_engine,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.sandbox_blast_radius import (
    SQLiteSandboxBlastRadiusEngine,
    sandbox_blast_radius_engine,
)
from core.security.auth import Principal, current_principal

_PERMISSION_ALIASES: Dict[str, str] = {
    "workspace:read": "read:all",
    "workspaces:read": "read:all",
    "runs:approve_p10": "p10:approve",
}


def get_kflow_sync_engine() -> KFlowBidirectionalSyncEngine:
    return kflow_bidirectional_sync_engine


def get_blast_radius_engine() -> SQLiteSandboxBlastRadiusEngine:
    return sandbox_blast_radius_engine


def _enforce_rbac(
    request: Request,
    principal: Principal,
    rbac: WorkspaceRbacController,
    workspace_id: str,
    permission: str,
) -> Dict[str, Any]:
    mapped = _PERMISSION_ALIASES.get(permission, permission)
    return _enforce_workspace_permission(request, principal, rbac, workspace_id, mapped)


router = APIRouter(
    prefix="/v1/platform/studio",
    tags=["Unified Platform Golden-Thread Studio, Bidirectional AST Sync & Blast-Radius"],
    dependencies=[Depends(current_principal)],
)
platform_studio_router = router


class KFlowStudioSyncRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    direction: str = Field(default="code_to_graph", max_length=32)
    language: str = Field(default="python", max_length=32)
    workflow_id: str = Field(default="WF-STUDIO-01", max_length=128)
    source_code: Optional[str] = Field(default=None)
    nodes: Optional[List[Dict[str, Any]]] = Field(default=None)
    persist: bool = Field(default=False)


class BlastRadiusRecordRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    trace_id: Optional[str] = Field(default=None, max_length=128)
    workflow_id: Optional[str] = Field(default=None, max_length=128)
    fs_reads: Optional[List[str]] = Field(default=None)
    fs_writes: Optional[List[str]] = Field(default=None)
    blocked_paths: Optional[List[str]] = Field(default=None)
    egress_attempts: int = Field(default=0)
    blocked_egress_hosts: Optional[List[str]] = Field(default=None)
    p10_gates_triggered: int = Field(default=0)
    seatbelted: bool = Field(default=True)


class PromptGateEvaluateRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    candidate_prompt_version: str = Field(default="p-15", max_length=128)
    candidate_model_id: str = Field(default="keelway-core:7b", max_length=256)
    candidate_prompt_text: str = Field(default="")
    required_json_keys: Optional[List[str]] = Field(default=None)
    min_pass_rate: float = Field(default=0.9)


@router.post("/kflow/sync")
async def sync_studio_kflow_route(
    payload: KFlowStudioSyncRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    sync_engine: KFlowBidirectionalSyncEngine = Depends(get_kflow_sync_engine),
) -> Dict[str, Any]:
    norm_direction = str(payload.direction or "").strip().lower()
    if not payload.persist and norm_direction == "code_to_graph":
        _enforce_rbac(request, principal, rbac, payload.workspace_id, "workspace:read")
    else:
        _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:dispatch")

    try:
        return sync_engine.sync(
            workspace_id=payload.workspace_id,
            direction=payload.direction,
            language=payload.language,
            workflow_id=payload.workflow_id,
            source_code=payload.source_code,
            nodes=payload.nodes,
            persist=payload.persist,
        )
    except (PayloadTooLargeError, BufferError) as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except SyntaxError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        if "exceeds 262144 byte limit" in str(exc):
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/blast-radius/record")
async def record_studio_blast_radius_route(
    payload: BlastRadiusRecordRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSandboxBlastRadiusEngine = Depends(get_blast_radius_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:dispatch")
    try:
        return engine.record_blast_radius(
            workspace_id=payload.workspace_id,
            trace_id=payload.trace_id,
            workflow_id=payload.workflow_id,
            fs_reads=payload.fs_reads,
            fs_writes=payload.fs_writes,
            blocked_paths=payload.blocked_paths,
            egress_attempts=payload.egress_attempts,
            blocked_egress_hosts=payload.blocked_egress_hosts,
            p10_gates_triggered=payload.p10_gates_triggered,
            seatbelted=payload.seatbelted,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/blast-radius")
async def list_studio_blast_radius_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    trace_id: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSandboxBlastRadiusEngine = Depends(get_blast_radius_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return engine.list_blast_radius_audits(
            workspace_id=workspace_id,
            trace_id=trace_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/prompt-gate/evaluate")
async def evaluate_studio_prompt_gate_route(
    payload: PromptGateEvaluateRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSandboxBlastRadiusEngine = Depends(get_blast_radius_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:dispatch")
    try:
        return engine.evaluate_prompt_gate(
            workspace_id=payload.workspace_id,
            candidate_prompt_version=payload.candidate_prompt_version,
            candidate_model_id=payload.candidate_model_id,
            candidate_prompt_text=payload.candidate_prompt_text,
            required_json_keys=payload.required_json_keys,
            min_pass_rate=payload.min_pass_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/prompt-gate/runs")
async def list_studio_prompt_gate_runs_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=20, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSandboxBlastRadiusEngine = Depends(get_blast_radius_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return engine.list_prompt_gate_runs(
            workspace_id=workspace_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
