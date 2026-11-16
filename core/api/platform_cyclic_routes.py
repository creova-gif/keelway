"""
FastAPI Cyclic KFlow Bounded Reflection Loops, Saga Compensation & Cost-Privacy Autopilot
Routes (`/v1/platform/kflow`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import (
    _enforce_workspace_permission,
    get_rbac_controller,
)
from core.platform.kflow_cyclic_autopilot import (
    CyclicKFlowPolicyViolationError,
    CyclicKFlowValidationError,
    SQLiteCyclicKFlowEngine,
    cyclic_kflow_engine,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import Principal, current_principal


def get_cyclic_kflow_engine() -> SQLiteCyclicKFlowEngine:
    return cyclic_kflow_engine


def _enforce_rbac(
    request: Request,
    principal: Principal,
    rbac: WorkspaceRbacController,
    workspace_id: str,
    permission: str,
) -> Dict[str, Any]:
    return _enforce_workspace_permission(request, principal, rbac, workspace_id, permission)


platform_cyclic_router = APIRouter(
    prefix="/v1/platform/kflow",
    tags=["Platform Cyclic KFlow & Autopilot"],
    dependencies=[Depends(current_principal)],
)
router = platform_cyclic_router


class CyclicKFlowValidateRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_id: str = Field(default="WF-CYCLIC-01", max_length=128)
    nodes: Optional[List[Dict[str, Any]]] = Field(default=None)
    loop_edges: Optional[List[Dict[str, Any]]] = Field(default=None)


class CyclicKFlowExecuteRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_id: str = Field(default="WF-CYCLIC-01", max_length=128)
    nodes: Optional[List[Dict[str, Any]]] = Field(default=None)
    loop_edges: Optional[List[Dict[str, Any]]] = Field(default=None)
    max_iterations_override: Optional[int] = Field(default=None)
    max_iterations: Optional[int] = Field(default=None)
    critic_threshold: float = Field(default=0.85)
    fan_out_shards: Optional[int] = Field(default=None)
    simulate_timeout: bool = Field(default=False)
    initial_state: Optional[Dict[str, Any]] = Field(default=None)
    approved_node_ids: Optional[List[str]] = Field(default=None)


class AutopilotSimulateRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_id: str = Field(default="WF-CYCLIC-01", max_length=128)
    nodes: Optional[List[Dict[str, Any]]] = Field(default=None)
    loop_edges: Optional[List[Dict[str, Any]]] = Field(default=None)
    budget_cap_usd: float = Field(default=0.15)
    privacy_policy: str = Field(default="hybrid_balanced", max_length=64)
    expected_loop_multiplier: int = Field(default=2)


@platform_cyclic_router.post("/cyclic/validate", response_model=None)
async def validate_cyclic_kflow_route(
    payload: CyclicKFlowValidateRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteCyclicKFlowEngine = Depends(get_cyclic_kflow_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "read:all")
    try:
        return engine.validate_cyclic_graph(
            workspace_id=payload.workspace_id,
            workflow_id=payload.workflow_id,
            nodes=payload.nodes,
            loop_edges=payload.loop_edges,
        )
    except (CyclicKFlowValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "cyclic_validation_error"})


@platform_cyclic_router.post("/cyclic/execute", response_model=None)
async def execute_cyclic_kflow_route(
    payload: CyclicKFlowExecuteRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteCyclicKFlowEngine = Depends(get_cyclic_kflow_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    if payload.approved_node_ids and any(str(nid).strip() for nid in payload.approved_node_ids):
        _enforce_rbac(request, principal, rbac, payload.workspace_id, "p10:approve")
    eff_max_iter = (
        payload.max_iterations_override
        if payload.max_iterations_override is not None
        else payload.max_iterations
    )
    try:
        return engine.execute_cyclic_graph(
            workspace_id=payload.workspace_id,
            workflow_id=payload.workflow_id,
            nodes=payload.nodes,
            loop_edges=payload.loop_edges,
            max_iterations_override=eff_max_iter,
            critic_threshold=payload.critic_threshold,
            fan_out_shards=payload.fan_out_shards,
            simulate_timeout=payload.simulate_timeout,
            initial_state=payload.initial_state,
            approved_node_ids=payload.approved_node_ids,
        )
    except CyclicKFlowPolicyViolationError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "policy_violation"})
    except (CyclicKFlowValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "cyclic_validation_error"})


@platform_cyclic_router.get("/cyclic/runs", response_model=None)
async def list_cyclic_kflow_runs_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    workflow_id: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteCyclicKFlowEngine = Depends(get_cyclic_kflow_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_cyclic_runs(workspace_id=workspace_id, workflow_id=workflow_id, limit=limit)
    except (CyclicKFlowValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "cyclic_validation_error"})


@platform_cyclic_router.get("/cyclic/runs/{run_id}")
async def get_cyclic_kflow_run_route(
    run_id: str,
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteCyclicKFlowEngine = Depends(get_cyclic_kflow_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    found = engine.get_cyclic_run(workspace_id=workspace_id, run_id=run_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cyclic KFlow run '{run_id}' not found in workspace '{workspace_id}'.",
        )
    return found


@platform_cyclic_router.post("/autopilot/simulate", response_model=None)
async def simulate_kflow_autopilot_route(
    payload: AutopilotSimulateRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteCyclicKFlowEngine = Depends(get_cyclic_kflow_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.simulate_autopilot(
            workspace_id=payload.workspace_id,
            workflow_id=payload.workflow_id,
            nodes=payload.nodes,
            loop_edges=payload.loop_edges,
            budget_cap_usd=payload.budget_cap_usd,
            privacy_policy=payload.privacy_policy,
            expected_loop_multiplier=payload.expected_loop_multiplier,
        )
    except (CyclicKFlowValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "cyclic_validation_error"})


@platform_cyclic_router.get("/autopilot/simulations", response_model=None)
async def list_kflow_autopilot_simulations_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    workflow_id: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteCyclicKFlowEngine = Depends(get_cyclic_kflow_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_autopilot_simulations(workspace_id=workspace_id, workflow_id=workflow_id, limit=limit)
    except (CyclicKFlowValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "cyclic_validation_error"})
