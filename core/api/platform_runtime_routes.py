"""
FastAPI Runtime Routes for the Keelway Unified Agent Platform (`/v1/platform`).

Exposes Phase 5 Multi-Workspace CRUD & 5-Role RBAC (`owner`, `admin`, `builder`, `operator`,
`viewer`), the `AES-256-GCM` Encrypted Secret Vault (`LocalSecretVault`), `HMAC-SHA256` Signed
Webhooks with SSRF protection (`SignedWebhookBus`), and Live Server-Sent Event (SSE) Agent &
KFlow Workflow Execution with human-only `P-10` checkpoints (`LiveExecutionStreamer`).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.eval.pricing_mirofish import PricingMiroFishSimulator, pricing_mirofish_simulator
from core.platform.execution_stream import LiveExecutionStreamer, live_execution_streamer
from core.platform.rbac_webhooks import (
    ROLE_PERMISSION_MATRIX,
    VALID_ROLES,
    SignedWebhookBus,
    WebhookValidationError,
    WorkspaceRbacController,
    signed_webhook_bus,
    workspace_rbac_controller,
)
from core.platform.vault import LocalSecretVault, VaultTamperError, local_secret_vault
from core.security.auth import Principal, current_principal
from core.security.rbac import Role

_PRINCIPAL_ROLE_MAP = {
    Role.OWNER: "owner",
    Role.ADMIN: "admin",
    Role.ENGINEER: "builder",
    Role.AUDITOR: "viewer",
    Role.PHONE: "viewer",
}
_SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}


def _can_narrow_to_role(ceiling_role: str, requested_role: str) -> bool:
    ceiling_perms = ROLE_PERMISSION_MATRIX.get(ceiling_role, frozenset())
    if "*" in ceiling_perms:
        return requested_role in ROLE_PERMISSION_MATRIX
    requested_perms = ROLE_PERMISSION_MATRIX.get(requested_role)
    return requested_perms is not None and requested_perms.issubset(ceiling_perms)


def get_secret_vault() -> LocalSecretVault:
    return local_secret_vault


def get_rbac_controller() -> WorkspaceRbacController:
    return workspace_rbac_controller


def get_webhook_bus() -> SignedWebhookBus:
    return signed_webhook_bus


def get_execution_streamer() -> LiveExecutionStreamer:
    return live_execution_streamer


def get_pricing_simulator() -> PricingMiroFishSimulator:
    return pricing_mirofish_simulator


router = APIRouter(
    prefix="/v1/platform",
    tags=["Unified Platform Runtime"],
    dependencies=[Depends(current_principal)],
)


def _slugify_workspace_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")[:64]


def _enforce_workspace_permission(
    request: Request,
    principal: Principal,
    rbac: WorkspaceRbacController,
    workspace_id: str,
    permission: str,
) -> Dict[str, Any]:
    ceiling_role = _PRINCIPAL_ROLE_MAP.get(principal.role, "viewer")
    raw_header_role = request.headers.get("x-keelway-role", "").strip().lower()
    raw_header_actor = request.headers.get("x-keelway-actor", "").strip()
    actor_id = (raw_header_actor if principal.role == Role.OWNER and raw_header_actor else principal.actor)

    if raw_header_role:
        if raw_header_role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported X-Keelway-Role '{raw_header_role}'. Expected {list(VALID_ROLES)}.",
            )
        effective_role = (
            raw_header_role
            if _can_narrow_to_role(ceiling_role, raw_header_role)
            else ceiling_role
        )
    else:
        effective_role = ceiling_role

    try:
        verdict = rbac.check_permission(workspace_id or "default", actor_id, permission, explicit_role=effective_role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not verdict["allowed"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=verdict["reason"])
    return verdict


class WorkspaceCreateRequest(BaseModel):
    id: Optional[str] = Field(default=None, max_length=128)
    workspace_id: Optional[str] = Field(default=None, max_length=128)
    name: str = Field(default="", max_length=255)
    branch: str = Field(default="main", max_length=128)
    isolation_mode: str = Field(default="seatbelt_local", max_length=64)


class RbacMemberUpsertRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    actor_id: str = Field(default="", max_length=255)
    role: str = Field(default="viewer", max_length=64)


class RbacCheckRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    actor_id: str = Field(default="local-operator", max_length=255)
    role: Optional[str] = Field(default=None, max_length=64)
    permission: str = Field(default="", max_length=128)


class SecretPutRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    name: str = Field(default="", max_length=128)
    secret_value: str = Field(default="", max_length=16_384)
    namespace: str = Field(default="byom", max_length=64)


class SecretRotateRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    secret_value: str = Field(default="", max_length=16_384)
    namespace: Optional[str] = Field(default=None, max_length=64)


class WebhookCreateRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    url: str = Field(default="", max_length=2048)
    events: List[str] = Field(default_factory=lambda: ["*"])
    description: str = Field(default="", max_length=512)
    secret: Optional[str] = Field(default=None, max_length=512)


class WebhookTestRequest(BaseModel):
    workspace_id: Optional[str] = Field(default=None, max_length=128)
    event_type: str = Field(default="webhook.test", max_length=128)
    payload: Dict[str, Any] = Field(default_factory=lambda: {"ping": "ok"})


class WebhookVerifyRequest(BaseModel):
    payload: Any
    signature: str = Field(default="", max_length=512)
    secret: str = Field(default="", max_length=512)
    timestamp: Union[str, int, float] = Field(default="")
    tolerance_seconds: int = Field(default=300, ge=1, le=86400)


class ExecutionRunStartRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    kind: str = Field(default="agent", max_length=32)
    target_id: str = Field(default="", max_length=128)
    objective: str = Field(default="", max_length=4000)
    requires_p10: bool = True
    stream: bool = False


class ExecutionP10ResolveRequest(BaseModel):
    decision: str = Field(default="", max_length=32)
    approver: str = Field(default="local-operator", max_length=128)
    reason: str = Field(default="", max_length=1000)
    workspace_id: Optional[str] = Field(default=None, max_length=128)


class PricingSimulationRequest(BaseModel):
    workspace_id: str = Field(default="default", max_length=128)
    schedule: str = Field(default="compare", max_length=64)
    seats: int = Field(default=8, ge=1, le=10_000)
    monthly_api_spend_usd: float = Field(default=1200.0, ge=0.0, le=10_000_000.0)
    run_swarm: bool = True


@router.get("/workspaces")
async def list_platform_workspaces(
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
) -> Dict[str, Any]:
    _enforce_workspace_permission(request, principal, rbac, "default", "read:all")
    workspaces = rbac.list_workspaces()
    return {"workspaces": workspaces, "total": len(workspaces)}


@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
async def create_platform_workspace(
    req: WorkspaceCreateRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
) -> Dict[str, Any]:
    target_id = (req.id or req.workspace_id or _slugify_workspace_id(req.name)).strip()
    _enforce_workspace_permission(request, principal, rbac, target_id or "default", "workspace:manage")
    try:
        return rbac.create_workspace(target_id, req.name, branch=req.branch, isolation_mode=req.isolation_mode)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/rbac/members")
async def list_rbac_members(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
) -> Dict[str, Any]:
    _enforce_workspace_permission(request, principal, rbac, workspace_id, "read:all")
    try:
        members = rbac.list_members(workspace_id=workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"workspace_id": workspace_id, "members": members, "roles": rbac.list_roles(), "total": len(members)}


@router.post("/rbac/members")
async def upsert_rbac_member(
    req: RbacMemberUpsertRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
) -> Dict[str, Any]:
    _enforce_workspace_permission(request, principal, rbac, req.workspace_id, "rbac:manage")
    try:
        return rbac.upsert_member(req.workspace_id, req.actor_id, req.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/rbac/check")
async def evaluate_rbac_permission(
    req: RbacCheckRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
) -> Dict[str, Any]:
    _enforce_workspace_permission(request, principal, rbac, req.workspace_id, "read:all")
    try:
        return rbac.check_permission(req.workspace_id, req.actor_id, req.permission, explicit_role=req.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/vault/secrets")
async def list_vault_secrets(
    request: Request,
    workspace_id: str = Query(default="default"),
    namespace: Optional[str] = Query(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    vault: LocalSecretVault = Depends(get_secret_vault),
) -> Dict[str, Any]:
    _enforce_workspace_permission(request, principal, rbac, workspace_id, "read:all")
    try:
        secrets_meta = vault.list_secrets(workspace_id=workspace_id, namespace=namespace)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"workspace_id": workspace_id, "secrets": secrets_meta, "total": len(secrets_meta)}


@router.post("/vault/secrets", status_code=status.HTTP_201_CREATED)
async def create_or_update_vault_secret(
    req: SecretPutRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    vault: LocalSecretVault = Depends(get_secret_vault),
) -> Dict[str, Any]:
    _enforce_workspace_permission(request, principal, rbac, req.workspace_id, "secrets:write")
    try:
        return vault.put_secret(req.workspace_id, req.name, req.secret_value, namespace=req.namespace)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/vault/secrets/{name}/rotate")
async def rotate_vault_secret(
    name: str,
    req: SecretRotateRequest,
    request: Request,
    workspace_id: Optional[str] = Query(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    vault: LocalSecretVault = Depends(get_secret_vault),
) -> Dict[str, Any]:
    target_ws = workspace_id or req.workspace_id
    _enforce_workspace_permission(request, principal, rbac, target_ws, "secrets:write")
    try:
        return vault.rotate_secret(target_ws, name, req.secret_value, namespace=req.namespace)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except VaultTamperError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/vault/secrets/{name}")
async def delete_vault_secret(
    name: str,
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    vault: LocalSecretVault = Depends(get_secret_vault),
) -> Dict[str, Any]:
    _enforce_workspace_permission(request, principal, rbac, workspace_id, "secrets:write")
    try:
        return vault.delete_secret(workspace_id=workspace_id, name=name)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/webhooks")
async def list_workspace_webhooks(
    request: Request,
    workspace_id: str = Query(default="default"),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    bus: SignedWebhookBus = Depends(get_webhook_bus),
) -> Dict[str, Any]:
    _enforce_workspace_permission(request, principal, rbac, workspace_id, "read:all")
    webhooks = bus.list_webhooks(workspace_id=workspace_id)
    deliveries = bus.list_deliveries(workspace_id=workspace_id)
    return {"workspace_id": workspace_id, "webhooks": webhooks, "deliveries": deliveries, "total": len(webhooks)}


@router.post("/webhooks", status_code=status.HTTP_201_CREATED)
async def register_workspace_webhook(
    req: WebhookCreateRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    bus: SignedWebhookBus = Depends(get_webhook_bus),
) -> Dict[str, Any]:
    _enforce_workspace_permission(request, principal, rbac, req.workspace_id, "webhooks:manage")
    try:
        return bus.create_webhook(req.workspace_id, req.url, req.events, description=req.description, secret=req.secret)
    except (WebhookValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/webhooks/{webhook_id}")
async def remove_workspace_webhook(
    webhook_id: str,
    request: Request,
    workspace_id: Optional[str] = Query(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    bus: SignedWebhookBus = Depends(get_webhook_bus),
) -> Dict[str, Any]:
    try:
        resolved_ws = workspace_id or bus.get_webhook_workspace(webhook_id)
    except KeyError as exc:
        _enforce_workspace_permission(request, principal, rbac, workspace_id or "default", "webhooks:manage")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    _enforce_workspace_permission(request, principal, rbac, resolved_ws, "webhooks:manage")
    try:
        return bus.delete_webhook(workspace_id=workspace_id, webhook_id=webhook_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/webhooks/{webhook_id}/test")
async def send_test_webhook_event(
    webhook_id: str,
    request: Request,
    req: Optional[WebhookTestRequest] = Body(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    bus: SignedWebhookBus = Depends(get_webhook_bus),
) -> Dict[str, Any]:
    try:
        resolved_ws = (req.workspace_id if req and req.workspace_id else None) or bus.get_webhook_workspace(webhook_id)
    except KeyError as exc:
        _enforce_workspace_permission(request, principal, rbac, "default", "webhooks:manage")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    _enforce_workspace_permission(request, principal, rbac, resolved_ws, "webhooks:manage")
    event_type = req.event_type if req is not None else "webhook.test"
    payload = req.payload if req is not None else {"ping": "ok", "webhook_id": webhook_id}
    try:
        deliveries = bus.emit_event(resolved_ws, event_type, payload, webhook_id=webhook_id, deliver_http=False)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (WebhookValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    receipt = deliveries[0]
    return {**receipt, "delivery": receipt}


@router.post("/webhooks/verify")
async def verify_webhook_signature_route(
    req: WebhookVerifyRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    bus: SignedWebhookBus = Depends(get_webhook_bus),
) -> Dict[str, Any]:
    _enforce_workspace_permission(request, principal, rbac, "default", "read:all")
    return bus.verify_signature(
        req.payload, req.signature, req.secret, req.timestamp, tolerance_seconds=req.tolerance_seconds
    )


@router.post("/execution/runs", response_model=None)
async def start_execution_run_route(
    req: ExecutionRunStartRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    streamer: LiveExecutionStreamer = Depends(get_execution_streamer),
) -> Union[Dict[str, Any], StreamingResponse]:
    required_perm = "workflows:run" if req.kind.strip().lower() == "workflow" else "agents:dispatch"
    verdict = _enforce_workspace_permission(request, principal, rbac, req.workspace_id, required_perm)
    try:
        run = streamer.start_run(
            req.workspace_id,
            req.kind,
            req.target_id,
            req.objective,
            requires_p10=req.requires_p10,
            initiator=verdict["actor_id"],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if req.stream:
        return StreamingResponse(
            streamer.iter_sse_lines(run["run_id"]),
            media_type="text/event-stream",
            headers={**_SSE_HEADERS, "X-Keelway-Run-Id": run["run_id"]},
        )
    return run


@router.get("/execution/runs/{run_id}/events", response_model=None)
async def stream_execution_run_events_route(
    run_id: str,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    streamer: LiveExecutionStreamer = Depends(get_execution_streamer),
) -> StreamingResponse:
    try:
        run = streamer.get_run(run_id)
    except KeyError as exc:
        _enforce_workspace_permission(request, principal, rbac, "default", "read:all")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    _enforce_workspace_permission(request, principal, rbac, run["workspace_id"], "read:all")
    return StreamingResponse(
        streamer.iter_sse_lines(run_id),
        media_type="text/event-stream",
        headers={**_SSE_HEADERS, "X-Keelway-Run-Id": run_id},
    )


@router.post("/execution/runs/{run_id}/p10")
async def resolve_execution_p10_route(
    run_id: str,
    req: ExecutionP10ResolveRequest,
    request: Request,
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    streamer: LiveExecutionStreamer = Depends(get_execution_streamer),
) -> Dict[str, Any]:
    try:
        run = streamer.get_run(run_id)
    except KeyError as exc:
        _enforce_workspace_permission(request, principal, rbac, req.workspace_id or "default", "p10:approve")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    verdict = _enforce_workspace_permission(request, principal, rbac, run["workspace_id"], "p10:approve")
    authenticated_actor = verdict["actor_id"]
    raw_approver = req.approver.strip()
    if principal.role != Role.OWNER:
        if raw_approver and raw_approver != "local-operator" and raw_approver != authenticated_actor:
            if raw_approver.lower().startswith(("agent:", "bot:", "service-agent:")):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="P-10 is a human-only checkpoint; autonomous agent identities cannot approve or deny P-10.",
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"P-10 approver '{raw_approver}' must match authenticated principal '{authenticated_actor}'.",
            )
        effective_approver = authenticated_actor
    else:
        effective_approver = raw_approver or authenticated_actor

    try:
        return streamer.resolve_p10(
            run_id,
            req.decision,
            approver=effective_approver,
            reason=req.reason,
            disallow_self_approval=(principal.role != Role.OWNER),
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/pricing/simulate")
async def simulate_platform_pricing_route(
    request: Request,
    req: Optional[PricingSimulationRequest] = Body(default=None),
    principal: Principal = Depends(current_principal),
    rbac: WorkspaceRbacController = Depends(get_rbac_controller),
    simulator: PricingMiroFishSimulator = Depends(get_pricing_simulator),
) -> Dict[str, Any]:
    effective_req = req or PricingSimulationRequest()
    _enforce_workspace_permission(request, principal, rbac, effective_req.workspace_id, "read:all")
    mode = effective_req.schedule.strip().lower()
    try:
        if mode == "compare":
            return await simulator.compare_schedules(
                seats=effective_req.seats,
                monthly_api_spend_usd=effective_req.monthly_api_spend_usd,
                run_swarm=effective_req.run_swarm,
            )
        return await simulator.simulate_schedule(
            mode,
            seats=effective_req.seats,
            monthly_api_spend_usd=effective_req.monthly_api_spend_usd,
            run_swarm=effective_req.run_swarm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
