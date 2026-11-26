"""Messaging endpoints: channel status, a test send, the WhatsApp webhook, and remote approval decisions."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from core.api import routes
from core.api.approval_relay import ApprovalRelay, RelayBlocked, fingerprint
from core.models.gateway import gateway
from core.security.auth import Principal, current_principal, record_audit, require
from core.security.rbac import Permission, Role

logger = logging.getLogger("keelway.messaging")
router = APIRouter(prefix="/v1/messaging", tags=["Messaging"])
relay = ApprovalRelay(air_gapped=lambda: gateway.air_gap.enabled)


async def apply_remote_decision(nonce: str, approved: bool, actor: str) -> str:
    """Approve or deny only the exact tool call the message was sent for, if it is still pending."""
    claimed = relay.claim(nonce)
    principal = Principal(actor=actor, role=Role.ADMIN)
    if not claimed:
        await record_audit(principal, "remote_approval", "expired or unknown request", False)
        return "This request has expired."
    task_id, digest = claimed
    agent = routes._active_agent_loops.get(task_id)
    if not agent or not agent.pending_approval or fingerprint(agent.pending_approval) != digest:
        await record_audit(principal, "remote_approval", f"{task_id} no longer pending", False)
        return "Already handled or no longer pending."
    tool = agent.pending_approval["tool_name"]
    await record_audit(principal, "remote_approval", f"{task_id}:{tool}:{'approve' if approved else 'deny'}", True)
    result = await agent.approve_pending(approved=approved)
    await routes._publish_agent(agent)
    if result.get("status") == "error":
        return f"Approved, but {tool} failed for {task_id}: {str(result.get('error', ''))[:120]}"
    return f"{'Approved' if approved else 'Denied'}: {tool} for {task_id}."


relay.on_decision = apply_remote_decision


@router.get("/status", dependencies=[Depends(current_principal)])
async def messaging_status() -> Dict[str, Any]:
    return {
        "channels": relay.channels(),
        "air_gapped": gateway.air_gap.enabled,
        "blocked": gateway.air_gap.enabled,
        "whatsapp_replies": relay.config.whatsapp_replies,
        "telegram_buttons": relay.config.telegram_buttons,
    }


@router.post("/test", dependencies=[Depends(require(Permission.APPROVE_TIER3))])
async def messaging_test(principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
    try:
        result = await relay.send_test()
    except RelayBlocked as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    delivered = [name for name, r in result["sent"].items() if r.get("ok")]
    await record_audit(principal, "messaging_test", ",".join(result["sent"]), bool(delivered))
    if not delivered:
        raise HTTPException(status_code=502, detail={"message": "No channel accepted the test message.", **result})
    return result


@router.get("/whatsapp/webhook", response_class=PlainTextResponse)
async def whatsapp_verify(
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
) -> str:
    expected = relay.config.whatsapp_verify_token
    if mode != "subscribe" or not expected or token != expected:
        raise HTTPException(status_code=403, detail="Verification failed.")
    return challenge


@router.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request) -> Dict[str, Any]:
    raw = await request.body()
    if not relay.whatsapp_signature_ok(raw, request.headers.get("x-hub-signature-256")):
        raise HTTPException(status_code=401, detail="Bad signature.")
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON.") from exc
    return {"outcomes": await relay.handle_whatsapp(payload)}


async def notify_if_paused(step_result: Dict[str, Any]) -> None:
    """Best effort: a send failure or air-gap never blocks the agent; the Studio card is always there."""
    if step_result.get("status") != "paused_for_approval" or not relay.channels():
        return
    try:
        await relay.notify_pending(step_result["pending"])
    except RelayBlocked:
        pass
    except Exception as e:
        logger.warning("Approval notification failed: %s", type(e).__name__)
