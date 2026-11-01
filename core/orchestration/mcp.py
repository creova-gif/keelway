"""
Keelway Universal Model Context Protocol (MCP) Bridge.
Implements the JSON-RPC Model Context Protocol standard:
- Discovers and registers external MCP tools and resources.
- Exposes Keelway's local Hybrid Memory and Security Gateway to external clients (Cursor, Claude Code, Zed).
"""

import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Awaitable


@dataclass
class MCPToolDefinition:
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass
class MCPResourceDefinition:
    uri: str
    name: str
    mime_type: str = "text/plain"
    description: str = ""


class MCPProtocolServer:
    """Lightweight, zero-overhead Model Context Protocol server for Keelway tools & resources."""

    def __init__(self):
        self.tools: Dict[str, MCPToolDefinition] = {}
        self.resources: Dict[str, MCPResourceDefinition] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> None:
        self.tools[name] = MCPToolDefinition(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            handler=handler,
        )

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str = "",
        mime_type: str = "text/plain",
    ) -> None:
        self.resources[uri] = MCPResourceDefinition(
            uri=uri,
            name=name,
            description=description,
            mime_type=mime_type,
        )

    async def handle_jsonrpc_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Processes an incoming JSON-RPC 2.0 MCP request."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/list":
            tools_list = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.parameters_schema,
                }
                for t in self.tools.values()
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}

        elif method == "resources/list":
            resources_list = [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mime_type,
                }
                for r in self.resources.values()
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": resources_list}}

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})
            if tool_name not in self.tools:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"MCP Tool '{tool_name}' not found"},
                }

            try:
                res = await self.tools[tool_name].handler(arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(res)}]},
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32000, "message": f"Tool execution failed: {str(e)}"},
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not implemented"},
        }


mcp_server = MCPProtocolServer()
