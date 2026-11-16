"""
FastAPI Formal Safety State-Machine Verifier & Federated Edge-to-Cluster Agent Mesh
Routes (`/v1/platform/safety/*` & `/v1/platform/mesh/*`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import _enforce_workspace_permission, get_rbac_controller
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.safety_and_mesh import (
    MeshSovereigntyViolationError,
    SafetyMeshValidationError,
    SafetyVerificationNotFoundError,
    SQLiteSafetyAndMeshEngine,
    safety_and_mesh_engine,
)
from core.security.auth import Principal, current_principal

_ROLE_HEADER_ALIASES: Dict[str, str] = {"developer": "builder", "auditor": "viewer"}


def get_safety_and_mesh_engine() -> SQLiteSafetyAndMeshEngine:
    return safety_and_mesh_engine


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


platform_safety_mesh_router = APIRouter(
    prefix="/v1/platform",
    tags=["Platform Formal Safety Verifier & Federated Edge Mesh"],
    dependencies=[Depends(current_principal)],
)
router = platform_safety_mesh_router


class SafetyNodeSpec(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=128)
    role: str = Field(default="agent", max_length=64)
    tool_kind: str = Field(default="read_only", max_length=64)
    requires_p10: bool = Field(default=False)
    max_iterations: int = Field(default=1)
    data_classification: str = Field(default="internal", max_length=64)


class SafetyEdgeSpec(BaseModel):
    from_node: str = Field(..., min_length=1, max_length=128)
    to_node: str = Field(..., min_length=1, max_length=128)
    condition: Optional[str] = Field(default=None, max_length=256)


class SafetyVerifyRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_id: str = Field(default="WF-TREASURY-01", max_length=128)
    workflow_name: str = Field(default="treasury-wire-approver", max_length=128)
    nodes: Optional[List[SafetyNodeSpec]] = Field(default=None)
    edges: Optional[List[SafetyEdgeSpec]] = Field(default=None)
    airgap_mode: bool = Field(default=False)
    inject_p10_guards: bool = Field(default=False)


class RegisterMeshNodeRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    node_id: Optional[str] = Field(default=None, max_length=128)
    name: str = Field(..., min_length=1, max_length=128)
    tier: str = Field(..., max_length=64)
    hardware_hal: str = Field(..., max_length=64)
    region: str = Field(default="local-loopback", max_length=128)
    vram_gb: int = Field(default=32)
    status: str = Field(default="ONLINE", max_length=32)


class DispatchMeshHandoffRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_name: str = Field(default="clinical-synthesis-pipeline", max_length=128)
    task_summary: str = Field(default="Ingest patient intake & synthesize anonymized cohort summary", max_length=1024)
    data_classification: str = Field(default="restricted_pii", max_length=64)
    allow_sanitized_burst: bool = Field(default=True)
    force_raw_cloud_burst: bool = Field(default=False)


@platform_safety_mesh_router.post("/safety/verify", response_model=None)
async def verify_workflow_safety_route(
    request: Request,
    payload: SafetyVerifyRequest = Body(default_factory=SafetyVerifyRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSafetyAndMeshEngine = Depends(get_safety_and_mesh_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.verify_workflow(
            workspace_id=payload.workspace_id,
            workflow_id=payload.workflow_id,
            workflow_name=payload.workflow_name,
            nodes=[n.model_dump() for n in payload.nodes] if payload.nodes is not None else None,
            edges=[e.model_dump() for e in payload.edges] if payload.edges is not None else None,
            airgap_mode=payload.airgap_mode,
            inject_p10_guards=payload.inject_p10_guards,
        )
    except (SafetyMeshValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "safety_mesh_validation_error"})


@platform_safety_mesh_router.get("/safety/verifications", response_model=None)
async def list_safety_verifications_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSafetyAndMeshEngine = Depends(get_safety_and_mesh_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_verifications(workspace_id=workspace_id, limit=limit)
    except (SafetyMeshValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "safety_mesh_validation_error"})


@platform_safety_mesh_router.get("/safety/verifications/{verification_id}", response_model=None)
async def get_safety_verification_route(
    verification_id: str,
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSafetyAndMeshEngine = Depends(get_safety_and_mesh_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.get_verification(workspace_id=workspace_id, verification_id=verification_id)
    except SafetyVerificationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.args[0] if exc.args else exc)) from exc
    except (SafetyMeshValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "safety_mesh_validation_error"})


@platform_safety_mesh_router.post("/mesh/nodes", response_model=None)
async def register_mesh_node_route(
    payload: RegisterMeshNodeRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSafetyAndMeshEngine = Depends(get_safety_and_mesh_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.register_node(
            workspace_id=payload.workspace_id,
            node_id=payload.node_id,
            name=payload.name,
            tier=payload.tier,
            hardware_hal=payload.hardware_hal,
            region=payload.region,
            vram_gb=payload.vram_gb,
            status=payload.status,
        )
    except (SafetyMeshValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "safety_mesh_validation_error"})


@platform_safety_mesh_router.get("/mesh/nodes", response_model=None)
async def list_mesh_nodes_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSafetyAndMeshEngine = Depends(get_safety_and_mesh_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_nodes(workspace_id=workspace_id)
    except (SafetyMeshValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "safety_mesh_validation_error"})


@platform_safety_mesh_router.post("/mesh/dispatch", response_model=None)
async def dispatch_mesh_handoff_route(
    request: Request,
    payload: DispatchMeshHandoffRequest = Body(default_factory=DispatchMeshHandoffRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSafetyAndMeshEngine = Depends(get_safety_and_mesh_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.dispatch_handoff(
            workspace_id=payload.workspace_id,
            workflow_name=payload.workflow_name,
            task_summary=payload.task_summary,
            data_classification=payload.data_classification,
            allow_sanitized_burst=payload.allow_sanitized_burst,
            force_raw_cloud_burst=payload.force_raw_cloud_burst,
        )
    except MeshSovereigntyViolationError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "mesh_sovereignty_violation"})
    except (SafetyMeshValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "safety_mesh_validation_error"})


@platform_safety_mesh_router.get("/mesh/handoffs", response_model=None)
async def list_mesh_handoffs_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSafetyAndMeshEngine = Depends(get_safety_and_mesh_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_handoffs(workspace_id=workspace_id, limit=limit)
    except (SafetyMeshValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "safety_mesh_validation_error"})
