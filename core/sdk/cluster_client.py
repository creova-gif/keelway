"""
Keelway Client SDK — Distributed Cluster & Model Lifecycle Namespace (`client.cluster`).

Provides 100% synchronous (`SyncClusterClient`) and asynchronous (`AsyncClusterClient`)
parity across `/v1/cluster/*`: GPU/NPU node discovery, registration, drain/restore,
VRAM- & residency-aware scheduling, model lifecycle shadow/canary/production promotion &
rollback, and multi-tenant governance budget reservation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import quote

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient


def _nodes_query(
    region: Optional[str],
    runtime: Optional[str],
    include_drained: bool,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"include_drained": bool(include_drained)}
    if region is not None:
        params["region"] = region
    if runtime is not None:
        params["runtime"] = runtime
    return params


def _node_action_path(node_id: str, action: str) -> str:
    clean_id = str(node_id or "").strip()
    if not clean_id:
        raise ValueError("node_id must be non-empty.")
    return f"/v1/cluster/nodes/{quote(clean_id, safe='')}/{action}"


class AsyncClusterClient:
    """Asynchronous `/v1/cluster/*` sub-client attached at `AsyncKeelwayClient.cluster`."""

    def __init__(self, client: "AsyncKeelwayClient") -> None:
        self._client = client

    async def list_nodes(
        self,
        region: Optional[str] = None,
        runtime: Optional[str] = None,
        include_drained: bool = True,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "GET",
            "/v1/cluster/nodes",
            params=_nodes_query(region, runtime, include_drained),
        )

    async def register_node(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/cluster/nodes/register", json=dict(payload))

    async def drain_node(self, node_id: str) -> Dict[str, Any]:
        return await self._client._req("POST", _node_action_path(node_id, "drain"))

    async def restore_node(self, node_id: str) -> Dict[str, Any]:
        return await self._client._req("POST", _node_action_path(node_id, "restore"))

    async def schedule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/cluster/schedule", json=dict(payload))

    async def list_lifecycle(self, stage: Optional[str] = None) -> Dict[str, Any]:
        params: Optional[Dict[str, Any]] = {"stage": stage} if stage is not None else None
        return await self._client._req("GET", "/v1/cluster/lifecycle", params=params)

    async def promote_model(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/cluster/lifecycle/promote", json=dict(payload))

    async def rollback_model(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client._req("POST", "/v1/cluster/lifecycle/rollback", json=dict(payload))

    async def governance_adapter_status(self) -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/cluster/governance-adapter/status")

    async def reserve_budget(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/cluster/governance-adapter/reserve-budget",
            json=dict(payload),
        )


class SyncClusterClient:
    """Synchronous `/v1/cluster/*` sub-client attached at `KeelwayClient.cluster`."""

    def __init__(self, client: "KeelwayClient") -> None:
        self._client = client

    def list_nodes(
        self,
        region: Optional[str] = None,
        runtime: Optional[str] = None,
        include_drained: bool = True,
    ) -> Dict[str, Any]:
        return self._client._req(
            "GET",
            "/v1/cluster/nodes",
            params=_nodes_query(region, runtime, include_drained),
        )

    def register_node(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/cluster/nodes/register", json=dict(payload))

    def drain_node(self, node_id: str) -> Dict[str, Any]:
        return self._client._req("POST", _node_action_path(node_id, "drain"))

    def restore_node(self, node_id: str) -> Dict[str, Any]:
        return self._client._req("POST", _node_action_path(node_id, "restore"))

    def schedule(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/cluster/schedule", json=dict(payload))

    def list_lifecycle(self, stage: Optional[str] = None) -> Dict[str, Any]:
        params: Optional[Dict[str, Any]] = {"stage": stage} if stage is not None else None
        return self._client._req("GET", "/v1/cluster/lifecycle", params=params)

    def promote_model(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/cluster/lifecycle/promote", json=dict(payload))

    def rollback_model(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._client._req("POST", "/v1/cluster/lifecycle/rollback", json=dict(payload))

    def governance_adapter_status(self) -> Dict[str, Any]:
        return self._client._req("GET", "/v1/cluster/governance-adapter/status")

    def reserve_budget(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/cluster/governance-adapter/reserve-budget",
            json=dict(payload),
        )
