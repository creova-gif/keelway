"""
FastAPI OTel GenAI Flight-Tape, Time-Travel Replay, Trace-to-Eval & LangGraph Migrator Routes (`/v1/platform`).

Exposes Phase 11A (`KEEL-DEVX-018`) workspace-scoped OpenTelemetry GenAI / flat span ingestion with
pre-storage DLP secret scrubbing, deterministic counterfactual Flight-Tape replay, 1-click trace-to-eval
dataset promotion, and 100% static AST/Regex LangGraph-to-KFlow migration.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import (
    _enforce_workspace_permission,
    get_rbac_controller,
)
from core.platform.flight_tape import (
    SQLiteFlightTapeEngine,
    flight_tape_engine,
)
from core.platform.langgraph_migrator import (
    LangGraphMigrator,
    langgraph_migrator,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import Principal, current_principal

_PERMISSION_ALIASES: Dict[str, str] = {
    "workspace:read": "read:all",
    "workspaces:read": "read:all",
    "runs:approve_p10": "p10:approve",
}


def get_flight_tape_engine() -> SQLiteFlightTapeEngine:
    return flight_tape_engine


def get_langgraph_migrator() -> LangGraphMigrator:
    return langgraph_migrator


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
    prefix="/v1/platform",
    tags=["Unified Platform OTel Flight-Tape, Eval Promotion & LangGraph Migrator"],
    dependencies=[Depends(current_principal)],
)
platform_devx_routes_router = router


class TraceIngestRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_name: str = Field(default="agent-trace", max_length=256)
    source_framework: str = Field(default="opentelemetry_genai", max_length=128)
    trace_id: Optional[str] = Field(default=None, max_length=128)
    spans: Optional[List[Dict[str, Any]]] = Field(default=None)
    resource_spans: Optional[List[Dict[str, Any]]] = Field(default=None)
    resourceSpans: Optional[List[Dict[str, Any]]] = Field(default=None)


class TraceReplayRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    from_step_index: int = Field(default=0)
    override_prompt: Optional[str] = Field(default=None)
    override_model: Optional[str] = Field(default=None, max_length=256)
    override_state: Optional[Dict[str, Any]] = Field(default=None)


class TraceEvalPromoteRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    trace_id: str = Field(default="", max_length=128)
    title: Optional[str] = Field(default=None, max_length=512)
    expected_substrings: Optional[List[str]] = Field(default=None)
    forbidden_substrings: Optional[List[str]] = Field(default=None)
    created_by: Optional[str] = Field(default=None, max_length=256)


class LangGraphMigrateRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    source_code: str = Field(default="")
    source_language: str = Field(default="python", max_length=32)
    workflow_name: Optional[str] = Field(default=None, max_length=256)


@router.post("/traces/ingest")
async def ingest_platform_traces_route(
    payload: TraceIngestRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteFlightTapeEngine = Depends(get_flight_tape_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:dispatch")
    effective_resource_spans = (
        payload.resource_spans if payload.resource_spans is not None else payload.resourceSpans
    )
    try:
        return engine.ingest_traces(
            workspace_id=payload.workspace_id,
            workflow_name=payload.workflow_name,
            source_framework=payload.source_framework,
            spans=payload.spans,
            resource_spans=effective_resource_spans,
            trace_id=payload.trace_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/traces")
async def list_platform_traces_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=20),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteFlightTapeEngine = Depends(get_flight_tape_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return engine.list_tapes(workspace_id=workspace_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/traces/{trace_id}/replay")
async def replay_platform_trace_route(
    trace_id: str,
    payload: TraceReplayRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteFlightTapeEngine = Depends(get_flight_tape_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:dispatch")
    try:
        return engine.replay_tape(
            workspace_id=payload.workspace_id,
            trace_id=trace_id,
            from_step_index=payload.from_step_index,
            override_prompt=payload.override_prompt,
            override_model=payload.override_model,
            override_state=payload.override_state,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/eval/dataset/promote")
async def promote_platform_trace_to_eval_route(
    payload: TraceEvalPromoteRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteFlightTapeEngine = Depends(get_flight_tape_engine),
) -> Dict[str, Any]:
    verdict = _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:dispatch")
    effective_creator = (payload.created_by or "").strip() or verdict["actor_id"]
    try:
        return engine.promote_trace_to_eval(
            workspace_id=payload.workspace_id,
            trace_id=payload.trace_id,
            title=payload.title,
            expected_substrings=payload.expected_substrings,
            forbidden_substrings=payload.forbidden_substrings,
            created_by=effective_creator,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/eval/dataset")
async def list_platform_eval_dataset_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteFlightTapeEngine = Depends(get_flight_tape_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return engine.list_eval_cases(workspace_id=workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/migrate/langgraph")
async def migrate_platform_langgraph_route(
    payload: LangGraphMigrateRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    migrator: LangGraphMigrator = Depends(get_langgraph_migrator),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:dispatch")
    try:
        return migrator.migrate_source(
            source_code=payload.source_code,
            source_language=payload.source_language,
            workflow_name=payload.workflow_name,
            workspace_id=payload.workspace_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
