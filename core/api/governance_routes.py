"""
FastAPI Control-Plane Routes for Enterprise Tenant Governance (Layer 6).

Exposes multi-tenant policy CRUD, one-time scoped API key lifecycle (`kw_live_...`),
pre-flight governance evaluation (residency, rate limits, spend caps, OpenCore fallback),
spend metering, persistence telemetry, and SHA-256 hash-chained audit verification under `/v1/governance`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError

from core.security.auth import Principal, current_principal
from core.security.tenant_governance import (
    DataResidencyZone,
    GovernanceAuditEntry,
    GovernanceDecision,
    GovernanceError,
    KeyAuthenticationResult,
    ScopedAPIKeyMetadata,
    SpendSnapshot,
    TenantGovernanceController,
    TenantGovernanceEngine,
    TenantPolicy,
    get_governance_controller,
)


def get_governance_engine() -> TenantGovernanceEngine:
    """Dependency returning the active governance controller (overridable in isolated tests)."""
    return get_governance_controller()


router = APIRouter(
    prefix="/v1/governance",
    tags=["Governance"],
    dependencies=[Depends(current_principal)],
)


class TenantPolicyUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    allowed_categories: Optional[List[str]] = None
    allowed_providers: Optional[List[str]] = None
    residency_zone: Optional[DataResidencyZone] = None
    daily_spend_limit_usd: Optional[float] = Field(default=None, ge=0.0)
    monthly_spend_limit_usd: Optional[float] = Field(default=None, ge=0.0)
    fallback_to_opencore_on_budget_exceeded: Optional[bool] = None
    requests_per_minute: Optional[int] = Field(default=None, ge=1)
    tokens_per_minute: Optional[int] = Field(default=None, ge=1)
    log_redacted_prompts: Optional[bool] = None
    retention_days: Optional[int] = Field(default=None, ge=1, le=3650)


class ScopedKeyIssueRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=255)
    scopes: List[str] = Field(..., min_length=1)
    expires_at: Optional[datetime] = None


class ScopedKeyIssuedResponse(ScopedAPIKeyMetadata):
    api_key: str = Field(..., description="One-time raw key (`kw_live_...`). Never persisted or shown again.")


class ScopedKeyVerifyRequest(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=256)
    required_scope: Optional[str] = Field(default=None, max_length=128)


class GovernanceEvaluateRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    requested_model: str = Field(..., min_length=1, max_length=255)
    provider: str = Field(..., min_length=1, max_length=128)
    category: str = Field(..., min_length=1, max_length=128)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    estimated_tokens: int = Field(default=0, ge=0)
    prompt_preview: Optional[str] = None
    forbid_open_weight: bool = False


class SpendRecordRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    cost_usd: float = Field(..., ge=0.0)
    tokens: int = Field(default=0, ge=0)
    model_id: str = Field(default="unspecified", min_length=1, max_length=255)
    provider: str = Field(default="unspecified", min_length=1, max_length=128)


class GovernanceAuditResponse(BaseModel):
    entries: List[GovernanceAuditEntry]
    total: int
    chain_valid: bool
    broken_at_seq: Optional[int] = None


class GovernancePersistenceResponse(BaseModel):
    persistent: bool
    backend: Literal["sqlite_wal", "memory"]
    tenants_count: int
    keys_count: int
    audit_events_count: int
    chain_verified: bool
    chain_head: str


@router.get("/persistence", response_model=GovernancePersistenceResponse)
async def get_governance_persistence(
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceController = Depends(get_governance_engine),
) -> GovernancePersistenceResponse:
    return GovernancePersistenceResponse(**engine.get_persistence_telemetry())


@router.post("/tenants", response_model=TenantPolicy, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    policy: TenantPolicy,
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> TenantPolicy:
    try:
        return engine.create_tenant(policy)
    except GovernanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc


@router.get("/tenants", response_model=List[TenantPolicy])
async def list_tenants(
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> List[TenantPolicy]:
    return engine.list_tenants()


@router.get("/tenants/{tenant_id}", response_model=TenantPolicy)
async def get_tenant(
    tenant_id: str,
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> TenantPolicy:
    policy = engine.get_tenant(tenant_id)
    if policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tenant '{tenant_id}' not found.")
    return policy


@router.patch("/tenants/{tenant_id}", response_model=TenantPolicy)
async def patch_tenant(
    tenant_id: str,
    patch: TenantPolicyUpdateRequest,
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> TenantPolicy:
    try:
        return engine.update_tenant(tenant_id, patch.model_dump(exclude_unset=True))
    except GovernanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/keys", response_model=ScopedKeyIssuedResponse, status_code=status.HTTP_201_CREATED)
async def issue_scoped_key(
    req: ScopedKeyIssueRequest,
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> ScopedKeyIssuedResponse:
    try:
        meta, raw_key = engine.issue_key(
            tenant_id=req.tenant_id,
            name=req.name,
            scopes=req.scopes,
            expires_at=req.expires_at,
        )
        return ScopedKeyIssuedResponse(**meta.model_dump(), api_key=raw_key)
    except GovernanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc


@router.get("/keys", response_model=List[ScopedAPIKeyMetadata])
async def list_scoped_keys(
    tenant_id: Optional[str] = Query(default=None),
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> List[ScopedAPIKeyMetadata]:
    return engine.key_manager.list_keys(tenant_id=tenant_id)


@router.delete("/keys/{key_id}", response_model=ScopedAPIKeyMetadata)
async def revoke_scoped_key(
    key_id: str,
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> ScopedAPIKeyMetadata:
    try:
        return engine.revoke_key(key_id)
    except GovernanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc


@router.post("/keys/verify", response_model=KeyAuthenticationResult)
async def verify_scoped_key(
    req: ScopedKeyVerifyRequest,
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> JSONResponse:
    result = engine.verify_key(req.api_key, required_scope=req.required_scope)
    return JSONResponse(status_code=result.status_code, content=result.model_dump(mode="json"))


@router.post("/evaluate", response_model=GovernanceDecision)
async def evaluate_governance_request(
    req: GovernanceEvaluateRequest,
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> JSONResponse:
    decision = engine.evaluate_request(
        tenant_id=req.tenant_id,
        requested_model=req.requested_model,
        provider=req.provider,
        category=req.category,
        estimated_cost_usd=req.estimated_cost_usd,
        estimated_tokens=req.estimated_tokens,
        prompt_preview=req.prompt_preview,
        forbid_open_weight=req.forbid_open_weight,
    )
    headers: Optional[Dict[str, str]] = None
    if decision.status_code == 429:
        headers = {"Retry-After": str(max(1, int(decision.retry_after_seconds + 0.999)))}
    return JSONResponse(status_code=decision.status_code, content=decision.model_dump(mode="json"), headers=headers)


@router.post("/spend/record", response_model=SpendSnapshot)
async def record_tenant_spend(
    req: SpendRecordRequest,
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> SpendSnapshot:
    try:
        return engine.record_spend(
            tenant_id=req.tenant_id,
            cost_usd=req.cost_usd,
            tokens=req.tokens,
            model_id=req.model_id,
            provider=req.provider,
        )
    except GovernanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.reason) from exc


@router.get("/audit", response_model=GovernanceAuditResponse)
async def get_governance_audit(
    tenant_id: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    _: Principal = Depends(current_principal),
    engine: TenantGovernanceEngine = Depends(get_governance_engine),
) -> GovernanceAuditResponse:
    entries = engine.audit_log.list_entries(tenant_id=tenant_id, limit=limit)
    chain_valid, broken_at_seq = engine.verify_audit_chain()
    return GovernanceAuditResponse(
        entries=entries,
        total=len(entries),
        chain_valid=chain_valid,
        broken_at_seq=broken_at_seq,
    )
