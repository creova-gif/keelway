"""
FastAPI Typed Structured-Output & Content-Block Normalizer + Autonomous Self-Healing
Root-Causer Routes (`/v1/platform/healing`).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import (
    _enforce_workspace_permission,
    get_rbac_controller,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.structured_self_healing import (
    SelfHealingNotFoundError,
    SQLiteStructuredHealingEngine,
    StructuredHealingValidationError,
    StructuredSchemaRejectedError,
    structured_healing_engine,
)
from core.security.auth import Principal, current_principal

_ROLE_HEADER_ALIASES: Dict[str, str] = {
    "developer": "builder",
    "auditor": "viewer",
}


def get_structured_healing_engine() -> SQLiteStructuredHealingEngine:
    return structured_healing_engine


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
        headers = [
            (k, mapped if k.lower() == b"x-keelway-role" else v)
            for k, v in request.scope.get("headers", [])
        ]
        request = Request({**request.scope, "headers": headers})
    return _enforce_workspace_permission(request, principal, rbac, workspace_id, permission)


platform_healing_router = APIRouter(
    prefix="/v1/platform/healing",
    tags=["Platform Structured Output & Autonomous Self-Healing"],
    dependencies=[Depends(current_principal)],
)
router = platform_healing_router


class NormalizeContentBlocksRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    provider_format: str = Field(default="deepseek_opencore", max_length=64)
    model_id: str = Field(default="keelway-core:7b", max_length=128)
    raw_payload: Union[Dict[str, Any], str] = Field(default="")


class EnforceStructuredOutputRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    schema_name: str = Field(default="AgentDecisionContract", max_length=128)
    provider_format: str = Field(default="deepseek_opencore", max_length=64)
    model_id: str = Field(default="keelway-core:7b", max_length=128)
    json_schema: Dict[str, Any]
    raw_output: Union[Dict[str, Any], str]
    strict_mode: bool = Field(default=False)
    fail_closed: bool = Field(default=True)


class DiagnoseFailureRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    trace_id: Optional[str] = Field(default=None, max_length=128)
    workflow_name: str = Field(default="invoice-triage-agent", max_length=128)
    failed_step: Optional[Dict[str, Any]] = Field(default=None)


class ApplySelfHealingRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    promote_to_eval: bool = Field(default=True)
    eval_title: Optional[str] = Field(default=None, max_length=256)


@platform_healing_router.post("/content-blocks/normalize", response_model=None)
async def normalize_content_blocks_route(
    payload: NormalizeContentBlocksRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStructuredHealingEngine = Depends(get_structured_healing_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "read:all")
    try:
        return engine.normalize_content_blocks(
            workspace_id=payload.workspace_id,
            provider_format=payload.provider_format,
            raw_payload=payload.raw_payload,
            model_id=payload.model_id,
        )
    except (StructuredHealingValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "healing_validation_error"})


@platform_healing_router.post("/structured/enforce", response_model=None)
async def enforce_structured_output_route(
    payload: EnforceStructuredOutputRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStructuredHealingEngine = Depends(get_structured_healing_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.enforce_structured_output(
            workspace_id=payload.workspace_id,
            json_schema=payload.json_schema,
            raw_output=payload.raw_output,
            schema_name=payload.schema_name,
            provider_format=payload.provider_format,
            model_id=payload.model_id,
            strict_mode=payload.strict_mode,
            fail_closed=payload.fail_closed,
        )
    except StructuredSchemaRejectedError as exc:
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "code": "structured_schema_rejected", "run": exc.run_record},
        )
    except (StructuredHealingValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "healing_validation_error"})


@platform_healing_router.get("/structured/runs", response_model=None)
async def list_structured_output_runs_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStructuredHealingEngine = Depends(get_structured_healing_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_structured_runs(workspace_id=workspace_id, limit=limit)
    except (StructuredHealingValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "healing_validation_error"})


@platform_healing_router.post("/root-cause/diagnose", response_model=None)
async def diagnose_failure_root_cause_route(
    payload: DiagnoseFailureRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStructuredHealingEngine = Depends(get_structured_healing_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.diagnose_failure(
            workspace_id=payload.workspace_id,
            trace_id=payload.trace_id,
            workflow_name=payload.workflow_name,
            failed_step=payload.failed_step,
        )
    except SelfHealingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.args[0] if exc.args else exc)
        ) from exc
    except (StructuredHealingValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "healing_validation_error"})


@platform_healing_router.post("/root-cause/{diagnosis_id}/apply", response_model=None)
async def apply_self_healing_patch_route(
    diagnosis_id: str,
    request: Request,
    payload: ApplySelfHealingRequest = Body(default_factory=ApplySelfHealingRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStructuredHealingEngine = Depends(get_structured_healing_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.apply_healing_patch(
            workspace_id=payload.workspace_id,
            diagnosis_id=diagnosis_id,
            promote_to_eval=payload.promote_to_eval,
            eval_title=payload.eval_title,
        )
    except SelfHealingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc.args[0] if exc.args else exc)
        ) from exc
    except (StructuredHealingValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "healing_validation_error"})


@platform_healing_router.get("/root-cause/diagnoses", response_model=None)
async def list_self_healing_diagnoses_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteStructuredHealingEngine = Depends(get_structured_healing_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_diagnoses(workspace_id=workspace_id, limit=limit)
    except (StructuredHealingValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "healing_validation_error"})
