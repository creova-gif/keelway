"""
Keelway Client SDK — Phase 14 Live Step-Through Debugger, Conditional Breakpoints,
DLP-Guarded State Mutation & 4D Routing CodeLens Mixins (`client.platform`).

Defines `AsyncPlatformDebuggerMixin` and `SyncPlatformDebuggerMixin` inherited by
`AsyncPlatformRuntimeMixin` and `SyncPlatformRuntimeMixin` for 100% sync + async parity across
`/v1/platform/debugger/*`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import quote

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient

_VALID_CONDITION_TYPES = (
    "always",
    "cost_usd_gt",
    "hybrid_score_lt",
    "before_shell_tool",
    "before_p10_gate",
    "line_match",
)
_VALID_STEP_ACTIONS = ("step_over", "step_into", "continue", "mutate_state")


def _debugger_seg(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return quote(clean, safe="")


def _debugger_breakpoint_body(
    node_id: Optional[str],
    workspace_id: str,
    workflow_id: str,
    file_path: str,
    line_number: Optional[int],
    condition_type: str,
    threshold: Optional[float],
    enabled: bool,
    label: Optional[str],
) -> Dict[str, Any]:
    clean_wf = str(workflow_id or "").strip()
    if not clean_wf:
        raise ValueError("workflow_id must be non-empty.")
    clean_cond = str(condition_type or "").strip()
    if clean_cond not in _VALID_CONDITION_TYPES:
        raise ValueError(f"condition_type must be one of {list(_VALID_CONDITION_TYPES)}.")
    body: Dict[str, Any] = {
        "workspace_id": workspace_id,
        "workflow_id": clean_wf,
        "file_path": str(file_path or "").strip() or "workflows/refund_agent.py",
        "condition_type": clean_cond,
        "enabled": bool(enabled),
    }
    if node_id is not None and str(node_id).strip():
        body["node_id"] = str(node_id).strip()
    if line_number is not None:
        if isinstance(line_number, bool) or int(line_number) < 1:
            raise ValueError("line_number must be >= 1.")
        body["line_number"] = int(line_number)
    if threshold is not None:
        if isinstance(threshold, bool):
            raise ValueError("threshold must be numeric.")
        body["threshold"] = float(threshold)
    if label is not None and str(label).strip():
        body["label"] = str(label).strip()
    return body


def _debugger_list_breakpoints_params(workspace_id: str, workflow_id: Optional[str]) -> Dict[str, Any]:
    params: Dict[str, Any] = {"workspace_id": workspace_id}
    if workflow_id is not None and str(workflow_id).strip():
        params["workflow_id"] = str(workflow_id).strip()
    return params


def _debugger_start_session_body(
    workflow_id: str,
    workspace_id: str,
    steps: Optional[List[Dict[str, Any]]],
    initial_state: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    clean_wf = str(workflow_id or "").strip()
    if not clean_wf:
        raise ValueError("workflow_id must be non-empty.")
    body: Dict[str, Any] = {"workspace_id": workspace_id, "workflow_id": clean_wf}
    if steps is not None:
        body["steps"] = [dict(step) for step in steps]
    if initial_state is not None:
        body["initial_state"] = dict(initial_state)
    return body


def _debugger_list_sessions_params(workspace_id: str, limit: int) -> Dict[str, Any]:
    if isinstance(limit, bool) or int(limit) < 1:
        raise ValueError("limit must be >= 1.")
    return {"workspace_id": workspace_id, "limit": int(limit)}


def _debugger_step_body(action: str, workspace_id: str, state_patch: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    clean_action = str(action or "").strip()
    if clean_action not in _VALID_STEP_ACTIONS:
        raise ValueError(f"action must be one of {list(_VALID_STEP_ACTIONS)}.")
    body: Dict[str, Any] = {"workspace_id": workspace_id, "action": clean_action}
    if state_patch is not None:
        body["state_patch"] = dict(state_patch)
    return body


def _debugger_codelens_params(
    workspace_id: str, workflow_id: Optional[str], file_path: Optional[str], source_code: Optional[str]
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"workspace_id": workspace_id}
    if workflow_id is not None and str(workflow_id).strip():
        params["workflow_id"] = str(workflow_id).strip()
    if file_path is not None and str(file_path).strip():
        params["file_path"] = str(file_path).strip()
    if source_code is not None:
        params["source_code"] = source_code
    return params


class AsyncPlatformDebuggerMixin:
    """Asynchronous Phase 14 Step-Through Debugger, Conditional Breakpoints & 4D CodeLens methods."""

    _client: "AsyncKeelwayClient"

    async def set_breakpoint(
        self,
        node_id: Optional[str] = None,
        *,
        workspace_id: str = "default",
        workflow_id: str = "WF-STUDIO-01",
        file_path: str = "workflows/refund_agent.py",
        line_number: Optional[int] = None,
        condition_type: str = "always",
        threshold: Optional[float] = None,
        enabled: bool = True,
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = _debugger_breakpoint_body(
            node_id, workspace_id, workflow_id, file_path, line_number, condition_type, threshold, enabled, label
        )
        return await self._client._req("POST", "/v1/platform/debugger/breakpoints", json=body)

    async def list_breakpoints(self, workspace_id: str = "default", workflow_id: Optional[str] = None) -> Dict[str, Any]:
        return await self._client._req(
            "GET", "/v1/platform/debugger/breakpoints", params=_debugger_list_breakpoints_params(workspace_id, workflow_id)
        )

    async def delete_breakpoint(self, breakpoint_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        seg = _debugger_seg(breakpoint_id, "breakpoint_id")
        return await self._client._req(
            "DELETE", f"/v1/platform/debugger/breakpoints/{seg}", params={"workspace_id": workspace_id}
        )

    async def start_debug_session(
        self,
        workflow_id: str = "WF-STUDIO-01",
        *,
        workspace_id: str = "default",
        steps: Optional[List[Dict[str, Any]]] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = _debugger_start_session_body(workflow_id, workspace_id, steps, initial_state)
        return await self._client._req("POST", "/v1/platform/debugger/sessions", json=body)

    async def list_debug_sessions(self, workspace_id: str = "default", limit: int = 20) -> Dict[str, Any]:
        return await self._client._req(
            "GET", "/v1/platform/debugger/sessions", params=_debugger_list_sessions_params(workspace_id, limit)
        )

    async def step_debug_session(
        self,
        session_id: str,
        action: str = "step_over",
        *,
        workspace_id: str = "default",
        state_patch: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        seg = _debugger_seg(session_id, "session_id")
        body = _debugger_step_body(action, workspace_id, state_patch)
        return await self._client._req("POST", f"/v1/platform/debugger/sessions/{seg}/step", json=body)

    async def get_debugger_codelens(
        self,
        workspace_id: str = "default",
        workflow_id: Optional[str] = None,
        file_path: Optional[str] = None,
        *,
        source_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = _debugger_codelens_params(workspace_id, workflow_id, file_path, source_code)
        return await self._client._req("GET", "/v1/platform/debugger/codelens", params=params)


class SyncPlatformDebuggerMixin:
    """Synchronous Phase 14 Step-Through Debugger, Conditional Breakpoints & 4D CodeLens methods."""

    _client: "KeelwayClient"

    def set_breakpoint(
        self,
        node_id: Optional[str] = None,
        *,
        workspace_id: str = "default",
        workflow_id: str = "WF-STUDIO-01",
        file_path: str = "workflows/refund_agent.py",
        line_number: Optional[int] = None,
        condition_type: str = "always",
        threshold: Optional[float] = None,
        enabled: bool = True,
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = _debugger_breakpoint_body(
            node_id, workspace_id, workflow_id, file_path, line_number, condition_type, threshold, enabled, label
        )
        return self._client._req("POST", "/v1/platform/debugger/breakpoints", json=body)

    def list_breakpoints(self, workspace_id: str = "default", workflow_id: Optional[str] = None) -> Dict[str, Any]:
        return self._client._req(
            "GET", "/v1/platform/debugger/breakpoints", params=_debugger_list_breakpoints_params(workspace_id, workflow_id)
        )

    def delete_breakpoint(self, breakpoint_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        seg = _debugger_seg(breakpoint_id, "breakpoint_id")
        return self._client._req(
            "DELETE", f"/v1/platform/debugger/breakpoints/{seg}", params={"workspace_id": workspace_id}
        )

    def start_debug_session(
        self,
        workflow_id: str = "WF-STUDIO-01",
        *,
        workspace_id: str = "default",
        steps: Optional[List[Dict[str, Any]]] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        body = _debugger_start_session_body(workflow_id, workspace_id, steps, initial_state)
        return self._client._req("POST", "/v1/platform/debugger/sessions", json=body)

    def list_debug_sessions(self, workspace_id: str = "default", limit: int = 20) -> Dict[str, Any]:
        return self._client._req(
            "GET", "/v1/platform/debugger/sessions", params=_debugger_list_sessions_params(workspace_id, limit)
        )

    def step_debug_session(
        self,
        session_id: str,
        action: str = "step_over",
        *,
        workspace_id: str = "default",
        state_patch: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        seg = _debugger_seg(session_id, "session_id")
        body = _debugger_step_body(action, workspace_id, state_patch)
        return self._client._req("POST", f"/v1/platform/debugger/sessions/{seg}/step", json=body)

    def get_debugger_codelens(
        self,
        workspace_id: str = "default",
        workflow_id: Optional[str] = None,
        file_path: Optional[str] = None,
        *,
        source_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        params = _debugger_codelens_params(workspace_id, workflow_id, file_path, source_code)
        return self._client._req("GET", "/v1/platform/debugger/codelens", params=params)
