"""
Command gate API: the Claude Code hook submits shell commands here, a person allows or denies them,
and `keelway exec` redeems the single-use ticket before running the command in the verified sandbox.
"""

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from core.agents import gate
from core.agents.gate import (
    GATE_WINDOW_SECONDS, MAX_COMMAND_CHARS, TERMINAL, GateConflict, TicketRejected, deny_message, gate_store,
)
from core.security.auth import Principal, require
from core.security.rbac import Permission

router = APIRouter(prefix="/v1/gate", tags=["Command gate"])


class SubmitRequest(BaseModel):
    command: str = Field(..., min_length=1)
    cwd: str = Field(..., min_length=1, max_length=4096)
    workspace_root: Optional[str] = Field(None, max_length=4096)
    tool: str = Field("Bash", max_length=40)
    requester: str = Field("Claude Code", max_length=60)
    session_id: str = Field("", max_length=120)


class DecisionRequest(BaseModel):
    allow: bool


class RedeemRequest(BaseModel):
    ticket: str = Field(..., min_length=1, max_length=200)
    command: str = Field(..., min_length=1)
    cwd: str = Field(..., min_length=1, max_length=4096)


class ResultRequest(BaseModel):
    exit_code: int
    duration_ms: float = 0.0
    timed_out: bool = False
    sandbox_failure: bool = False
    backend: str = Field("", max_length=40)
    stdout_sha256: str = Field("", max_length=64)
    stderr_sha256: str = Field("", max_length=64)


class TamperRequest(BaseModel):
    tool: str = Field(..., max_length=40)
    path: str = Field(..., max_length=4096)
    cwd: str = Field(..., min_length=1, max_length=4096)
    session_id: str = Field("", max_length=120)


def _store() -> gate.GateStore:
    return gate.gate_store


def _studio_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _deny_text(req: gate.GateRequest, request: Request) -> Optional[str]:
    if req.status not in (gate.DENIED, gate.TIMED_OUT):
        return None
    key = req.deny_key or "denied"
    if key == "timed_out":
        return deny_message(key, minutes=GATE_WINDOW_SECONDS // 60, studio_url=_studio_url(request))
    if key == "sandbox":
        return deny_message(key, detail=req.sandbox.detail)
    if key == "protected":
        return deny_message(key, path=req.command.split(" ", 1)[-1])
    who = "you" if req.decided_by in (None, "local", "launch-token") else req.decided_by
    return deny_message("denied", actor=f"{who} (Keelway Studio)" if who == "you" else who)


def _view(req: gate.GateRequest, request: Request, store: gate.GateStore) -> Dict[str, Any]:
    body = req.public(store.clock())
    body["deny_code"] = gate.DENY_REASONS[req.deny_key].code if req.deny_key else None
    body["deny_message"] = _deny_text(req, request)
    return body


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def submit_gate_request(
    body: SubmitRequest, request: Request, _: Principal = Depends(require(Permission.GATE_SUBMIT)),
) -> Dict[str, Any]:
    if len(body.command) > MAX_COMMAND_CHARS:
        raise HTTPException(status_code=413, detail=deny_message("too_long", limit=MAX_COMMAND_CHARS))
    store = _store()
    verdict = await asyncio.to_thread(store.verify_cache.get, body.workspace_root or body.cwd)
    req = store.submit(
        body.command, body.cwd, workspace_root=body.workspace_root, requester=body.requester, tool=body.tool,
        session_id=body.session_id, sandbox=verdict,
    )
    return _view(req, request, store)


@router.get("/requests/{request_id}/wait")
async def wait_for_decision(
    request_id: str, request: Request, timeout: float = Query(25.0, ge=0, le=60),
    _: Principal = Depends(require(Permission.GATE_SUBMIT)),
) -> Dict[str, Any]:
    """Long-poll until the request is decided or times out; the hook calls this until status is terminal."""
    store = _store()
    deadline = store.clock() + timeout
    while True:
        req = store.get(request_id)
        if req is None:
            raise HTTPException(status_code=404, detail="Unknown gate request (Keelway may have restarted).")
        if req.status in TERMINAL or store.clock() >= deadline:
            body = _view(req, request, store)
            body["ticket"] = store.ticket(req)
            return body
        await asyncio.sleep(0.2)


@router.get("/pending")
async def list_pending(request: Request, _: Principal = Depends(require(Permission.APPROVE_AGENT_STEPS))) -> Dict[str, Any]:
    store = _store()
    pending = [_view(r, request, store) for r in store.pending()]
    return {"requests": pending, "waiting": len(pending)}


@router.get("/history")
async def list_history(
    request: Request, limit: int = Query(50, ge=1, le=500), _: Principal = Depends(require(Permission.VIEW_AUDIT_LOGS)),
) -> Dict[str, Any]:
    store = _store()
    return {"requests": [_view(r, request, store) for r in store.history(limit)]}


@router.post("/requests/{request_id}/decision")
async def decide(
    request_id: str, body: DecisionRequest, request: Request,
    principal: Principal = Depends(require(Permission.APPROVE_AGENT_STEPS)),
) -> Dict[str, Any]:
    store = _store()
    try:
        req = store.decide(request_id, body.allow, principal.actor)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown gate request.")
    except GateConflict as exc:
        raise HTTPException(status_code=409, detail=f"Already decided: {exc}.")
    return _view(req, request, store)


@router.post("/deny-waiting")
async def deny_waiting(request: Request, principal: Principal = Depends(require(Permission.APPROVE_AGENT_STEPS))) -> Dict[str, Any]:
    store = _store()
    denied = store.deny_waiting(principal.actor)
    return {"denied": [r.id for r in denied], "count": len(denied)}


@router.post("/redeem")
async def redeem_ticket(
    body: RedeemRequest, request: Request, _: Principal = Depends(require(Permission.GATE_SUBMIT)),
) -> Dict[str, Any]:
    store = _store()
    try:
        req = store.redeem(body.ticket, body.command, body.cwd)
    except TicketRejected as exc:
        raise HTTPException(status_code=403, detail=deny_message("ticket", problem=exc.problem))
    verdict = await asyncio.to_thread(store.verify_cache.get, req.workspace_root)
    if not verdict.ok:
        result = {"exit_code": 126, "sandbox_failure": True, "refused": True, "detail": verdict.detail}
        store.record_result(req.id, result)
        raise HTTPException(status_code=409, detail=deny_message("sandbox", detail=verdict.detail))
    return {"id": req.id, "cwd": req.cwd, "workspace_root": req.workspace_root, "sandbox": verdict.to_dict()}


@router.post("/requests/{request_id}/result")
async def record_result(
    request_id: str, body: ResultRequest, request: Request, _: Principal = Depends(require(Permission.GATE_SUBMIT)),
) -> Dict[str, Any]:
    store = _store()
    try:
        req = store.record_result(request_id, body.model_dump())
    except KeyError:
        raise HTTPException(status_code=404, detail="No redeemed gate request with that id.")
    except GateConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return _view(req, request, store)


@router.post("/tamper", status_code=status.HTTP_201_CREATED)
async def record_tamper(
    body: TamperRequest, request: Request, _: Principal = Depends(require(Permission.GATE_SUBMIT)),
) -> Dict[str, Any]:
    store = _store()
    req = store.record_tamper(body.tool, body.path, body.cwd, body.session_id)
    return _view(req, request, store)
