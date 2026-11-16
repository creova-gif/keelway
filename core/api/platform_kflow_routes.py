"""
FastAPI KFlow Topological DAG, KSpaces CRDT Sync & CycloneDX SBOM Routes (`/v1/platform`).

Exposes Phase 8 workspace-governed KFlow multi-wave DAG execution with P-10 RBAC enforcement,
KSpaces LWW-Element-Set CRDT synchronization with pre-storage DLP secret scrubbing, and live
cryptographically verified CycloneDX 1.5 SBOM provenance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import (
    _enforce_workspace_permission,
    get_rbac_controller,
)
from core.platform.kflow_crdt import (
    KFlowCycleError,
    KFlowDagEngine,
    KSpacesCrdtEngine,
    kflow_dag_engine,
    kspaces_crdt_engine,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import Principal, current_principal
from core.security.sbom import SBOMGenerator, SBOMVerifier

_PERMISSION_ALIASES: Dict[str, str] = {
    "workspace:read": "read:all",
    "workspaces:read": "read:all",
    "runs:approve_p10": "p10:approve",
}


def get_kflow_engine() -> KFlowDagEngine:
    return kflow_dag_engine


def get_kspaces_crdt_engine() -> KSpacesCrdtEngine:
    return kspaces_crdt_engine


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
    tags=["Unified Platform KFlow, KSpaces CRDT & SBOM"],
    dependencies=[Depends(current_principal)],
)


class KFlowExecuteRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    workflow_id: str = Field(default="", max_length=128)
    nodes: List[Dict[str, Any]] = Field(default_factory=list)
    trigger: str = Field(default="manual", max_length=128)
    token_budget: int = Field(default=25000)
    approved_node_ids: Optional[List[str]] = Field(default=None)


class KSpacesSyncRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    peer_id: str = Field(default="", max_length=128)
    operations: List[Dict[str, Any]] = Field(default_factory=list)


@router.post("/automation/workflows/execute")
async def execute_platform_kflow_dag_route(
    payload: KFlowExecuteRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: KFlowDagEngine = Depends(get_kflow_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workflows:run")
    if payload.approved_node_ids and any(str(nid).strip() for nid in payload.approved_node_ids):
        _enforce_rbac(request, principal, rbac, payload.workspace_id, "runs:approve_p10")
    try:
        return engine.execute_dag(
            workspace_id=payload.workspace_id,
            workflow_id=payload.workflow_id,
            nodes=payload.nodes,
            trigger=payload.trigger,
            token_budget=payload.token_budget,
            approved_node_ids=payload.approved_node_ids,
        )
    except (KFlowCycleError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/automation/runs")
async def list_platform_kflow_runs_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    workflow_id: Optional[str] = Query(default=None),
    limit: int = Query(default=25),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    engine: KFlowDagEngine = Depends(get_kflow_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return engine.list_runs(workspace_id=workspace_id, workflow_id=workflow_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/kspaces/sync")
async def sync_platform_kspaces_crdt_route(
    payload: KSpacesSyncRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    crdt: KSpacesCrdtEngine = Depends(get_kspaces_crdt_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "agents:dispatch")
    try:
        return crdt.apply_ops(
            workspace_id=payload.workspace_id,
            peer_id=payload.peer_id,
            operations=payload.operations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/kspaces/state")
async def get_platform_kspaces_crdt_state_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    namespace: Optional[str] = Query(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    crdt: KSpacesCrdtEngine = Depends(get_kspaces_crdt_engine),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return crdt.get_state(workspace_id=workspace_id, namespace=namespace)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/security/sbom")
async def get_platform_security_sbom_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    manifest_dict = SBOMGenerator.generate(repo_root=Path(__file__).resolve().parents[2]).to_dict()
    valid, v_status, _details = SBOMVerifier.verify(manifest_dict)
    return {
        "workspace_id": workspace_id,
        "verified": valid,
        "verification_status": v_status,
        "bom_format": manifest_dict["bom_format"],
        "spec_version": manifest_dict["spec_version"],
        "serial_number": manifest_dict["serial_number"],
        "component_count": len(manifest_dict["components"]),
        "root_digest_sha256": manifest_dict["root_digest_sha256"],
        "provenance_signature": manifest_dict["provenance_signature"],
        "manifest": manifest_dict,
    }
