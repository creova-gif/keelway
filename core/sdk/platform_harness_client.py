"""
Keelway Client SDK — Phase 18 Universal Coding-Agent Co-Harness
+ Parallel Worktree CI Gate Mixins (`client.platform`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import quote

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient

_VALID_AGENT_HOSTS = ("claude_code", "cursor", "codex_cli")
_VALID_HOOK_MODES = ("enforce", "audit_only")
_VALID_TICKET_STATUSES = ("PENDING", "APPROVED", "DENIED", "CONSUMED")
_VALID_TICKET_DECISIONS = ("APPROVED", "DENIED")


def _clean_non_empty(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return clean


def _seg(value: str, field_name: str) -> str:
    return quote(_clean_non_empty(value, field_name), safe="")


def _clean_ws(workspace_id: str) -> str:
    return str(workspace_id or "default").strip() or "default"


def _validate_agent_host(agent_host: str) -> str:
    clean = str(agent_host or "").strip()
    if clean not in _VALID_AGENT_HOSTS:
        raise ValueError(f"agent_host must be one of {list(_VALID_AGENT_HOSTS)}.")
    return clean


def _render_hook_body(agent_host: str, mode: str, workspace_id: str) -> Dict[str, Any]:
    clean_mode = str(mode or "").strip()
    if clean_mode not in _VALID_HOOK_MODES:
        raise ValueError(f"mode must be one of {list(_VALID_HOOK_MODES)}.")
    return {"workspace_id": _clean_ws(workspace_id), "agent_host": _validate_agent_host(agent_host), "mode": clean_mode}


def _intercept_body(command: str, tool_name: str, agent_host: str, ticket_id: Optional[str], workspace_id: str) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "workspace_id": _clean_ws(workspace_id),
        "agent_host": _validate_agent_host(agent_host),
        "tool_name": _clean_non_empty(tool_name, "tool_name"),
        "command": _clean_non_empty(command, "command"),
    }
    if ticket_id is not None and str(ticket_id).strip():
        body["ticket_id"] = str(ticket_id).strip()
    return body


def _tickets_query_params(workspace_id: str, status: Optional[str], limit: int) -> Dict[str, Any]:
    if isinstance(limit, bool) or int(limit) < 1:
        raise ValueError("limit must be >= 1.")
    params: Dict[str, Any] = {"workspace_id": _clean_ws(workspace_id), "limit": int(limit)}
    if status is not None and str(status).strip():
        clean_status = str(status).strip()
        if clean_status not in _VALID_TICKET_STATUSES:
            raise ValueError(f"status must be one of {list(_VALID_TICKET_STATUSES)}.")
        params["status"] = clean_status
    return params


def _decide_ticket_body(decision: str, reviewer: str, reason: str, workspace_id: str) -> Dict[str, Any]:
    clean_decision = str(decision or "").strip()
    if clean_decision not in _VALID_TICKET_DECISIONS:
        raise ValueError(f"decision must be one of {list(_VALID_TICKET_DECISIONS)}.")
    return {
        "workspace_id": _clean_ws(workspace_id),
        "decision": clean_decision,
        "reviewer": _clean_non_empty(reviewer, "reviewer"),
        "reason": _clean_non_empty(reason, "reason"),
    }


def _evaluate_ci_gate_body(
    workspace_id: str, workflow_name: str, diff_summary: str, min_eval_score: float, candidates: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    if isinstance(min_eval_score, bool) or not (0.0 <= float(min_eval_score) <= 1.0):
        raise ValueError("min_eval_score must be between 0.0 and 1.0.")
    body: Dict[str, Any] = {
        "workspace_id": _clean_ws(workspace_id),
        "workflow_name": _clean_non_empty(workflow_name, "workflow_name"),
        "diff_summary": _clean_non_empty(diff_summary, "diff_summary"),
        "min_eval_score": float(min_eval_score),
    }
    if candidates is not None:
        if not isinstance(candidates, list):
            raise ValueError("candidates must be a list of dicts.")
        body["candidates"] = [dict(candidate) for candidate in candidates]
    return body


class AsyncPlatformHarnessMixin:
    """Asynchronous Phase 18 Coding-Agent Co-Harness & Worktree CI Gate methods."""

    _client: "AsyncKeelwayClient"

    async def render_agent_hook_config(
        self, *, agent_host: str = "claude_code", mode: str = "enforce", workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/platform/harness/hooks/render", json=_render_hook_body(agent_host, mode, workspace_id))

    async def intercept_agent_tool_call(
        self,
        *,
        command: str = "git push origin main",
        tool_name: str = "Bash",
        agent_host: str = "claude_code",
        ticket_id: Optional[str] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST", "/v1/platform/harness/intercept", json=_intercept_body(command, tool_name, agent_host, ticket_id, workspace_id)
        )

    async def list_harness_tickets(
        self, *, workspace_id: str = "default", status: Optional[str] = None, limit: int = 25
    ) -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/harness/tickets", params=_tickets_query_params(workspace_id, status, limit))

    async def decide_harness_ticket(
        self,
        ticket_id: str,
        decision: str = "APPROVED",
        *,
        reviewer: str = "lead-engineer",
        reason: str = "Verified safe workspace scope",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        body = _decide_ticket_body(decision, reviewer, reason, workspace_id)
        return await self._client._req("POST", f"/v1/platform/harness/tickets/{_seg(ticket_id, 'ticket_id')}/decide", json=body)

    async def evaluate_worktree_ci_gate(
        self,
        *,
        workspace_id: str = "default",
        workflow_name: str = "pr-worktree-arena",
        diff_summary: str = "Refactor retry backoff & add unit test in core/platform/",
        min_eval_score: float = 0.85,
        candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        body = _evaluate_ci_gate_body(workspace_id, workflow_name, diff_summary, min_eval_score, candidates)
        return await self._client._req("POST", "/v1/platform/harness/ci-gate/evaluate", json=body)

    async def list_worktree_ci_gate_runs(self, *, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/harness/ci-gate/runs", params=_tickets_query_params(workspace_id, None, limit))


class SyncPlatformHarnessMixin:
    """Synchronous Phase 18 Coding-Agent Co-Harness & Worktree CI Gate methods."""

    _client: "KeelwayClient"

    def render_agent_hook_config(
        self, *, agent_host: str = "claude_code", mode: str = "enforce", workspace_id: str = "default"
    ) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/platform/harness/hooks/render", json=_render_hook_body(agent_host, mode, workspace_id))

    def intercept_agent_tool_call(
        self,
        *,
        command: str = "git push origin main",
        tool_name: str = "Bash",
        agent_host: str = "claude_code",
        ticket_id: Optional[str] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST", "/v1/platform/harness/intercept", json=_intercept_body(command, tool_name, agent_host, ticket_id, workspace_id)
        )

    def list_harness_tickets(
        self, *, workspace_id: str = "default", status: Optional[str] = None, limit: int = 25
    ) -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/harness/tickets", params=_tickets_query_params(workspace_id, status, limit))

    def decide_harness_ticket(
        self,
        ticket_id: str,
        decision: str = "APPROVED",
        *,
        reviewer: str = "lead-engineer",
        reason: str = "Verified safe workspace scope",
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        body = _decide_ticket_body(decision, reviewer, reason, workspace_id)
        return self._client._req("POST", f"/v1/platform/harness/tickets/{_seg(ticket_id, 'ticket_id')}/decide", json=body)

    def evaluate_worktree_ci_gate(
        self,
        *,
        workspace_id: str = "default",
        workflow_name: str = "pr-worktree-arena",
        diff_summary: str = "Refactor retry backoff & add unit test in core/platform/",
        min_eval_score: float = 0.85,
        candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        body = _evaluate_ci_gate_body(workspace_id, workflow_name, diff_summary, min_eval_score, candidates)
        return self._client._req("POST", "/v1/platform/harness/ci-gate/evaluate", json=body)

    def list_worktree_ci_gate_runs(self, *, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/harness/ci-gate/runs", params=_tickets_query_params(workspace_id, None, limit))


PlatformHarnessMixin = SyncPlatformHarnessMixin
