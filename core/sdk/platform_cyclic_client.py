"""
Keelway Client SDK — Phase 15 Bounded Cyclic KFlow Sub-Graphs, Saga Compensation
& Pre-Run Cost/Privacy Autopilot Mixins (`client.platform`).

Defines `AsyncPlatformCyclicMixin` and `SyncPlatformCyclicMixin` inherited by
`AsyncPlatformRuntimeMixin` and `SyncPlatformRuntimeMixin` for 100% sync + async parity across
`/v1/platform/kflow/*`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import quote

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient

_VALID_PRIVACY_POLICIES = ("hybrid_balanced", "airgap_strict", "eu_residency")


def _cyclic_seg(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return quote(clean, safe="")


def _cyclic_validate_body(
    workspace_id: str,
    workflow_id: str,
    nodes: Optional[List[Dict[str, Any]]],
    loop_edges: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    clean_wf = str(workflow_id or "").strip()
    if not clean_wf:
        raise ValueError("workflow_id must be non-empty.")
    body: Dict[str, Any] = {"workspace_id": workspace_id, "workflow_id": clean_wf}
    if nodes is not None:
        body["nodes"] = [dict(node) for node in nodes]
    if loop_edges is not None:
        body["loop_edges"] = [dict(edge) for edge in loop_edges]
    return body


def _cyclic_execute_body(
    workspace_id: str,
    workflow_id: str,
    nodes: Optional[List[Dict[str, Any]]],
    loop_edges: Optional[List[Dict[str, Any]]],
    max_iterations_override: Optional[int],
    critic_threshold: float,
    fan_out_shards: Optional[int],
    simulate_timeout: bool,
    initial_state: Optional[Dict[str, Any]],
    approved_node_ids: Optional[List[str]],
) -> Dict[str, Any]:
    body = _cyclic_validate_body(workspace_id, workflow_id, nodes, loop_edges)
    if isinstance(critic_threshold, bool) or float(critic_threshold) < 0.0 or float(critic_threshold) > 1.0:
        raise ValueError("critic_threshold must be between 0.0 and 1.0.")
    body["critic_threshold"] = float(critic_threshold)
    body["simulate_timeout"] = bool(simulate_timeout)
    if max_iterations_override is not None:
        if isinstance(max_iterations_override, bool) or int(max_iterations_override) < 1 or int(max_iterations_override) > 10:
            raise ValueError("max_iterations_override must be between 1 and 10.")
        body["max_iterations_override"] = int(max_iterations_override)
    if fan_out_shards is not None:
        if isinstance(fan_out_shards, bool) or int(fan_out_shards) < 1 or int(fan_out_shards) > 16:
            raise ValueError("fan_out_shards must be between 1 and 16.")
        body["fan_out_shards"] = int(fan_out_shards)
    if initial_state is not None:
        body["initial_state"] = dict(initial_state)
    if approved_node_ids is not None:
        body["approved_node_ids"] = [str(nid) for nid in approved_node_ids]
    return body


def _cyclic_list_params(workspace_id: str, workflow_id: Optional[str], limit: int) -> Dict[str, Any]:
    if isinstance(limit, bool) or int(limit) < 1:
        raise ValueError("limit must be >= 1.")
    params: Dict[str, Any] = {"workspace_id": workspace_id, "limit": int(limit)}
    if workflow_id is not None and str(workflow_id).strip():
        params["workflow_id"] = str(workflow_id).strip()
    return params


def _autopilot_simulate_body(
    workspace_id: str,
    workflow_id: str,
    nodes: Optional[List[Dict[str, Any]]],
    loop_edges: Optional[List[Dict[str, Any]]],
    budget_cap_usd: float,
    privacy_policy: str,
    expected_loop_multiplier: int,
) -> Dict[str, Any]:
    body = _cyclic_validate_body(workspace_id, workflow_id, nodes, loop_edges)
    clean_policy = str(privacy_policy or "").strip()
    if clean_policy not in _VALID_PRIVACY_POLICIES:
        raise ValueError(f"privacy_policy must be one of {list(_VALID_PRIVACY_POLICIES)}.")
    if isinstance(budget_cap_usd, bool) or float(budget_cap_usd) < 0.0:
        raise ValueError("budget_cap_usd must be >= 0.0.")
    if isinstance(expected_loop_multiplier, bool) or int(expected_loop_multiplier) < 1:
        raise ValueError("expected_loop_multiplier must be >= 1.")
    body["budget_cap_usd"] = float(budget_cap_usd)
    body["privacy_policy"] = clean_policy
    body["expected_loop_multiplier"] = int(expected_loop_multiplier)
    return body


class AsyncPlatformCyclicMixin:
    """Asynchronous Phase 15 Bounded Cyclic KFlow & Cost/Privacy Autopilot methods."""

    _client: "AsyncKeelwayClient"

    async def validate_cyclic_kflow(
        self,
        *,
        workspace_id: str = "default",
        workflow_id: str = "WF-CYCLIC-01",
        nodes: Optional[List[Dict[str, Any]]] = None,
        loop_edges: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        body = _cyclic_validate_body(workspace_id, workflow_id, nodes, loop_edges)
        return await self._client._req("POST", "/v1/platform/kflow/cyclic/validate", json=body)

    async def execute_cyclic_kflow(
        self,
        *,
        workspace_id: str = "default",
        workflow_id: str = "WF-CYCLIC-01",
        nodes: Optional[List[Dict[str, Any]]] = None,
        loop_edges: Optional[List[Dict[str, Any]]] = None,
        max_iterations_override: Optional[int] = None,
        critic_threshold: float = 0.85,
        fan_out_shards: Optional[int] = None,
        simulate_timeout: bool = False,
        initial_state: Optional[Dict[str, Any]] = None,
        approved_node_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        body = _cyclic_execute_body(
            workspace_id, workflow_id, nodes, loop_edges, max_iterations_override,
            critic_threshold, fan_out_shards, simulate_timeout, initial_state, approved_node_ids,
        )
        return await self._client._req("POST", "/v1/platform/kflow/cyclic/execute", json=body)

    async def list_cyclic_kflow_runs(
        self, *, workspace_id: str = "default", workflow_id: Optional[str] = None, limit: int = 25
    ) -> Dict[str, Any]:
        params = _cyclic_list_params(workspace_id, workflow_id, limit)
        return await self._client._req("GET", "/v1/platform/kflow/cyclic/runs", params=params)

    async def get_cyclic_kflow_run(self, run_id: str, *, workspace_id: str = "default") -> Dict[str, Any]:
        seg = _cyclic_seg(run_id, "run_id")
        return await self._client._req("GET", f"/v1/platform/kflow/cyclic/runs/{seg}", params={"workspace_id": workspace_id})

    async def simulate_kflow_autopilot(
        self,
        *,
        workspace_id: str = "default",
        workflow_id: str = "WF-CYCLIC-01",
        nodes: Optional[List[Dict[str, Any]]] = None,
        loop_edges: Optional[List[Dict[str, Any]]] = None,
        budget_cap_usd: float = 0.15,
        privacy_policy: str = "hybrid_balanced",
        expected_loop_multiplier: int = 2,
    ) -> Dict[str, Any]:
        body = _autopilot_simulate_body(
            workspace_id, workflow_id, nodes, loop_edges, budget_cap_usd, privacy_policy, expected_loop_multiplier
        )
        return await self._client._req("POST", "/v1/platform/kflow/autopilot/simulate", json=body)

    async def list_kflow_autopilot_simulations(
        self, *, workspace_id: str = "default", workflow_id: Optional[str] = None, limit: int = 25
    ) -> Dict[str, Any]:
        params = _cyclic_list_params(workspace_id, workflow_id, limit)
        return await self._client._req("GET", "/v1/platform/kflow/autopilot/simulations", params=params)


class SyncPlatformCyclicMixin:
    """Synchronous Phase 15 Bounded Cyclic KFlow & Cost/Privacy Autopilot methods."""

    _client: "KeelwayClient"

    def validate_cyclic_kflow(
        self,
        *,
        workspace_id: str = "default",
        workflow_id: str = "WF-CYCLIC-01",
        nodes: Optional[List[Dict[str, Any]]] = None,
        loop_edges: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        body = _cyclic_validate_body(workspace_id, workflow_id, nodes, loop_edges)
        return self._client._req("POST", "/v1/platform/kflow/cyclic/validate", json=body)

    def execute_cyclic_kflow(
        self,
        *,
        workspace_id: str = "default",
        workflow_id: str = "WF-CYCLIC-01",
        nodes: Optional[List[Dict[str, Any]]] = None,
        loop_edges: Optional[List[Dict[str, Any]]] = None,
        max_iterations_override: Optional[int] = None,
        critic_threshold: float = 0.85,
        fan_out_shards: Optional[int] = None,
        simulate_timeout: bool = False,
        initial_state: Optional[Dict[str, Any]] = None,
        approved_node_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        body = _cyclic_execute_body(
            workspace_id, workflow_id, nodes, loop_edges, max_iterations_override,
            critic_threshold, fan_out_shards, simulate_timeout, initial_state, approved_node_ids,
        )
        return self._client._req("POST", "/v1/platform/kflow/cyclic/execute", json=body)

    def list_cyclic_kflow_runs(
        self, *, workspace_id: str = "default", workflow_id: Optional[str] = None, limit: int = 25
    ) -> Dict[str, Any]:
        params = _cyclic_list_params(workspace_id, workflow_id, limit)
        return self._client._req("GET", "/v1/platform/kflow/cyclic/runs", params=params)

    def get_cyclic_kflow_run(self, run_id: str, *, workspace_id: str = "default") -> Dict[str, Any]:
        seg = _cyclic_seg(run_id, "run_id")
        return self._client._req("GET", f"/v1/platform/kflow/cyclic/runs/{seg}", params={"workspace_id": workspace_id})

    def simulate_kflow_autopilot(
        self,
        *,
        workspace_id: str = "default",
        workflow_id: str = "WF-CYCLIC-01",
        nodes: Optional[List[Dict[str, Any]]] = None,
        loop_edges: Optional[List[Dict[str, Any]]] = None,
        budget_cap_usd: float = 0.15,
        privacy_policy: str = "hybrid_balanced",
        expected_loop_multiplier: int = 2,
    ) -> Dict[str, Any]:
        body = _autopilot_simulate_body(
            workspace_id, workflow_id, nodes, loop_edges, budget_cap_usd, privacy_policy, expected_loop_multiplier
        )
        return self._client._req("POST", "/v1/platform/kflow/autopilot/simulate", json=body)

    def list_kflow_autopilot_simulations(
        self, *, workspace_id: str = "default", workflow_id: Optional[str] = None, limit: int = 25
    ) -> Dict[str, Any]:
        params = _cyclic_list_params(workspace_id, workflow_id, limit)
        return self._client._req("GET", "/v1/platform/kflow/autopilot/simulations", params=params)
