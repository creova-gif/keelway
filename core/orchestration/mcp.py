"""
Keelway Universal Model Context Protocol (MCP) Bridge.
Implements the JSON-RPC Model Context Protocol standard:
- Discovers and registers external MCP tools and resources.
- Exposes Keelway's local Hybrid Memory and Security Gateway to external clients (Cursor, Claude Code, Zed).
"""

import asyncio
import fnmatch
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Awaitable, IO

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_VERSIONS = {"2025-06-18", "2025-03-26", "2024-11-05"}


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

    async def handle_jsonrpc_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processes an incoming JSON-RPC 2.0 MCP message; notifications (no id) get no response."""
        if not isinstance(request, dict) or request.get("jsonrpc", "2.0") != "2.0" or not isinstance(request.get("method"), str):
            return {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None,
                    "error": {"code": -32600, "message": "Invalid Request"}}
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}
        if "id" not in request:
            return None
        if not isinstance(params, dict):
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Invalid params"}}

        if method == "initialize":
            asked = params.get("protocolVersion")
            asked = asked if isinstance(asked, str) else None
            return {"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": asked if asked in SUPPORTED_VERSIONS else PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}, "resources": {"listChanged": False}},
                "serverInfo": {"name": "keelway", "version": "1"},
            }}

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

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
                # MCP reports tool failures in the result so the model can see and recover from them.
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"content": [{"type": "text", "text": f"Tool execution failed: {e}"}], "isError": True},
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method '{method}' not implemented"},
        }


async def _safe_handle(server: MCPProtocolServer, message: Any) -> Optional[Dict[str, Any]]:
    try:
        return await server.handle_jsonrpc_request(message)
    except Exception as e:  # one bad message must not end the session
        print(f"keelway mcp: internal error: {e}", file=sys.stderr)
        req_id = message.get("id") if isinstance(message, dict) else None
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": "Internal error"}}


async def serve_stdio(server: MCPProtocolServer, stdin: Optional[IO[str]] = None, stdout: Optional[IO[str]] = None) -> None:
    """MCP stdio transport: newline-delimited JSON-RPC on stdin/stdout; nothing else is ever written to stdout."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    loop = asyncio.get_running_loop()
    while True:
        line = await loop.run_in_executor(None, stdin.readline)
        if not line:
            return
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response: Optional[Dict[str, Any]] = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
        else:
            if isinstance(message, list) and not message:
                response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
            elif isinstance(message, list):
                replies = [r for r in [await _safe_handle(server, m) for m in message] if r is not None]
                response = replies or None  # type: ignore[assignment]
            else:
                response = await _safe_handle(server, message)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            stdout.flush()


PROTECTED_DIRS = {".git", ".keelway", ".kora"}
SECRET_GLOBS = (".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_dsa*", "id_ecdsa*",
                "id_ed25519*", ".netrc", ".npmrc", ".pypirc", ".git-credentials")
SECRET_ALLOWED = {".env.example", ".env.sample", ".env.template"}


def _is_secret_name(name: str) -> bool:
    return name.lower() not in SECRET_ALLOWED and any(fnmatch.fnmatch(name.lower(), g) for g in SECRET_GLOBS)


def build_workspace_server(root: Optional[str] = None) -> MCPProtocolServer:
    """Read-only Keelway workspace tools for MCP clients. Writes and commands stay behind Keelway's approval gates."""
    from core.storage.workspace_fs import WorkspaceFilesystem

    fs = WorkspaceFilesystem(root)
    server = MCPProtocolServer()

    def _blocked(rel: Path) -> Optional[str]:
        if PROTECTED_DIRS & set(rel.parts):
            return "inside a protected Keelway/git directory"
        if any(_is_secret_name(part) for part in rel.parts):
            return "a credentials file"
        return None

    def _guard(path: str) -> str:
        resolved = fs.resolve_safe_path(path)
        for rel in (Path(path.lstrip("/\\")), resolved.relative_to(fs.root)):
            reason = _blocked(rel)
            if reason:
                raise PermissionError(f"'{path}' is {reason}")
        return path

    def _prune(node: Dict[str, Any]) -> Dict[str, Any]:
        kept = []
        for child in node.get("children", []):
            try:
                rel = (fs.root / child["path"]).resolve().relative_to(fs.root)
            except ValueError:
                continue  # symlink pointing outside the workspace
            if _blocked(rel) or _is_secret_name(child["name"]):
                continue
            kept.append(_prune(child))
        if "children" in node:
            node["children"] = kept
        return node

    async def list_files(args: Dict[str, Any]) -> Dict[str, Any]:
        result = fs.get_file_tree(_guard(args.get("path", ".")), max_depth=int(args.get("max_depth", 3)))
        result["tree"] = _prune(result["tree"])
        return result

    async def read_file(args: Dict[str, Any]) -> Dict[str, Any]:
        return fs.read_file(_guard(args["path"]), max_bytes=1_000_000)

    async def git_status(args: Dict[str, Any]) -> Dict[str, Any]:
        return fs.get_git_status()

    async def git_diff(args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        target = str(fs.resolve_safe_path(_guard(path)).relative_to(fs.root)) if path else "."
        excludes = [f":(exclude,glob)**/{d}/**" for d in sorted(PROTECTED_DIRS)]

        def _git(*extra: str) -> str:
            res = subprocess.run(["git", "diff", "HEAD", "--no-renames", "--relative", *extra], cwd=str(fs.root),
                                 capture_output=True, text=True, timeout=8)
            return res.stdout if res.returncode == 0 else ""

        # List changed files NUL-separated (never quoted), drop credentials files, then diff only what's left,
        # so allowed templates like .env.example still show and no header parsing is involved.
        changed = (await asyncio.to_thread(_git, "--name-only", "-z", "--", target, *excludes)).split("\0")
        allowed = [f":(literal){f}" for f in changed if f and not any(_is_secret_name(p) for p in Path(f).parts)]
        diff = await asyncio.to_thread(_git, "--", *allowed) if allowed else ""
        return {"path": path or "workspace", "diff": diff}

    path_arg = {"path": {"type": "string", "description": "Path relative to the workspace root"}}
    server.register_tool("list_files", "List files in the Keelway workspace (read-only).",
                         {"type": "object", "properties": {**path_arg, "max_depth": {"type": "integer"}}}, list_files)
    server.register_tool("read_file", "Read a text file from the Keelway workspace (read-only).",
                         {"type": "object", "properties": path_arg, "required": ["path"]}, read_file)
    server.register_tool("git_status", "Show git status of the Keelway workspace.", {"type": "object", "properties": {}}, git_status)
    server.register_tool("git_diff", "Show the git diff of the workspace, optionally for one path.",
                         {"type": "object", "properties": path_arg}, git_diff)
    return server


mcp_server = MCPProtocolServer()
