"""
Keelway Client SDK — Phase 8 KFlow DAG Execution, KSpaces CRDT Sync & SBOM Mixins (`client.platform`).

Defines `AsyncPlatformKflowMixin` and `SyncPlatformKflowMixin` inherited by
`AsyncPlatformRuntimeMixin` and `SyncPlatformRuntimeMixin` for 100% sync + async parity across
`/v1/platform/automation/*`, `/v1/platform/kspaces/*`, and `/v1/platform/security/sbom`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient


def _kflow_exec_body(
    workflow_id: str,
    nodes: Optional[List[Dict[str, Any]]],
    trigger: str,
    token_budget: int,
    approved_node_ids: Optional[List[str]],
    workspace_id: str,
) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "workflow_id": workflow_id,
        "nodes": [dict(n) for n in (nodes or [])],
        "trigger": trigger,
        "token_budget": token_budget,
        "approved_node_ids": list(approved_node_ids or []),
    }


def _kflow_runs_params(workspace_id: str, workflow_id: Optional[str], limit: Optional[int]) -> Dict[str, Any]:
    params: Dict[str, Any] = {"workspace_id": workspace_id}
    if workflow_id is not None:
        params["workflow_id"] = workflow_id
    if limit is not None:
        params["limit"] = limit
    return params


def _kspaces_state_params(workspace_id: str, namespace: Optional[str]) -> Dict[str, Any]:
    params: Dict[str, Any] = {"workspace_id": workspace_id}
    if namespace is not None:
        params["namespace"] = namespace
    return params


class AsyncPlatformKflowMixin:
    """Asynchronous Phase 8 KFlow DAG, KSpaces CRDT & SBOM methods on `AsyncKeelwayClient.platform`."""

    _client: "AsyncKeelwayClient"

    async def execute_kflow_dag(
        self,
        workflow_id: str,
        nodes: Optional[List[Dict[str, Any]]] = None,
        trigger: str = "manual",
        token_budget: int = 25000,
        approved_node_ids: Optional[List[str]] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/automation/workflows/execute",
            json=_kflow_exec_body(workflow_id, nodes, trigger, token_budget, approved_node_ids, workspace_id),
        )

    async def list_kflow_runs(
        self,
        workspace_id: str = "default",
        workflow_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET",
            "/v1/platform/automation/runs",
            params=_kflow_runs_params(workspace_id, workflow_id, limit),
        )

    async def sync_kspaces_crdt(
        self,
        peer_id: str,
        operations: List[Dict[str, Any]],
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/kspaces/sync",
            json={"workspace_id": workspace_id, "peer_id": peer_id, "operations": [dict(op) for op in operations]},
        )

    async def get_kspaces_state(
        self,
        workspace_id: str = "default",
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET",
            "/v1/platform/kspaces/state",
            params=_kspaces_state_params(workspace_id, namespace),
        )

    async def get_platform_sbom(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/security/sbom", params={"workspace_id": workspace_id})


class SyncPlatformKflowMixin:
    """Synchronous Phase 8 KFlow DAG, KSpaces CRDT & SBOM methods on `KeelwayClient.platform`."""

    _client: "KeelwayClient"

    def execute_kflow_dag(
        self,
        workflow_id: str,
        nodes: Optional[List[Dict[str, Any]]] = None,
        trigger: str = "manual",
        token_budget: int = 25000,
        approved_node_ids: Optional[List[str]] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/automation/workflows/execute",
            json=_kflow_exec_body(workflow_id, nodes, trigger, token_budget, approved_node_ids, workspace_id),
        )

    def list_kflow_runs(
        self,
        workspace_id: str = "default",
        workflow_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET",
            "/v1/platform/automation/runs",
            params=_kflow_runs_params(workspace_id, workflow_id, limit),
        )

    def sync_kspaces_crdt(
        self,
        peer_id: str,
        operations: List[Dict[str, Any]],
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/kspaces/sync",
            json={"workspace_id": workspace_id, "peer_id": peer_id, "operations": [dict(op) for op in operations]},
        )

    def get_kspaces_state(
        self,
        workspace_id: str = "default",
        namespace: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET",
            "/v1/platform/kspaces/state",
            params=_kspaces_state_params(workspace_id, namespace),
        )

    def get_platform_sbom(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/security/sbom", params={"workspace_id": workspace_id})
