"""
Keelway Client SDK — Phase 7 MCP Control Plane & Golden Evaluation Mixins (`client.platform`).

Defines `AsyncPlatformMcpEvalMixin` and `SyncPlatformMcpEvalMixin` inherited by
`AsyncPlatformRuntimeMixin` and `SyncPlatformRuntimeMixin` for 100% sync + async parity
across `/v1/platform/mcp/*` and `/v1/platform/evals/*`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from urllib.parse import quote

if TYPE_CHECKING:
    from core.sdk.client import AsyncKeelwayClient, KeelwayClient


def _mcp_seg(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be non-empty.")
    return quote(clean, safe="")


def _mcp_server_body(
    server_id: str,
    name: str,
    transport: str,
    endpoint: str,
    workspace_id: str,
    allowed_tools: Optional[List[str]],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "id": server_id,
        "name": name,
        "transport": transport,
        "endpoint": endpoint,
        "workspace_id": workspace_id,
    }
    if allowed_tools is not None:
        out["allowed_tools"] = list(allowed_tools)
    return out


class AsyncPlatformMcpEvalMixin:
    """Asynchronous Phase 7 MCP & Golden Evaluation methods on `AsyncKeelwayClient.platform`."""

    _client: "AsyncKeelwayClient"

    async def list_mcp_servers(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/mcp/servers", params={"workspace_id": workspace_id})

    async def register_mcp_server(
        self,
        id: str,
        name: str,
        transport: str,
        endpoint: str,
        workspace_id: str = "default",
        allowed_tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/mcp/servers",
            json=_mcp_server_body(id, name, transport, endpoint, workspace_id, allowed_tools),
        )

    async def delete_mcp_server(self, server_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req(
            "DELETE",
            f"/v1/platform/mcp/servers/{_mcp_seg(server_id, 'server_id')}",
            params={"workspace_id": workspace_id},
        )

    async def list_mcp_tools(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/mcp/tools", params={"workspace_id": workspace_id})

    async def call_mcp_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/mcp/call",
            json={"workspace_id": workspace_id, "tool_name": tool_name, "arguments": dict(arguments or {})},
        )

    async def run_golden_evals(self, category: str = "all", workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req(
            "POST",
            "/v1/platform/evals/golden",
            json={"workspace_id": workspace_id, "category": category},
        )

    async def get_latest_golden_evals(self, workspace_id: str = "default") -> Dict[str, Any]:
        return await self._client._req("GET", "/v1/platform/evals/latest", params={"workspace_id": workspace_id})


class SyncPlatformMcpEvalMixin:
    """Synchronous Phase 7 MCP & Golden Evaluation methods on `KeelwayClient.platform`."""

    _client: "KeelwayClient"

    def list_mcp_servers(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/mcp/servers", params={"workspace_id": workspace_id})

    def register_mcp_server(
        self,
        id: str,
        name: str,
        transport: str,
        endpoint: str,
        workspace_id: str = "default",
        allowed_tools: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/mcp/servers",
            json=_mcp_server_body(id, name, transport, endpoint, workspace_id, allowed_tools),
        )

    def delete_mcp_server(self, server_id: str, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req(
            "DELETE",
            f"/v1/platform/mcp/servers/{_mcp_seg(server_id, 'server_id')}",
            params={"workspace_id": workspace_id},
        )

    def list_mcp_tools(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/mcp/tools", params={"workspace_id": workspace_id})

    def call_mcp_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/mcp/call",
            json={"workspace_id": workspace_id, "tool_name": tool_name, "arguments": dict(arguments or {})},
        )

    def run_golden_evals(self, category: str = "all", workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req(
            "POST",
            "/v1/platform/evals/golden",
            json={"workspace_id": workspace_id, "category": category},
        )

    def get_latest_golden_evals(self, workspace_id: str = "default") -> Dict[str, Any]:
        return self._client._req("GET", "/v1/platform/evals/latest", params={"workspace_id": workspace_id})
