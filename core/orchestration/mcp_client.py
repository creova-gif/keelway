"""
Keelway Universal Model Context Protocol (MCP) Client & Tool Bridge.
Connects to local and external MCP servers over stdio or in-process transports,
discovers external tools and resources, and securely binds them into the Keelway Agent Loop.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from core.security.env_scrub import scrub_env
from core.orchestration.mcp import MCPProtocolServer


@dataclass
class DiscoveredMCPTool:
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    server_id: str
    is_mutation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters_schema": self.parameters_schema,
            "server_id": self.server_id,
            "is_mutation": self.is_mutation,
        }


class MCPClient:
    """Universal MCP client supporting in-process and stdio subprocess servers."""

    def __init__(
        self,
        server_id: str,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        in_process_server: Optional[MCPProtocolServer] = None,
    ):
        self.server_id = server_id
        self.command = command
        self.args = args or []
        self.env = env or {}
        self.cwd = cwd
        self.in_process_server = in_process_server

        self.proc: Optional[asyncio.subprocess.Process] = None
        self._request_counter = 0
        self.initialized = False
        self.discovered_tools: Dict[str, DiscoveredMCPTool] = {}
        self.server_info: Dict[str, Any] = {}

    async def connect(self) -> None:
        """Start server process (if stdio) and perform MCP initialize handshake."""
        if self.in_process_server is not None:
            # In-process connection
            await self._perform_handshake_in_process()
        else:
            # Subprocess stdio connection
            if not self.command:
                raise ValueError("Either command or in_process_server must be provided to MCPClient.")
            await self._start_subprocess()
            await self._perform_handshake_stdio()

        # Discover available tools
        await self.refresh_tools()

    async def _start_subprocess(self) -> None:
        """Spawn external MCP server with scrubbed environment."""
        clean_env, _ = scrub_env(os.environ)
        clean_env.update(self.env)
        cmd_list = [self.command] + self.args

        # Substitute python with sys.executable for virtualenv isolation
        if cmd_list[0] in ("python", "python3"):
            cmd_list[0] = sys.executable

        self.proc = await asyncio.create_subprocess_exec(
            *cmd_list,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
            env=clean_env,
        )

    async def _send_jsonrpc_message(self, method: str, params: Optional[Dict[str, Any]] = None, is_notification: bool = False) -> Any:
        self._request_counter += 1
        msg_id = self._request_counter if not is_notification else None
        req: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if msg_id is not None:
            req["id"] = msg_id
        if params is not None:
            req["params"] = params

        if self.in_process_server is not None:
            resp = await self.in_process_server.handle_jsonrpc_request(req)
            if is_notification:
                return None
            if resp is None:
                raise RuntimeError(f"Null response from in-process MCP server for method '{method}'")
            if "error" in resp:
                raise RuntimeError(f"MCP error {resp['error'].get('code')}: {resp['error'].get('message')}")
            return resp.get("result")

        # Subprocess stdio transport
        if not self.proc or not self.proc.stdin or not self.proc.stdout:
            raise RuntimeError(f"MCP client for '{self.server_id}' is not connected.")

        raw_line = json.dumps(req) + "\n"
        self.proc.stdin.write(raw_line.encode("utf-8"))
        await self.proc.stdin.drain()

        if is_notification:
            return None

        line = await self.proc.stdout.readline()
        if not line:
            raise RuntimeError(f"MCP server '{self.server_id}' closed connection unexpectedly.")

        resp = json.loads(line.decode("utf-8"))
        if "error" in resp:
            raise RuntimeError(f"MCP error {resp['error'].get('code')}: {resp['error'].get('message')}")
        return resp.get("result")

    async def _perform_handshake_in_process(self) -> None:
        init_res = await self._send_jsonrpc_message("initialize", {
            "protocolVersion": "2025-06-18",
            "clientInfo": {"name": "keelway-core", "version": "0.1.0"},
            "capabilities": {"roots": {"listChanged": True}},
        })
        self.server_info = init_res or {}
        await self._send_jsonrpc_message("notifications/initialized", is_notification=True)
        self.initialized = True

    async def _perform_handshake_stdio(self) -> None:
        init_res = await self._send_jsonrpc_message("initialize", {
            "protocolVersion": "2025-06-18",
            "clientInfo": {"name": "keelway-core", "version": "0.1.0"},
            "capabilities": {"roots": {"listChanged": True}},
        })
        self.server_info = init_res or {}
        await self._send_jsonrpc_message("notifications/initialized", is_notification=True)
        self.initialized = True

    async def refresh_tools(self) -> List[DiscoveredMCPTool]:
        """Fetch list of tools exposed by the MCP server."""
        res = await self._send_jsonrpc_message("tools/list", {})
        tools_list = (res or {}).get("tools", [])
        self.discovered_tools.clear()

        mutation_verbs = ("write", "edit", "delete", "create", "execute", "run", "remove", "update", "patch", "mutate")

        for t in tools_list:
            name = t.get("name", "")
            desc = t.get("description", "")
            schema = t.get("inputSchema") or t.get("parameters_schema") or {}
            # Infer mutation flag from name or description
            is_mutation = any(v in name.lower() or v in desc.lower() for v in mutation_verbs)
            tool = DiscoveredMCPTool(
                name=name,
                description=desc,
                parameters_schema=schema,
                server_id=self.server_id,
                is_mutation=is_mutation,
            )
            self.discovered_tools[name] = tool

        return list(self.discovered_tools.values())

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke an MCP tool on the server."""
        if tool_name not in self.discovered_tools:
            # Re-check or attempt call directly
            pass

        res = await self._send_jsonrpc_message("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        # If response is standard MCP format: {"content": [{"type": "text", "text": "..."}]}
        if isinstance(res, dict) and "content" in res and isinstance(res["content"], list):
            for item in res["content"]:
                if isinstance(item, dict) and item.get("type") == "text":
                    try:
                        parsed = json.loads(item.get("text", ""))
                        if isinstance(parsed, dict):
                            res.update(parsed)
                    except Exception:
                        pass
        return res or {}

    async def disconnect(self) -> None:
        """Close stdio connection and terminate server process."""
        if self.proc:
            try:
                if self.proc.stdin:
                    self.proc.stdin.close()
                self.proc.terminate()
                await asyncio.wait_for(self.proc.wait(), timeout=3.0)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            finally:
                self.proc = None
        self.initialized = False
        self.discovered_tools.clear()


class MCPClientManager:
    """Manages active MCP client connections and mounts external tools into Agent Loops."""

    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}

    def register_client(self, client: MCPClient) -> None:
        self.clients[client.server_id] = client

    async def connect_client(self, client: MCPClient) -> List[DiscoveredMCPTool]:
        await client.connect()
        self.clients[client.server_id] = client
        return list(client.discovered_tools.values())

    async def get_client(self, server_id: str) -> Optional[MCPClient]:
        return self.clients.get(server_id)

    async def disconnect_all(self) -> None:
        for client in self.clients.values():
            await client.disconnect()
        self.clients.clear()

    def get_all_tools(self) -> List[DiscoveredMCPTool]:
        tools: List[DiscoveredMCPTool] = []
        for client in self.clients.values():
            tools.extend(client.discovered_tools.values())
        return tools

    def mount_tools_into_agent_loop(self, agent_loop: Any, prefix_server: bool = True) -> int:
        """Mounts discovered MCP tools as AgentTool handlers in an AutonomousAgentLoop."""
        from core.orchestration.agent_loop import AgentTool

        mounted_count = 0
        for server_id, client in self.clients.items():
            for tool_name, disc_tool in client.discovered_tools.items():
                bound_name = f"{server_id}__{tool_name}" if prefix_server else tool_name

                # Create closure for tool invocation
                def _make_handler(cl: MCPClient, tname: str):
                    async def _handler(args: Dict[str, Any]) -> Dict[str, Any]:
                        return await cl.call_tool(tname, args)
                    return _handler

                agent_loop.tools[bound_name] = AgentTool(
                    name=bound_name,
                    description=f"[MCP:{server_id}] {disc_tool.description}",
                    parameters=disc_tool.parameters_schema,
                    is_mutation=disc_tool.is_mutation,
                    handler=_make_handler(client, tool_name),
                )
                mounted_count += 1
        return mounted_count
