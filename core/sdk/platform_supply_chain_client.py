"""
Keelway Client SDK — Phase 20 Cryptographic MCP & Skill Lockfile,
Tool-Poisoning / Rug-Pull Firewall & Conformance Benchmark Mixins (`client.platform`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient

_DEFAULT_TOOL_SCHEMA_JSON = '{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}'
_VALID_SIMULATE_MODES = ("clean", "rug_pull", "poisoning")
_VALID_TARGET_KINDS = ("mcp_server", "skill_package", "opencore_model")


def _clean_non_empty(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return clean


def _clean_ws(workspace_id: str) -> str:
    return str(workspace_id or "default").strip() or "default"


def _validate_positive_int(value: int, field_name: str) -> int:
    if isinstance(value, bool) or int(value) < 1:
        raise ValueError(f"{field_name} must be >= 1.")
    return int(value)


def _validate_unit_score(value: float, field_name: str) -> float:
    if isinstance(value, bool) or not (0.0 <= float(value) <= 1.0):
        raise ValueError(f"{field_name} must be between 0.0 and 1.0.")
    return float(value)


def _normalize_tool_specs(tools: List[Dict[str, Any]], field_name: str) -> List[Dict[str, Any]]:
    if not isinstance(tools, list):
        raise ValueError(f"{field_name} must be a list of tool specs.")
    normalized: List[Dict[str, Any]] = []
    for item in tools:
        if not isinstance(item, dict):
            raise ValueError(f"Each entry in {field_name} must be a dict.")
        desc = item.get("description")
        if not isinstance(desc, str) or desc == "":
            raise ValueError(f"{field_name}[].description must be a non-empty string.")
        schema_raw = item.get("input_schema_json")
        schema_json = schema_raw if isinstance(schema_raw, str) and schema_raw != "" else _DEFAULT_TOOL_SCHEMA_JSON
        normalized.append(
            {
                "server_id": _clean_non_empty(str(item.get("server_id") or ""), f"{field_name}[].server_id"),
                "tool_name": _clean_non_empty(str(item.get("tool_name") or ""), f"{field_name}[].tool_name"),
                "version": str(item.get("version") or "1.0.0").strip() or "1.0.0",
                "description": desc,
                "input_schema_json": schema_json,
            }
        )
    return normalized


def _list_query_params(workspace_id: str, limit: int) -> Dict[str, Any]:
    return {"workspace_id": _clean_ws(workspace_id), "limit": _validate_positive_int(limit, "limit")}


def _pin_lockfile_body(workspace_id: str, lockfile_name: str, tools: Optional[List[Dict[str, Any]]]) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "workspace_id": _clean_ws(workspace_id),
        "lockfile_name": _clean_non_empty(lockfile_name, "lockfile_name"),
    }
    if tools is not None:
        body["tools"] = _normalize_tool_specs(tools, "tools")
    return body


def _verify_lockfile_body(
    workspace_id: str, lockfile_id: Optional[str], live_tools: Optional[List[Dict[str, Any]]], simulate_mode: str
) -> Dict[str, Any]:
    clean_mode = str(simulate_mode or "").strip()
    if clean_mode not in _VALID_SIMULATE_MODES:
        raise ValueError(f"simulate_mode must be one of {list(_VALID_SIMULATE_MODES)}.")
    body: Dict[str, Any] = {"workspace_id": _clean_ws(workspace_id), "simulate_mode": clean_mode}
    if lockfile_id is not None and str(lockfile_id).strip():
        body["lockfile_id"] = str(lockfile_id).strip()
    if live_tools is not None:
        body["live_tools"] = _normalize_tool_specs(live_tools, "live_tools")
    return body


def _bench_run_body(
    workspace_id: str,
    target_id: str,
    target_kind: str,
    model_id: str,
    latency_budget_ms: int,
    min_conformance_score: float,
    scenarios: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    clean_kind = str(target_kind or "").strip()
    if clean_kind not in _VALID_TARGET_KINDS:
        raise ValueError(f"target_kind must be one of {list(_VALID_TARGET_KINDS)}.")
    body: Dict[str, Any] = {
        "workspace_id": _clean_ws(workspace_id),
        "target_id": _clean_non_empty(target_id, "target_id"),
        "target_kind": clean_kind,
        "model_id": _clean_non_empty(model_id, "model_id"),
        "latency_budget_ms": _validate_positive_int(latency_budget_ms, "latency_budget_ms"),
        "min_conformance_score": _validate_unit_score(min_conformance_score, "min_conformance_score"),
    }
    if scenarios is not None:
        if not isinstance(scenarios, list):
            raise ValueError("scenarios must be a list of dicts.")
        body["scenarios"] = [dict(scenario) for scenario in scenarios]
    return body


class AsyncPlatformSupplyChainMixin:
    """Asynchronous Phase 20 Cryptographic MCP Lockfile & Conformance Benchmark methods."""

    _client: "AsyncKeelwayClient"

    async def pin_mcp_lockfile(
        self,
        workspace_id: str = "default",
        lockfile_name: str = "keelway.lock.json",
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        body = _pin_lockfile_body(workspace_id, lockfile_name, tools)
        return await self._client._req("POST", "/v1/platform/supply-chain/lock/pin", json=body)

    async def list_mcp_lockfiles(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return await self._client._req(
            "GET", "/v1/platform/supply-chain/lock/snapshots", params=_list_query_params(workspace_id, limit)
        )

    async def verify_mcp_lockfile(
        self,
        workspace_id: str = "default",
        lockfile_id: Optional[str] = None,
        live_tools: Optional[List[Dict[str, Any]]] = None,
        simulate_mode: str = "clean",
    ) -> Dict[str, Any]:
        body = _verify_lockfile_body(workspace_id, lockfile_id, live_tools, simulate_mode)
        return await self._client._req("POST", "/v1/platform/supply-chain/lock/verify", json=body)

    async def list_mcp_lock_verifications(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return await self._client._req(
            "GET", "/v1/platform/supply-chain/lock/verifications", params=_list_query_params(workspace_id, limit)
        )

    async def run_conformance_benchmark(
        self,
        workspace_id: str = "default",
        target_id: str = "mcp-git-local",
        target_kind: str = "mcp_server",
        model_id: str = "keelway-core:7b",
        latency_budget_ms: int = 250,
        min_conformance_score: float = 0.90,
        scenarios: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        body = _bench_run_body(
            workspace_id, target_id, target_kind, model_id, latency_budget_ms, min_conformance_score, scenarios
        )
        return await self._client._req("POST", "/v1/platform/supply-chain/bench/run", json=body)

    async def list_conformance_benchmarks(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return await self._client._req(
            "GET", "/v1/platform/supply-chain/bench/runs", params=_list_query_params(workspace_id, limit)
        )


class SyncPlatformSupplyChainMixin:
    """Synchronous Phase 20 Cryptographic MCP Lockfile & Conformance Benchmark methods."""

    _client: "KeelwayClient"

    def pin_mcp_lockfile(
        self,
        workspace_id: str = "default",
        lockfile_name: str = "keelway.lock.json",
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        body = _pin_lockfile_body(workspace_id, lockfile_name, tools)
        return self._client._req("POST", "/v1/platform/supply-chain/lock/pin", json=body)

    def list_mcp_lockfiles(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return self._client._req(
            "GET", "/v1/platform/supply-chain/lock/snapshots", params=_list_query_params(workspace_id, limit)
        )

    def verify_mcp_lockfile(
        self,
        workspace_id: str = "default",
        lockfile_id: Optional[str] = None,
        live_tools: Optional[List[Dict[str, Any]]] = None,
        simulate_mode: str = "clean",
    ) -> Dict[str, Any]:
        body = _verify_lockfile_body(workspace_id, lockfile_id, live_tools, simulate_mode)
        return self._client._req("POST", "/v1/platform/supply-chain/lock/verify", json=body)

    def list_mcp_lock_verifications(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return self._client._req(
            "GET", "/v1/platform/supply-chain/lock/verifications", params=_list_query_params(workspace_id, limit)
        )

    def run_conformance_benchmark(
        self,
        workspace_id: str = "default",
        target_id: str = "mcp-git-local",
        target_kind: str = "mcp_server",
        model_id: str = "keelway-core:7b",
        latency_budget_ms: int = 250,
        min_conformance_score: float = 0.90,
        scenarios: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        body = _bench_run_body(
            workspace_id, target_id, target_kind, model_id, latency_budget_ms, min_conformance_score, scenarios
        )
        return self._client._req("POST", "/v1/platform/supply-chain/bench/run", json=body)

    def list_conformance_benchmarks(self, workspace_id: str = "default", limit: int = 25) -> Dict[str, Any]:
        return self._client._req(
            "GET", "/v1/platform/supply-chain/bench/runs", params=_list_query_params(workspace_id, limit)
        )


PlatformSupplyChainMixin = SyncPlatformSupplyChainMixin
