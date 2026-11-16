"""
Keelway Client SDK — Phase 17 Formal Safety State-Machine Verifier
+ Federated Edge-to-Cluster Agent Mesh Mixins (`client.platform`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient

_VALID_MESH_TIERS = ("edge_local", "cluster_burst")
_VALID_HARDWARE_HALS = ("apple_metal_secure_enclave", "nvidia_h100_cc", "linux_tpm2")
_VALID_NODE_STATUSES = ("ONLINE", "DRAINING")
_VALID_DATA_CLASSIFICATIONS = ("public", "internal", "restricted_pii")


def _clean_non_empty(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return clean


def _safety_mesh_list_params(workspace_id: str, limit: int) -> Dict[str, Any]:
    if isinstance(limit, bool) or int(limit) < 1:
        raise ValueError("limit must be >= 1.")
    clean_ws = str(workspace_id or "default").strip() or "default"
    return {"workspace_id": clean_ws, "limit": int(limit)}


def _verify_safety_body(
    workspace_id: str,
    workflow_id: str,
    workflow_name: str,
    nodes: Optional[List[Dict[str, Any]]],
    edges: Optional[List[Dict[str, Any]]],
    airgap_mode: bool,
    inject_p10_guards: bool,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "workspace_id": str(workspace_id or "default").strip() or "default",
        "workflow_id": _clean_non_empty(workflow_id, "workflow_id"),
        "workflow_name": _clean_non_empty(workflow_name, "workflow_name"),
        "airgap_mode": bool(airgap_mode),
        "inject_p10_guards": bool(inject_p10_guards),
    }
    if nodes is not None:
        if not isinstance(nodes, list):
            raise ValueError("nodes must be a list of dicts.")
        body["nodes"] = [dict(node) for node in nodes]
    if edges is not None:
        if not isinstance(edges, list):
            raise ValueError("edges must be a list of dicts.")
        body["edges"] = [dict(edge) for edge in edges]
    return body


def _register_mesh_node_body(
    name: str, tier: str, hardware_hal: str, workspace_id: str, node_id: Optional[str], region: str, vram_gb: int, status: str
) -> Dict[str, Any]:
    clean_tier = str(tier or "").strip()
    if clean_tier not in _VALID_MESH_TIERS:
        raise ValueError(f"tier must be one of {list(_VALID_MESH_TIERS)}.")
    clean_hal = str(hardware_hal or "").strip()
    if clean_hal not in _VALID_HARDWARE_HALS:
        raise ValueError(f"hardware_hal must be one of {list(_VALID_HARDWARE_HALS)}.")
    if isinstance(vram_gb, bool) or int(vram_gb) < 1:
        raise ValueError("vram_gb must be >= 1.")
    clean_status = str(status or "").strip()
    if clean_status not in _VALID_NODE_STATUSES:
        raise ValueError(f"status must be one of {list(_VALID_NODE_STATUSES)}.")
    body: Dict[str, Any] = {
        "workspace_id": str(workspace_id or "default").strip() or "default",
        "name": _clean_non_empty(name, "name"),
        "tier": clean_tier,
        "hardware_hal": clean_hal,
        "region": _clean_non_empty(region, "region"),
        "vram_gb": int(vram_gb),
        "status": clean_status,
    }
    if node_id is not None and str(node_id).strip():
        body["node_id"] = str(node_id).strip()
    return body


def _dispatch_mesh_handoff_body(
    workspace_id: str, workflow_name: str, task_summary: str, data_classification: str, allow_sanitized_burst: bool, force_raw_cloud_burst: bool
) -> Dict[str, Any]:
    clean_cls = str(data_classification or "").strip()
    if clean_cls not in _VALID_DATA_CLASSIFICATIONS:
        raise ValueError(f"data_classification must be one of {list(_VALID_DATA_CLASSIFICATIONS)}.")
    return {
        "workspace_id": str(workspace_id or "default").strip() or "default",
        "workflow_name": _clean_non_empty(workflow_name, "workflow_name"),
        "task_summary": _clean_non_empty(task_summary, "task_summary"),
        "data_classification": clean_cls,
        "allow_sanitized_burst": bool(allow_sanitized_burst),
        "force_raw_cloud_burst": bool(force_raw_cloud_burst),
    }


class AsyncPlatformSafetyMeshMixin:
    """Asynchronous Phase 17 Formal Safety Verifier & Federated Edge Mesh methods."""

    _client: "AsyncKeelwayClient"

    async def verify_workflow_safety(
        self,
        *,
        workspace_id: str = "default",
        workflow_id: str = "WF-TREASURY-01",
        workflow_name: str = "treasury-wire-approver",
        nodes: Optional[List[Dict[str, Any]]] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
        airgap_mode: bool = False,
        inject_p10_guards: bool = False,
    ) -> Dict[str, Any]:
        body = _verify_safety_body(workspace_id, workflow_id, workflow_name, nodes, edges, airgap_mode, inject_p10_guards)
        return await self._client._req("POST", "/v1/platform/safety/verify", json=body)

    async def list_safety_verifications(self, *, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/safety/verifications", params=_safety_mesh_list_params(workspace_id, limit))

    async def register_mesh_node(
        self,
        name: str,
        *,
        tier: str = "edge_local",
        hardware_hal: str = "apple_metal_secure_enclave",
        workspace_id: str = "default",
        node_id: Optional[str] = None,
        region: str = "local-loopback",
        vram_gb: int = 32,
        status: str = "ONLINE",
    ) -> Dict[str, Any]:
        body = _register_mesh_node_body(name, tier, hardware_hal, workspace_id, node_id, region, vram_gb, status)
        return await self._client._req("POST", "/v1/platform/mesh/nodes", json=body)

    async def list_mesh_nodes(self, *, workspace_id: str = "default") -> Dict[str, Any]:
        clean_ws = str(workspace_id or "default").strip() or "default"
        return await self._client._req("GET", "/v1/platform/mesh/nodes", params={"workspace_id": clean_ws})

    async def dispatch_mesh_handoff(
        self,
        *,
        workspace_id: str = "default",
        workflow_name: str = "clinical-synthesis-pipeline",
        task_summary: str = "Ingest patient intake & synthesize anonymized cohort summary",
        data_classification: str = "restricted_pii",
        allow_sanitized_burst: bool = True,
        force_raw_cloud_burst: bool = False,
    ) -> Dict[str, Any]:
        body = _dispatch_mesh_handoff_body(
            workspace_id, workflow_name, task_summary, data_classification, allow_sanitized_burst, force_raw_cloud_burst
        )
        return await self._client._req("POST", "/v1/platform/mesh/dispatch", json=body)

    async def list_mesh_handoffs(self, *, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/mesh/handoffs", params=_safety_mesh_list_params(workspace_id, limit))


class SyncPlatformSafetyMeshMixin:
    """Synchronous Phase 17 Formal Safety Verifier & Federated Edge Mesh methods."""

    _client: "KeelwayClient"

    def verify_workflow_safety(
        self,
        *,
        workspace_id: str = "default",
        workflow_id: str = "WF-TREASURY-01",
        workflow_name: str = "treasury-wire-approver",
        nodes: Optional[List[Dict[str, Any]]] = None,
        edges: Optional[List[Dict[str, Any]]] = None,
        airgap_mode: bool = False,
        inject_p10_guards: bool = False,
    ) -> Dict[str, Any]:
        body = _verify_safety_body(workspace_id, workflow_id, workflow_name, nodes, edges, airgap_mode, inject_p10_guards)
        return self._client._req("POST", "/v1/platform/safety/verify", json=body)

    def list_safety_verifications(self, *, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/safety/verifications", params=_safety_mesh_list_params(workspace_id, limit))

    def register_mesh_node(
        self,
        name: str,
        *,
        tier: str = "edge_local",
        hardware_hal: str = "apple_metal_secure_enclave",
        workspace_id: str = "default",
        node_id: Optional[str] = None,
        region: str = "local-loopback",
        vram_gb: int = 32,
        status: str = "ONLINE",
    ) -> Dict[str, Any]:
        body = _register_mesh_node_body(name, tier, hardware_hal, workspace_id, node_id, region, vram_gb, status)
        return self._client._req("POST", "/v1/platform/mesh/nodes", json=body)

    def list_mesh_nodes(self, *, workspace_id: str = "default") -> Dict[str, Any]:
        clean_ws = str(workspace_id or "default").strip() or "default"
        return self._client._req("GET", "/v1/platform/mesh/nodes", params={"workspace_id": clean_ws})

    def dispatch_mesh_handoff(
        self,
        *,
        workspace_id: str = "default",
        workflow_name: str = "clinical-synthesis-pipeline",
        task_summary: str = "Ingest patient intake & synthesize anonymized cohort summary",
        data_classification: str = "restricted_pii",
        allow_sanitized_burst: bool = True,
        force_raw_cloud_burst: bool = False,
    ) -> Dict[str, Any]:
        body = _dispatch_mesh_handoff_body(
            workspace_id, workflow_name, task_summary, data_classification, allow_sanitized_burst, force_raw_cloud_burst
        )
        return self._client._req("POST", "/v1/platform/mesh/dispatch", json=body)

    def list_mesh_handoffs(self, *, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/mesh/handoffs", params=_safety_mesh_list_params(workspace_id, limit))


PlatformSafetyMeshMixin = SyncPlatformSafetyMeshMixin
