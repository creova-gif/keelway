"""Remote MCP tool dispatch for `PlatformMcpRegistry` (KEEL-ENG-042).

Makes registered `platform_mcp_servers` records actually invocable:

- `stdio` endpoints are executed through the existing `core.orchestration.mcp_client.MCPClient`
  (env-scrubbed subprocess, `python`→`sys.executable`, JSON-RPC initialize handshake,
  `tools/list` discovery, `tools/call`). Each registry call uses a fresh bounded session —
  no persistent process state is retained between calls.
- `sse` endpoints are invoked as streamable-HTTP JSON-RPC POSTs and accept either a JSON
  body or `text/event-stream` `data:` frames.

Both transports return the tool's JSON result payload; failures raise `McpClientError`.
"""

from __future__ import annotations

import asyncio
import json
import shlex
from typing import Any, Dict, Optional

import httpx

from core.orchestration.mcp_client import MCPClient

DEFAULT_TIMEOUT_S = 30.0


class McpClientError(RuntimeError):
    """Raised when a remote MCP server cannot be reached or returns an error."""


def _call_stdio(endpoint: str, tool_name: str, arguments: Dict[str, Any], timeout_s: float) -> Any:
    argv = shlex.split(endpoint)
    if not argv:
        raise McpClientError("MCP stdio endpoint resolved to an empty command.")
    client = MCPClient(server_id="registry-stdio", command=argv[0], args=argv[1:])

    async def _run() -> Dict[str, Any]:
        await client.connect()
        try:
            return await client.call_tool(tool_name, arguments)
        finally:
            await client.disconnect()

    try:
        return asyncio.run(asyncio.wait_for(_run(), timeout=timeout_s))
    except asyncio.TimeoutError as exc:
        raise McpClientError(f"MCP stdio call timed out after {timeout_s}s.") from exc
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError) as exc:
        raise McpClientError(f"MCP stdio call failed: {exc}") from exc


def _parse_sse_payload(text: str) -> Optional[Dict[str, Any]]:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                msg = json.loads(data)
            except ValueError:
                continue
            if isinstance(msg, dict):
                return msg
    return None


def _unwrap_mcp_result(res: Any) -> Any:
    """Unwrap standard MCP `content[0].text` JSON payloads when present."""
    if isinstance(res, dict):
        content = res.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            text = first.get("text") if isinstance(first, dict) else None
            if isinstance(text, str):
                try:
                    return json.loads(text)
                except ValueError:
                    return {"text": text}
    return res if res is not None else {}


def _call_sse(endpoint: str, tool_name: str, arguments: Dict[str, Any], timeout_s: float,
              http_transport: Optional[httpx.BaseTransport] = None) -> Any:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    try:
        with httpx.Client(timeout=timeout_s, transport=http_transport) as client:
            resp = client.post(endpoint, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise McpClientError(f"MCP SSE endpoint unreachable: {exc}") from exc
    if resp.status_code >= 400:
        raise McpClientError(f"MCP SSE endpoint returned HTTP {resp.status_code}: {resp.text[:300]}")
    ctype = resp.headers.get("content-type", "")
    msg: Optional[Dict[str, Any]] = None
    if "text/event-stream" in ctype:
        msg = _parse_sse_payload(resp.text)
    else:
        try:
            parsed = resp.json()
            msg = parsed if isinstance(parsed, dict) else None
        except ValueError:
            msg = None
    if msg is None:
        raise McpClientError("MCP SSE endpoint returned an unparseable response.")
    if "error" in msg:
        raise McpClientError(f"MCP tools/call error: {msg['error']}")
    return _unwrap_mcp_result(msg.get("result"))


def call_remote_tool(
    transport: str,
    endpoint: str,
    tool_name: str,
    arguments: Dict[str, Any],
    timeout_s: float = DEFAULT_TIMEOUT_S,
    http_transport: Optional[httpx.BaseTransport] = None,
) -> Any:
    """Invoke `tools/call` on a registered external MCP server.

    Returns the tool's JSON result payload. Raises `McpClientError` on
    transport/protocol failures.
    """
    clean_transport = str(transport or "").strip().lower()
    if clean_transport == "stdio":
        return _unwrap_mcp_result(_call_stdio(endpoint, tool_name, arguments, timeout_s))
    if clean_transport == "sse":
        return _call_sse(endpoint, tool_name, arguments, timeout_s, http_transport)
    raise McpClientError(f"Unsupported MCP transport '{clean_transport}'.")
