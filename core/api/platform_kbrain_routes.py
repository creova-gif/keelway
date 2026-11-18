"""
FastAPI KBrain Hybrid Memory & KHub Air-Gapped Skill Registry Routes (`/v1/platform`).

Exposes Phase 10A workspace-scoped KBrain fact recording with fail-closed DLP secret rejection,
Hybrid BM25 + Character 3-Gram Cosine Similarity search, `owner`/`operator` P-10 conflict
resolution, KHub cryptographic skill catalog inspection, and air-gapped `.tar.gz` mirror verification.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import (
    _enforce_workspace_permission,
    get_rbac_controller,
)
from core.platform.kbrain_khub import (
    SQLiteKBrainEngine,
    SQLiteKHubRegistry,
    SecretLeakDetectedError,
    kbrain_engine,
    khub_registry,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import Principal, current_principal
from core.security.rbac import Role

_PERMISSION_ALIASES: Dict[str, str] = {
    "workspace:read": "read:all",
    "workspaces:read": "read:all",
    "runs:approve_p10": "p10:approve",
}


def get_kbrain_engine() -> SQLiteKBrainEngine:
    return kbrain_engine


def get_khub_registry() -> SQLiteKHubRegistry:
    return khub_registry


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
    tags=["Unified Platform KBrain Hybrid Memory & KHub Air-Gapped Registry"],
    dependencies=[Depends(current_principal)],
)


class KBrainRecordFactRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    key: str = Field(default="", max_length=256)
    statement: str = Field(default="", max_length=8192)
    scope: str = Field(default="project", max_length=64)
    provenance_uri: str = Field(default="workspace", max_length=1024)
    tags: Optional[List[str]] = Field(default=None)
    created_by: Optional[str] = Field(default=None, max_length=256)
    auto_approve: bool = Field(default=True)


class KBrainResolveFactRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    resolution: str = Field(default="approve", max_length=32)
    approver_id: Optional[str] = Field(default=None, max_length=256)


class KHubMirrorVerifyRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    skill_ids: List[str] = Field(default_factory=list)


@router.post("/kbrain/facts")
async def record_platform_kbrain_fact_route(
    payload: KBrainRecordFactRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteKBrainEngine = Depends(get_kbrain_engine),
) -> Dict[str, Any]:
    verdict = _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:dispatch")
    effective_creator = (payload.created_by or "").strip() or verdict["actor_id"]
    try:
        return engine.record_fact(
            workspace_id=payload.workspace_id,
            key=payload.key,
            statement=payload.statement,
            scope=payload.scope,
            provenance_uri=payload.provenance_uri,
            tags=payload.tags,
            created_by=effective_creator,
            auto_approve=payload.auto_approve,
        )
    except (SecretLeakDetectedError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/kbrain/search")
async def search_platform_kbrain_facts_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    query: str = Query(default=""),
    max_scope: str = Query(default="org"),
    include_conflicts: bool = Query(default=False),
    limit: int = Query(default=10),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteKBrainEngine = Depends(get_kbrain_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return engine.search_facts(
            workspace_id=workspace_id,
            query=query,
            max_scope=max_scope,
            include_conflicts=include_conflicts,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/kbrain/facts/{fact_id}/resolve")
async def resolve_platform_kbrain_fact_route(
    fact_id: str,
    payload: KBrainResolveFactRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: SQLiteKBrainEngine = Depends(get_kbrain_engine),
) -> Dict[str, Any]:
    verdict = _enforce_rbac(request, principal, rbac, payload.workspace_id, "runs:approve_p10")
    if verdict["role"] not in {"owner", "operator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"KBrain P-10 fact resolution requires 'owner' or 'operator' role; role '{verdict['role']}' is denied.",
        )

    raw_approver = (payload.approver_id or "").strip() if payload.approver_id is not None else ""
    if principal.role == Role.OWNER and raw_approver:
        effective_approver = raw_approver
    elif raw_approver and raw_approver != verdict["actor_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Approver '{raw_approver}' must match authenticated principal '{verdict['actor_id']}'.",
        )
    else:
        effective_approver = verdict["actor_id"]

    try:
        return engine.resolve_fact(
            workspace_id=payload.workspace_id,
            fact_id=fact_id,
            resolution=payload.resolution,
            approver_id=effective_approver,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/khub/skills")
async def list_platform_khub_skills_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    registry: SQLiteKHubRegistry = Depends(get_khub_registry),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return registry.list_skills(workspace_id=workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/khub/mirror/verify")
async def verify_platform_khub_mirror_route(
    payload: KHubMirrorVerifyRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    registry: SQLiteKHubRegistry = Depends(get_khub_registry),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:dispatch")
    try:
        return registry.verify_airgap_mirror(
            workspace_id=payload.workspace_id,
            skill_ids=payload.skill_ids if payload.skill_ids else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
