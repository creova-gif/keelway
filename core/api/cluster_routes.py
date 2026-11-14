"""
FastAPI Control-Plane Routes for Multi-Node GPU Cluster, Model Lifecycle & PostgreSQL Governance (`/v1/cluster`).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.cluster.lifecycle import (
    LifecycleGateError,
    LifecycleModelNotFoundError,
    ModelLifecycleEntry,
    ModelLifecycleRegistry,
    model_lifecycle_registry,
)
from core.cluster.postgres_adapter import (
    BudgetReservationResult,
    PostgresGovernanceAdapter,
    postgres_governance_adapter,
)
from core.cluster.scheduler import (
    ClusterNode,
    ClusterNodeNotFoundError,
    ClusterScheduler,
    PlacementCapacityError,
    PlacementDecision,
    PlacementValidationError,
    cluster_scheduler,
)
from core.security.auth import Principal, current_principal


def get_cluster_scheduler() -> ClusterScheduler:
    """Return active GPU cluster scheduler (overridable in isolated tests)."""
    return cluster_scheduler


def get_lifecycle_registry() -> ModelLifecycleRegistry:
    """Return active model lifecycle registry (overridable in isolated tests)."""
    return model_lifecycle_registry


def get_postgres_governance_adapter() -> PostgresGovernanceAdapter:
    """Return active PostgreSQL/parity governance adapter (overridable in isolated tests)."""
    return postgres_governance_adapter


router = APIRouter(
    prefix="/v1/cluster",
    tags=["Cluster & Fleet"],
    dependencies=[Depends(current_principal)],
)


class NodeRegisterRequest(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=128)
    runtime: str = Field(..., min_length=1, max_length=64)
    region: str = Field(..., min_length=1, max_length=64)
    total_vram_gb: float = Field(..., gt=0.0)
    free_vram_gb: Optional[float] = Field(default=None, ge=0.0)
    gpu_count: int = Field(default=1, ge=1)
    gpu_model: str = Field(default="Generic Accelerator", min_length=1, max_length=128)
    loaded_models: List[str] = Field(default_factory=list)
    active_requests: int = Field(default=0, ge=0)


class SchedulePlacementRequest(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=255)
    required_vram_gb: float = Field(default=16.0, gt=0.0)
    region_residency: str = Field(default="global", min_length=1, max_length=64)
    privacy_level: str = Field(default="standard", min_length=1, max_length=64)
    runtime_preference: Optional[str] = Field(default=None, max_length=64)
    tensor_parallel: int = Field(default=1, ge=1)


class LifecyclePromoteRequest(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=255)
    target_stage: str = Field(default="stable", min_length=1, max_length=32)
    traffic_weight_pct: int = Field(default=100, ge=0, le=100)


class LifecycleRollbackRequest(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=255)
    reason: str = Field(default="SLO regression detected", min_length=1, max_length=500)


class ReserveBudgetRequest(BaseModel):
    tenant_id: str = Field(default="default", min_length=1, max_length=128)
    amount_usd: float = Field(..., ge=0.0)
    actor: Optional[str] = Field(default=None, max_length=128)
    capability: str = Field(default="cluster.inference", min_length=1, max_length=128)
    monthly_limit_usd: Optional[float] = Field(default=None, ge=0.0)
    fallback_to_opencore: Optional[bool] = None


@router.get("/nodes")
async def list_cluster_nodes(
    region: Optional[str] = Query(default=None),
    runtime: Optional[str] = Query(default=None),
    include_drained: bool = Query(default=True),
    _: Principal = Depends(current_principal),
    scheduler: ClusterScheduler = Depends(get_cluster_scheduler),
) -> Dict[str, Any]:
    nodes = scheduler.list_nodes(region=region, runtime=runtime, include_drained=include_drained)
    serialized = [n.model_dump(mode="json") for n in nodes]
    return {
        "nodes": serialized,
        "total": len(serialized),
        "healthy_count": sum(1 for n in nodes if n.status == "healthy"),
        "drained_count": sum(1 for n in nodes if n.status == "drained"),
        "total_vram_gb": round(sum(n.total_vram_gb for n in nodes), 2),
        "free_vram_gb": round(sum(n.free_vram_gb for n in nodes), 2),
    }


@router.post("/nodes/register", response_model=ClusterNode, status_code=status.HTTP_201_CREATED)
async def register_cluster_node(
    req: NodeRegisterRequest,
    _: Principal = Depends(current_principal),
    scheduler: ClusterScheduler = Depends(get_cluster_scheduler),
) -> ClusterNode:
    try:
        return scheduler.register_node(
            node_id=req.node_id,
            runtime=req.runtime,
            region=req.region,
            total_vram_gb=req.total_vram_gb,
            free_vram_gb=req.free_vram_gb,
            gpu_count=req.gpu_count,
            gpu_model=req.gpu_model,
            loaded_models=req.loaded_models,
            active_requests=req.active_requests,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/nodes/{node_id}/drain", response_model=ClusterNode)
async def drain_cluster_node(
    node_id: str,
    _: Principal = Depends(current_principal),
    scheduler: ClusterScheduler = Depends(get_cluster_scheduler),
) -> ClusterNode:
    try:
        return scheduler.drain_node(node_id)
    except ClusterNodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/nodes/{node_id}/restore", response_model=ClusterNode)
async def restore_cluster_node(
    node_id: str,
    _: Principal = Depends(current_principal),
    scheduler: ClusterScheduler = Depends(get_cluster_scheduler),
) -> ClusterNode:
    try:
        return scheduler.restore_node(node_id)
    except ClusterNodeNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/schedule", response_model=PlacementDecision)
async def schedule_model_placement(
    req: SchedulePlacementRequest,
    _: Principal = Depends(current_principal),
    scheduler: ClusterScheduler = Depends(get_cluster_scheduler),
) -> PlacementDecision:
    try:
        return scheduler.schedule_placement(
            model_id=req.model_id,
            required_vram_gb=req.required_vram_gb,
            region_residency=req.region_residency,
            privacy_level=req.privacy_level,
            runtime_preference=req.runtime_preference,
            tensor_parallel=req.tensor_parallel,
        )
    except PlacementValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PlacementCapacityError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/lifecycle")
async def list_model_lifecycle(
    stage: Optional[str] = Query(default=None),
    _: Principal = Depends(current_principal),
    registry: ModelLifecycleRegistry = Depends(get_lifecycle_registry),
) -> Dict[str, Any]:
    entries = [e.model_dump(mode="json") for e in registry.list_entries(stage=stage)]
    return {
        "entries": entries,
        "models": entries,
        "total": len(entries),
    }


@router.post("/lifecycle/promote", response_model=ModelLifecycleEntry)
async def promote_lifecycle_model(
    req: LifecyclePromoteRequest,
    _: Principal = Depends(current_principal),
    registry: ModelLifecycleRegistry = Depends(get_lifecycle_registry),
) -> ModelLifecycleEntry:
    try:
        return registry.promote_model(
            model_id=req.model_id,
            target_stage=req.target_stage,
            traffic_weight_pct=req.traffic_weight_pct,
        )
    except LifecycleModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (LifecycleGateError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/lifecycle/rollback", response_model=ModelLifecycleEntry)
async def rollback_lifecycle_canary(
    req: LifecycleRollbackRequest,
    _: Principal = Depends(current_principal),
    registry: ModelLifecycleRegistry = Depends(get_lifecycle_registry),
) -> ModelLifecycleEntry:
    try:
        return registry.rollback_canary(model_id=req.model_id, reason=req.reason)
    except LifecycleModelNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/governance-adapter/status")
async def get_governance_adapter_status(
    _: Principal = Depends(current_principal),
    adapter: PostgresGovernanceAdapter = Depends(get_postgres_governance_adapter),
) -> Dict[str, Any]:
    return adapter.get_adapter_status()


@router.post("/governance-adapter/reserve-budget", response_model=BudgetReservationResult)
async def reserve_cluster_governance_budget(
    req: ReserveBudgetRequest,
    principal: Principal = Depends(current_principal),
    adapter: PostgresGovernanceAdapter = Depends(get_postgres_governance_adapter),
) -> JSONResponse:
    try:
        if req.monthly_limit_usd is not None or req.fallback_to_opencore is not None:
            adapter.configure_tenant_budget(
                tenant_id=req.tenant_id,
                monthly_limit_usd=req.monthly_limit_usd if req.monthly_limit_usd is not None else 100.0,
                fallback_to_opencore=True if req.fallback_to_opencore is None else req.fallback_to_opencore,
            )
        actor_id = req.actor or getattr(principal, "actor", None) or "api_client"
        result = adapter.reserve_spend_atomic(
            tenant_id=req.tenant_id,
            amount_usd=req.amount_usd,
            actor=str(actor_id),
            capability=req.capability,
        )
        return JSONResponse(status_code=result.status_code, content=result.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
