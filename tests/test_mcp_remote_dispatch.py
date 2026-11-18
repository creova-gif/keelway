"""KEEL-ENG-042 — Remote MCP dispatch tests.

Verifies that `PlatformMcpRegistry.call_tool` can invoke registered external
MCP servers over `stdio` (via `core.orchestration.mcp_client.MCPClient`) and
`sse` (via `core.platform.mcp_client.call_remote_tool`), including allow-list
enforcement, ambiguity detection, redaction/receipt parity with builtins, and
failure paths.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict

import httpx
import pytest

from core.platform.mcp_client import McpClientError, call_remote_tool
from core.platform.mcp_registry import PlatformMcpRegistry


_STDLIB_ECHO_SERVER = '''\
import json, sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    method = msg.get("method")
    mid = msg.get("id")
    if mid is None:
        continue
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {},
                  "serverInfo": {"name": "echo-fixture", "version": "0.0.1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "echo.tool", "description": "Echo arguments",
                             "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        params = msg.get("params") or {}
        payload = {"echo": params.get("arguments") or {},
                   "tool": params.get("name")}
        result = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    else:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid,
                                     "error": {"code": -32601, "message": "unknown"}}) + "\\n")
        sys.stdout.flush()
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\\n")
    sys.stdout.flush()
'''


@pytest.fixture()
def echo_server_path(tmp_path: Path) -> Path:
    script = tmp_path / "mcp_echo_server.py"
    script.write_text(_STDLIB_ECHO_SERVER, encoding="utf-8")
    return script


@pytest.fixture()
def registry(tmp_path: Path) -> PlatformMcpRegistry:
    reg = PlatformMcpRegistry(db_path=tmp_path / "mcp.db", workspace_root=tmp_path)
    yield reg
    reg.close()


def test_stdio_remote_tool_roundtrip(registry: PlatformMcpRegistry, echo_server_path: Path) -> None:
    endpoint = f"{sys.executable} {echo_server_path}"
    registry.register_server("default", "echo-srv", "Echo", "stdio", endpoint, ["echo.tool"])

    res = registry.call_tool("default", "echo.tool", {"hello": "world", "n": 3})

    assert res["ok"] is True
    assert res["tool_name"] == "echo.tool"
    assert res["receipt_sha256"]
    assert res["result"]["echo"] == {"hello": "world", "n": 3}
    assert res["result"]["tool"] == "echo.tool"


def test_stdio_remote_tool_redacts_secrets(registry: PlatformMcpRegistry, echo_server_path: Path) -> None:
    endpoint = f"{sys.executable} {echo_server_path}"
    registry.register_server("default", "echo-srv", "Echo", "stdio", endpoint, ["*"])

    res = registry.call_tool("default", "echo.tool", {"token": "sk-ant-api03-" + "a" * 40})

    assert res["redacted"] is True
    assert "sk-ant-api03-" not in json.dumps(res["result"])


def test_unregistered_tool_still_keyerror(registry: PlatformMcpRegistry) -> None:
    with pytest.raises(KeyError):
        registry.call_tool("default", "no.such.tool", {})


def test_tool_not_in_allowed_tools_keyerror(registry: PlatformMcpRegistry, echo_server_path: Path) -> None:
    endpoint = f"{sys.executable} {echo_server_path}"
    registry.register_server("default", "echo-srv", "Echo", "stdio", endpoint, ["other.tool"])
    with pytest.raises(KeyError):
        registry.call_tool("default", "echo.tool", {})


def test_wildcard_allowed_tools(registry: PlatformMcpRegistry, echo_server_path: Path) -> None:
    endpoint = f"{sys.executable} {echo_server_path}"
    registry.register_server("default", "echo-srv", "Echo", "stdio", endpoint, ["*"])
    res = registry.call_tool("default", "echo.tool", {"x": 1})
    assert res["ok"] is True


def test_ambiguous_tool_claim_raises(registry: PlatformMcpRegistry, echo_server_path: Path) -> None:
    endpoint = f"{sys.executable} {echo_server_path}"
    registry.register_server("default", "srv-a", "A", "stdio", endpoint, ["echo.tool"])
    registry.register_server("default", "srv-b", "B", "stdio", endpoint, ["*"])
    with pytest.raises(ValueError, match="multiple servers"):
        registry.call_tool("default", "echo.tool", {})


def test_stdio_spawn_failure_wrapped(registry: PlatformMcpRegistry, tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist.py"
    registry.register_server("default", "bad-srv", "Bad", "stdio",
                             f"{sys.executable} {missing}", ["*"])
    from core.platform.mcp_registry import McpToolArgumentError
    with pytest.raises(McpToolArgumentError):
        registry.call_tool("default", "anything", {})


def test_sse_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["method"] == "tools/call"
        assert body["params"]["name"] == "remote.tool"
        return httpx.Response(200, json={
            "jsonrpc": "2.0", "id": "call-1",
            "result": {"content": [{"type": "text", "text": json.dumps({"answer": 42})}]},
        })

    transport = httpx.MockTransport(handler)
    res = call_remote_tool("sse", "https://mcp.example/sse", "remote.tool", {"q": 1},
                           http_transport=transport)
    assert res == {"answer": 42}


def test_sse_event_stream_response() -> None:
    payload = json.dumps({
        "jsonrpc": "2.0", "id": "call-1",
        "result": {"content": [{"type": "text", "text": json.dumps({"ok": True})}]},
    })

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              text=f"event: message\ndata: {payload}\n\n")

    transport = httpx.MockTransport(handler)
    res = call_remote_tool("sse", "https://mcp.example/sse", "t", {}, http_transport=transport)
    assert res == {"ok": True}


def test_sse_error_and_http_failure() -> None:
    def err_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": "call-1",
                                         "error": {"code": -32000, "message": "denied"}})

    with pytest.raises(McpClientError, match="denied"):
        call_remote_tool("sse", "https://mcp.example/sse", "t", {},
                         http_transport=httpx.MockTransport(err_handler))

    def http_err(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    with pytest.raises(McpClientError, match="HTTP 503"):
        call_remote_tool("sse", "https://mcp.example/sse", "t", {},
                         http_transport=httpx.MockTransport(http_err))


def test_unsupported_transport() -> None:
    with pytest.raises(McpClientError, match="Unsupported MCP transport"):
        call_remote_tool("websocket", "wss://x", "t", {})
