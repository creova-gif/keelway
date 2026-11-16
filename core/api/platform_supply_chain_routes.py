"""
FastAPI Cryptographic MCP & Skill Merkle Lockfile, Poisoning/Rug-Pull Firewall & Conformance
Benchmark Routes (`/v1/platform/supply-chain/*`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import _enforce_workspace_permission, get_rbac_controller
from core.platform.mcp_lockfile_and_bench import (
    DEFAULT_BENCH_MODEL_ID,
    DEFAULT_BENCH_TARGET_ID,
    DEFAULT_LOCKFILE_NAME,
    DEFAULT_TOOL_INPUT_SCHEMA,
    LockfileNotFoundError,
    SQLiteSupplyChainLockEngine,
    SupplyChainValidationError,
    supply_chain_lock_engine,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import Principal, current_principal

_ROLE_HEADER_ALIASES: Dict[str, str] = {"developer": "builder", "auditor": "viewer"}


def get_supply_chain_lock_engine() -> SQLiteSupplyChainLockEngine:
    return supply_chain_lock_engine


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


platform_supply_chain_router = APIRouter(
    prefix="/v1/platform/supply-chain",
    tags=["Platform MCP Lockfile & Conformance Benchmark"],
    dependencies=[Depends(current_principal)],
)
router = platform_supply_chain_router


class McpLockToolSpecModel(BaseModel):
    server_id: str = Field(..., max_length=128)
    tool_name: str = Field(..., max_length=128)
    version: str = Field(default="1.0.0", max_length=128)
    description: str = Field(..., max_length=32768)
    input_schema_json: str = Field(default=DEFAULT_TOOL_INPUT_SCHEMA, max_length=65536)


class PinMcpLockfileRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    lockfile_name: str = Field(default=DEFAULT_LOCKFILE_NAME, max_length=128)
    tools: Optional[List[McpLockToolSpecModel]] = Field(default=None)


class VerifyMcpLockfileRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    lockfile_id: Optional[str] = Field(default=None, max_length=128)
    live_tools: Optional[List[McpLockToolSpecModel]] = Field(default=None)
    simulate_mode: str = Field(default="clean", max_length=64)


class ConformanceScenarioModel(BaseModel):
    scenario_id: str = Field(..., max_length=128)
    schema_valid: bool
    deterministic_match: bool
    latency_ms: int
    frontier_cost_usd: float = Field(default=0.014)


class RunConformanceBenchmarkRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    target_id: str = Field(default=DEFAULT_BENCH_TARGET_ID, max_length=128)
    target_kind: str = Field(default="mcp_server", max_length=64)
    model_id: str = Field(default=DEFAULT_BENCH_MODEL_ID, max_length=128)
    latency_budget_ms: int = Field(default=250)
    min_conformance_score: float = Field(default=0.90)
    scenarios: Optional[List[ConformanceScenarioModel]] = Field(default=None)


@platform_supply_chain_router.post("/lock/pin", response_model=None)
async def pin_mcp_lockfile_route(
    request: Request,
    payload: PinMcpLockfileRequest = Body(default_factory=PinMcpLockfileRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSupplyChainLockEngine = Depends(get_supply_chain_lock_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.pin_mcp_lockfile(
            workspace_id=payload.workspace_id,
            lockfile_name=payload.lockfile_name,
            tools=payload.tools,
        )
    except (SupplyChainValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "supply_chain_validation_error"})


@platform_supply_chain_router.get("/lock/snapshots", response_model=None)
async def list_mcp_lockfiles_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSupplyChainLockEngine = Depends(get_supply_chain_lock_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_mcp_lockfiles(workspace_id=workspace_id, limit=limit)
    except (SupplyChainValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "supply_chain_validation_error"})


@platform_supply_chain_router.post("/lock/verify", response_model=None)
async def verify_mcp_lockfile_route(
    request: Request,
    payload: VerifyMcpLockfileRequest = Body(default_factory=VerifyMcpLockfileRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSupplyChainLockEngine = Depends(get_supply_chain_lock_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.verify_mcp_lockfile(
            workspace_id=payload.workspace_id,
            lockfile_id=payload.lockfile_id,
            live_tools=payload.live_tools,
            simulate_mode=payload.simulate_mode,
        )
    except LockfileNotFoundError as exc:
        return JSONResponse(status_code=404, content={"detail": str(exc), "code": "lockfile_not_found"})
    except (SupplyChainValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "supply_chain_validation_error"})


@platform_supply_chain_router.get("/lock/verifications", response_model=None)
async def list_mcp_lock_verifications_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSupplyChainLockEngine = Depends(get_supply_chain_lock_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_lock_verifications(workspace_id=workspace_id, limit=limit)
    except (SupplyChainValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "supply_chain_validation_error"})


@platform_supply_chain_router.post("/bench/run", response_model=None)
async def run_conformance_benchmark_route(
    request: Request,
    payload: RunConformanceBenchmarkRequest = Body(default_factory=RunConformanceBenchmarkRequest),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSupplyChainLockEngine = Depends(get_supply_chain_lock_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    try:
        return engine.run_conformance_benchmark(
            workspace_id=payload.workspace_id,
            target_id=payload.target_id,
            target_kind=payload.target_kind,
            model_id=payload.model_id,
            latency_budget_ms=payload.latency_budget_ms,
            min_conformance_score=payload.min_conformance_score,
            scenarios=payload.scenarios,
        )
    except (SupplyChainValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "supply_chain_validation_error"})


@platform_supply_chain_router.get("/bench/runs", response_model=None)
async def list_conformance_benchmarks_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    limit: int = Query(default=25, ge=1, le=200),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteSupplyChainLockEngine = Depends(get_supply_chain_lock_engine),
) -> Union[Dict[str, Any], JSONResponse]:
    _enforce_rbac(request, principal, rbac, workspace_id, "read:all")
    try:
        return engine.list_conformance_benchmarks(workspace_id=workspace_id, limit=limit)
    except (SupplyChainValidationError, ValueError) as exc:
        return JSONResponse(status_code=422, content={"detail": str(exc), "code": "supply_chain_validation_error"})
