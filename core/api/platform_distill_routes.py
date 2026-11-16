"""
FastAPI Semantic Prompt Cache, Shadow Dual-Run Router & QLoRA Distillation Flywheel
Routes (`/v1/platform/distill/*`).
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Union

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import _enforce_workspace_permission, get_rbac_controller
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.shadow_distillation import (
    DEFAULT_CODE_RESPONSE,
    DEFAULT_FRONTIER_MODEL,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_SHADOW_PROMPT,
    SQLiteShadowDistillationEngine,
    ShadowDistillationValidationError,
    shadow_distillation_engine,
)
from core.security.auth import Principal, current_principal

_ROLE_HEADER_ALIASES: Dict[str, str] = {"developer": "builder", "auditor": "viewer"}


def get_shadow_distillation_engine() -> SQLiteShadowDistillationEngine:
    return shadow_distillation_engine


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


platform_distill_router = APIRouter(
    prefix="/v1/platform/distill",
    tags=["Platform Semantic Cache & QLoRA Distillation"],
    dependencies=[Depends(current_principal)],
)
router = platform_distill_router


class EvaluateShadowPromptRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    task_tag: str = Field(default="code-patch", max_length=128)
    prompt: str = Field(default=DEFAULT_SHADOW_PROMPT, max_length=32768)
    frontier_model: str = Field(default=DEFAULT_FRONTIER_MODEL, max_length=128)
    local_model: str = Field(default=DEFAULT_LOCAL_MODEL, max_length=128)
    frontier_response: str = Field(default=DEFAULT_CODE_RESPONSE, max_length=65536)
    local_response: str = Field(default=DEFAULT_CODE_RESPONSE, max_length=65536)
    frontier_cost_usd: float = Field(default=0.018)
    frontier_latency_ms: int = Field(default=840)
    local_latency_ms: int = Field(default=95)
    similarity_threshold: float = Field(default=0.82)
    bypass_cache: bool = Field(default=False)


class CompileDistillationDatasetRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    task_tag: str = Field(default="", max_length=128)
    export_format: Literal["sft_jsonl", "dpo_preference"] = Field(default="dpo_preference")
    target_base_model: str = Field(default=DEFAULT_LOCAL_MODEL, max_length=128)
    min_parity_score: float = Field(default=0.0)


class EvaluatePromotionGateRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    task_tag: str = Field(default="code-patch", max_length=128)
    target_local_model: str = Field(default=DEFAULT_LOCAL_MODEL, max_length=128)
    min_pairs: int = Field(default=3)
    min_avg_parity: float = Field(default=0.85)
    monthly_request_volume: int = Field(default=50000)


@platform_distill_router.post("/shadow/evaluate", response_model=None)
async def evaluate_shadow_prompt_route(
    request: Request,
    payload: EvaluateShadowPromptRequest = Body(default_factory=EvaluateShadowPromptRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteShadowDistillationEngine = Depends(get_shadow_distillation_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.evaluate_shadow_prompt(
            workspace_id=payload.workspace_id,
            task_tag=payload.task_tag,
            prompt=payload.prompt,
            frontier_model=payload.frontier_model,
            local_model=payload.local_model,
            frontier_response=payload.frontier_response,
            local_response=payload.local_response,
            frontier_cost_usd=payload.frontier_cost_usd,
            frontier_latency_ms=payload.frontier_latency_ms,
            local_latency_ms=payload.local_latency_ms,
            similarity_threshold=payload.similarity_threshold,
            bypass_cache=payload.bypass_cache,
        )
    except (ShadowDistillationValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "shadow_distillation_validation_error"})


@platform_distill_router.get("/shadow/pairs", response_model=None)
async def list_shadow_pairs_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    task_tag: str = Query(default=""),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteShadowDistillationEngine = Depends(get_shadow_distillation_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_shadow_pairs(workspace_id=workspace_id, task_tag=task_tag, limit=limit)
    except (ShadowDistillationValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "shadow_distillation_validation_error"})


@platform_distill_router.get("/cache/stats", response_model=None)
async def get_semantic_cache_stats_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteShadowDistillationEngine = Depends(get_shadow_distillation_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.get_cache_stats(workspace_id=workspace_id)
    except (ShadowDistillationValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "shadow_distillation_validation_error"})


@platform_distill_router.post("/datasets/compile", response_model=None)
async def compile_distillation_dataset_route(
    request: Request,
    payload: CompileDistillationDatasetRequest = Body(default_factory=CompileDistillationDatasetRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteShadowDistillationEngine = Depends(get_shadow_distillation_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.compile_distillation_dataset(
            workspace_id=payload.workspace_id,
            task_tag=payload.task_tag,
            export_format=payload.export_format,
            target_base_model=payload.target_base_model,
            min_parity_score=payload.min_parity_score,
        )
    except (ShadowDistillationValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "shadow_distillation_validation_error"})


@platform_distill_router.get("/datasets", response_model=None)
async def list_distillation_datasets_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteShadowDistillationEngine = Depends(get_shadow_distillation_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_distillation_datasets(workspace_id=workspace_id, limit=limit)
    except (ShadowDistillationValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "shadow_distillation_validation_error"})


@platform_distill_router.post("/promotion/evaluate", response_model=None)
async def evaluate_promotion_gate_route(
    request: Request,
    payload: EvaluatePromotionGateRequest = Body(default_factory=EvaluatePromotionGateRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteShadowDistillationEngine = Depends(get_shadow_distillation_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.evaluate_promotion_gate(
            workspace_id=payload.workspace_id,
            task_tag=payload.task_tag,
            target_local_model=payload.target_local_model,
            min_pairs=payload.min_pairs,
            min_avg_parity=payload.min_avg_parity,
            monthly_request_volume=payload.monthly_request_volume,
        )
    except (ShadowDistillationValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "shadow_distillation_validation_error"})
