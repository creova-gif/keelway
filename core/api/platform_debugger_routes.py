"""
FastAPI Live Step-Through Debugger, Conditional Breakpoints, DLP-Guarded State Mutation
& 4D Routing CodeLens Bridge Routes (`/v1/platform/debugger`).

Exposes Phase 14 (`KEEL-DEBUG-021`) workspace-scoped conditional gutter breakpoints, paused
frame stepping (`step_over`, `step_into`, `continue`), DLP-enforced state mutation (`422`
`policy_violation`), and VS Code / Cursor Extension Host CodeLens URIs guarded by 5-role RBAC.
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
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.step_debugger import (
    DebuggerPolicyViolationError,
    SQLiteStepDebuggerEngine,
    step_debugger_engine,
)
from core.security.auth import Principal, current_principal

_PERMISSION_ALIASES: Dict[str, str] = {
    "workspace:read": "read:all",
    "workspaces:read": "read:all",
    "workflows:write": "agents:dispatch",
    "agents:execute": "workflows:run",
    "runs:approve_p10": "p10:approve",
}


def get_step_debugger_engine() -> SQLiteStepDebuggerEngine:
    return step_debugger_engine


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
    prefix="/v1/platform/debugger",
    tags=["Unified Platform Step-Through Debugger & IDE Extension Bridge"],
    dependencies=[Depends(current_principal)],
)
platform_debugger_router = router


class DebuggerBreakpointCreateRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_id: str = Field(default="WF-STUDIO-01", max_length=128)
    node_id: Optional[str] = Field(default=None, max_length=128)
    file_path: str = Field(default="workflows/refund_agent.py", max_length=512)
    line_number: Optional[int] = Field(default=None)
    condition_type: str = Field(default="always", max_length=64)
    threshold: Optional[float] = Field(default=None)
    enabled: bool = Field(default=True)
    label: Optional[str] = Field(default=None, max_length=512)


class DebuggerSessionStartRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_id: str = Field(default="WF-STUDIO-01", max_length=128)
    steps: Optional[List[Dict[str, Any]]] = Field(default=None)
    initial_state: Optional[Dict[str, Any]] = Field(default=None)
    initial_variables: Optional[Dict[str, Any]] = Field(default=None)


class DebuggerSessionStepRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    action: str = Field(default="step_over", max_length=64)
    state_patch: Optional[Dict[str, Any]] = Field(default=None)


class DebuggerCodeLensInspectRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_id: str = Field(default="WF-STUDIO-01", max_length=128)
    file_path: str = Field(default="workflows/refund_agent.py", max_length=512)
    source_code: Optional[str] = Field(default=None)


@router.post("/breakpoints", response_model=None)
async def set_debugger_breakpoint_route(
    payload: DebuggerBreakpointCreateRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStepDebuggerEngine = Depends(get_step_debugger_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:write")
    try:
        return engine.set_breakpoint(
            workspace_id=payload.workspace_id,
            workflow_id=payload.workflow_id,
            node_id=payload.node_id,
            file_path=payload.file_path,
            line_number=payload.line_number,
            condition_type=payload.condition_type,
            threshold=payload.threshold,
            enabled=payload.enabled,
            label=payload.label,
        )
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "policy_violation"})


@router.get("/breakpoints")
async def list_debugger_breakpoints_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    workflow_id: Optional[str] = Query(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStepDebuggerEngine = Depends(get_step_debugger_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    return engine.list_breakpoints(workspace_id=workspace_id, workflow_id=workflow_id)


@router.delete("/breakpoints/{breakpoint_id}")
async def delete_debugger_breakpoint_route(
    breakpoint_id: str,
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStepDebuggerEngine = Depends(get_step_debugger_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workflows:write")
    try:
        return engine.delete_breakpoint(workspace_id=workspace_id, breakpoint_id=breakpoint_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.args[0] if exc.args else exc)) from exc


@router.post("/sessions", response_model=None)
async def start_debugger_session_route(
    payload: DebuggerSessionStartRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStepDebuggerEngine = Depends(get_step_debugger_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:execute")
    eff_initial = payload.initial_state if payload.initial_state is not None else payload.initial_variables
    try:
        return engine.start_session(
            workspace_id=payload.workspace_id,
            workflow_id=payload.workflow_id,
            steps=payload.steps,
            initial_state=eff_initial,
        )
    except DebuggerPolicyViolationError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "policy_violation"})
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "invalid_debugger_request"})


@router.get("/sessions", response_model=None)
async def list_debugger_sessions_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=20, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStepDebuggerEngine = Depends(get_step_debugger_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return engine.list_sessions(workspace_id=workspace_id, limit=limit)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "invalid_debugger_request"})


@router.get("/sessions/{session_id}")
async def get_debugger_session_route(
    session_id: str,
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStepDebuggerEngine = Depends(get_step_debugger_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return engine.get_session(workspace_id=workspace_id, session_id=session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.args[0] if exc.args else exc)) from exc


@router.post("/sessions/{session_id}/step", response_model=None)
async def step_debugger_session_route(
    session_id: str,
    payload: DebuggerSessionStepRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStepDebuggerEngine = Depends(get_step_debugger_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:execute")
    try:
        return engine.step_session(
            workspace_id=payload.workspace_id,
            session_id=session_id,
            action=payload.action,
            state_patch=payload.state_patch,
        )
    except DebuggerPolicyViolationError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "policy_violation"})
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.args[0] if exc.args else exc)) from exc
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "invalid_debugger_request"})


@router.get("/codelens")
async def get_debugger_codelens_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    workflow_id: str = Query(default="WF-STUDIO-01"),
    file_path: str = Query(default="workflows/refund_agent.py"),
    source_code: Optional[str] = Query(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStepDebuggerEngine = Depends(get_step_debugger_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    return engine.get_codelens(
        workspace_id=workspace_id,
        workflow_id=workflow_id,
        file_path=file_path,
        source_code=source_code,
    )


@router.post("/codelens/inspect")
async def inspect_debugger_codelens_route(
    payload: DebuggerCodeLensInspectRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStepDebuggerEngine = Depends(get_step_debugger_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workspace:read")
    return engine.get_codelens(
        workspace_id=payload.workspace_id,
        workflow_id=payload.workflow_id,
        file_path=payload.file_path,
        source_code=payload.source_code,
    )
