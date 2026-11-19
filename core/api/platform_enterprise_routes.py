"""
FastAPI Enterprise Identity (OIDC/SAML & SCIM 2.0), Dual-Human P-10 Quorum,
Tamper-Evident SIEM Export & Prometheus/OTLP Observability Routes (`/v1/platform`).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from core.api.platform_runtime_routes import (
    _enforce_workspace_permission,
    get_rbac_controller,
)
from core.platform.enterprise_identity_siem import (
    EnterpriseIdentitySiemManager,
    enterprise_identity_siem_manager,
)
from core.platform.rbac_webhooks import WorkspaceRbacController, workspace_rbac_controller
from core.security.auth import Principal, current_principal
from core.security.rbac import Role

_PERMISSION_ALIASES: Dict[str, str] = {
    "workspace:read": "read:all",
    "workspaces:read": "read:all",
    "runs:approve_p10": "p10:approve",
}


def get_enterprise_identity_siem_manager() -> EnterpriseIdentitySiemManager:
    return enterprise_identity_siem_manager


def _enforce_rbac(
    request: Request,
    principal: Principal,
    rbac: WorkspaceRbacController,
    workspace_id: str,
    permission: str,
) -> Dict[str, Any]:
    mapped = _PERMISSION_ALIASES.get(permission, permission)
    return _enforce_workspace_permission(request, principal, rbac, workspace_id, mapped)


@contextmanager
def _synced_rbac_controller(
    rbac: WorkspaceRbacController, manager: EnterpriseIdentitySiemManager
) -> Iterator[WorkspaceRbacController]:
    if rbac is workspace_rbac_controller and str(rbac._db_path) != str(manager.db_path):
        transient = WorkspaceRbacController(db_path=manager.db_path)
        try:
            yield transient
        finally:
            transient.close()
    else:
        yield rbac


router = APIRouter(
    prefix="/v1/platform",
    tags=["Unified Platform Enterprise Identity, P-10 Quorum, SIEM & Observability"],
    dependencies=[Depends(current_principal)],
)


class OidcConfigureRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    issuer_url: Optional[str] = Field(default=None, max_length=2048)
    issuer: Optional[str] = Field(default=None, max_length=2048)
    client_id: str = Field(default="", max_length=256)
    signing_secret: Optional[str] = Field(default=None, max_length=4096)
    jwks_uri: Optional[str] = Field(default=None, max_length=2048)
    jwks_json: Optional[Any] = Field(default=None)
    group_role_mapping: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class OidcExchangeRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    id_token: str = Field(default="", max_length=16_384)


class ScimUserProvisionRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    userName: Optional[str] = Field(default=None, max_length=255)
    user_name: Optional[str] = Field(default=None, max_length=255)
    displayName: Optional[str] = Field(default=None, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=255)
    name: Optional[Dict[str, Any]] = Field(default=None)
    emails: Optional[List[Any]] = Field(default=None)
    groups: Optional[List[Any]] = Field(default=None)
    active: bool = True


class ScimUserPatchRequest(BaseModel):
    workspace_id: Optional[str] = Field(default=None, max_length=128)
    active: Optional[bool] = None
    groups: Optional[List[Any]] = None
    displayName: Optional[str] = Field(default=None, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=255)
    Operations: Optional[List[Dict[str, Any]]] = None


class P10QuorumApproveRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    proposal_id: str = Field(default="", max_length=256)
    approver_id: Optional[str] = Field(default=None, max_length=256)
    initiator_id: str = Field(default="", max_length=256)
    required_approvals: int = Field(default=2)
    reason: str = Field(default="", max_length=2000)


def _coerce_scim_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    return None


def _extract_scim_patch_fields(
    payload: ScimUserPatchRequest,
) -> tuple[Optional[bool], Optional[List[Any]], Optional[str], List[str]]:
    active = payload.active
    groups = payload.groups
    display = payload.displayName if payload.displayName is not None else payload.display_name
    ignored: List[str] = []
    name_parts: Dict[str, str] = {}
    for op in payload.Operations or []:
        if not isinstance(op, dict):
            ignored.append("<malformed-op>")
            continue
        verb = str(op.get("op") or "replace").strip().lower()
        path = str(op.get("path") or "").strip().lower()
        val = op.get("value")
        if verb == "remove":
            if path == "groups":
                groups = []
            elif path in {"active", "displayname"}:
                ignored.append(f"{verb}:{path} (required attribute cannot be removed)")
            else:
                ignored.append(f"{verb}:{path or '<bulk>'}")
            continue
        if verb not in {"add", "replace"}:
            ignored.append(f"{verb}:{path or '<bulk>'}")
            continue
        if path == "active":
            coerced = _coerce_scim_bool(val)
            active = coerced if coerced is not None else active
            if coerced is None:
                ignored.append(f"{verb}:active (non-boolean value ignored)")
        elif path == "displayname" and isinstance(val, str):
            display = val
        elif path == "groups" and isinstance(val, list):
            groups = val
        elif path in {"name.givenname", "name.familyname"} and isinstance(val, str):
            name_parts[path] = val.strip()
        elif not path and isinstance(val, dict):
            if "active" in val:
                coerced = _coerce_scim_bool(val["active"])
                if coerced is not None:
                    active = coerced
                else:
                    ignored.append(f"{verb}:active (non-boolean value ignored)")
            if isinstance(val.get("displayName"), str):
                display = val["displayName"]
            if isinstance(val.get("groups"), list):
                groups = val["groups"]
            name_val = val.get("name")
            if isinstance(name_val, dict):
                if isinstance(name_val.get("givenName"), str):
                    name_parts["name.givenname"] = name_val["givenName"].strip()
                if isinstance(name_val.get("familyName"), str):
                    name_parts["name.familyname"] = name_val["familyName"].strip()
            handled = {"active", "displayName", "groups", "name"}
            ignored.extend(f"{verb}:{k}" for k in val if k not in handled)
        else:
            ignored.append(f"{verb}:{path or '<bulk>'}")
    if display is None and name_parts:
        composed = " ".join(p for p in (name_parts.get("name.givenname"), name_parts.get("name.familyname")) if p).strip()
        if composed:
            display = composed
    return active, groups, display, ignored


@router.get("/enterprise/oidc")
async def get_enterprise_oidc_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    manager: EnterpriseIdentitySiemManager = Depends(get_enterprise_identity_siem_manager),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return manager.get_oidc(workspace_id=workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/enterprise/oidc")
async def configure_enterprise_oidc_route(
    payload: OidcConfigureRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    manager: EnterpriseIdentitySiemManager = Depends(get_enterprise_identity_siem_manager),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "rbac:manage")
    resolved_issuer = payload.issuer_url if payload.issuer_url is not None else (payload.issuer or "")
    try:
        return manager.configure_oidc(
            workspace_id=payload.workspace_id,
            issuer_url=resolved_issuer,
            client_id=payload.client_id,
            signing_secret=payload.signing_secret,
            group_role_mapping=payload.group_role_mapping,
            enabled=payload.enabled,
            jwks_uri=payload.jwks_uri,
            jwks_json=payload.jwks_json,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/enterprise/oidc/exchange")
async def exchange_enterprise_oidc_token_route(
    payload: OidcExchangeRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    manager: EnterpriseIdentitySiemManager = Depends(get_enterprise_identity_siem_manager),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, payload.workspace_id, "workspace:read")
    try:
        return manager.exchange_oidc_token(workspace_id=payload.workspace_id, id_token=payload.id_token)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/enterprise/scim/v2/Users")
async def list_enterprise_scim_users_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    filter: Optional[str] = Query(default=None),
    startIndex: int = Query(default=1),
    count: Optional[int] = Query(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    manager: EnterpriseIdentitySiemManager = Depends(get_enterprise_identity_siem_manager),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return manager.list_scim_users(
            workspace_id=workspace_id, filter=filter, start_index=startIndex, count=count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/enterprise/scim/v2/Users")
async def provision_enterprise_scim_user_route(
    payload: ScimUserProvisionRequest,
    request: Request,
    workspace_id: Optional[str] = Query(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    manager: EnterpriseIdentitySiemManager = Depends(get_enterprise_identity_siem_manager),
) -> Dict[str, Any]:
    target_ws = workspace_id or payload.workspace_id or "default"
    _enforce_rbac(request, principal, rbac, target_ws, "rbac:manage")
    resolved_user = payload.userName if payload.userName is not None else (payload.user_name or "")
    resolved_display = payload.displayName if payload.displayName is not None else (payload.display_name or "")
    if not resolved_display and isinstance(payload.name, dict):
        resolved_display = " ".join(
            p for p in (str(payload.name.get("givenName") or "").strip(), str(payload.name.get("familyName") or "").strip()) if p
        ).strip()
    try:
        with _synced_rbac_controller(rbac, manager) as effective_rbac:
            return manager.provision_scim_user(
                workspace_id=target_ws,
                user_name=resolved_user,
                display_name=resolved_display,
                groups=payload.groups,
                active=payload.active,
                rbac=effective_rbac,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/enterprise/scim/v2/Users/{scim_user_id}")
async def patch_enterprise_scim_user_route(
    scim_user_id: str,
    payload: ScimUserPatchRequest,
    request: Request,
    workspace_id: Optional[str] = Query(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    manager: EnterpriseIdentitySiemManager = Depends(get_enterprise_identity_siem_manager),
) -> Dict[str, Any]:
    target_ws = workspace_id or payload.workspace_id or "default"
    _enforce_rbac(request, principal, rbac, target_ws, "rbac:manage")
    next_active, next_groups, next_display, ignored_ops = _extract_scim_patch_fields(payload)
    try:
        with _synced_rbac_controller(rbac, manager) as effective_rbac:
            resource = manager.patch_scim_user(
                workspace_id=target_ws,
                scim_user_id=scim_user_id,
                active=next_active,
                groups=next_groups,
                display_name=next_display,
                rbac=effective_rbac,
            )
            if ignored_ops:
                resource["warnings"] = {"ignored_operations": ignored_ops}
            return resource
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/enterprise/p10-quorum/approve")
async def approve_enterprise_p10_quorum_route(
    payload: P10QuorumApproveRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    manager: EnterpriseIdentitySiemManager = Depends(get_enterprise_identity_siem_manager),
) -> Dict[str, Any]:
    verdict = _enforce_rbac(request, principal, rbac, payload.workspace_id, "runs:approve_p10")
    raw_approver = (payload.approver_id or "").strip() if payload.approver_id is not None else ""
    if principal.role == Role.OWNER:
        effective_approver = raw_approver if payload.approver_id is not None else verdict["actor_id"]
    else:
        if raw_approver and raw_approver != verdict["actor_id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"P-10 quorum approver '{raw_approver}' must match authenticated principal '{verdict['actor_id']}'.",
            )
        effective_approver = verdict["actor_id"]

    try:
        return manager.approve_p10_quorum(
            workspace_id=payload.workspace_id,
            proposal_id=payload.proposal_id,
            approver_id=effective_approver,
            approver_role=verdict["role"],
            initiator_id=payload.initiator_id,
            required_approvals=payload.required_approvals,
            reason=payload.reason,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/enterprise/p10-quorum/{proposal_id}")
async def get_enterprise_p10_quorum_route(
    proposal_id: str,
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    manager: EnterpriseIdentitySiemManager = Depends(get_enterprise_identity_siem_manager),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return manager.get_p10_quorum(workspace_id=workspace_id, proposal_id=proposal_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/enterprise/siem/export")
async def export_enterprise_siem_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    format: str = Query(default="ocsf"),
    limit: int = Query(default=50),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    manager: EnterpriseIdentitySiemManager = Depends(get_enterprise_identity_siem_manager),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return manager.export_siem(workspace_id=workspace_id, export_format=format, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/observability/metrics")
async def get_platform_observability_metrics_route(
    request: Request,
    workspace_id: str = Query(default="default"),
    format: str = Query(default="otlp_json"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    manager: EnterpriseIdentitySiemManager = Depends(get_enterprise_identity_siem_manager),
) -> Dict[str, Any]:
    _enforce_rbac(request, principal, rbac, workspace_id, "workspace:read")
    try:
        return manager.get_observability_metrics(workspace_id=workspace_id, metrics_format=format)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
