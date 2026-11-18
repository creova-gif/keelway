"""
Workspace Model Context Protocol Registry & Governed Tool Bridge (`PlatformMcpRegistry`).

Persists workspace-scoped external MCP servers (`sse` / `stdio`) in crash-safe SQLite WAL mode
(`platform_mcp_servers`), wraps `MCPProtocolServer` (`PROTOCOL_VERSION = "2025-06-18"`), exposes
5 built-in sovereign workspace/governance/vault tools on `"keelway-core-mcp"`, enforces SSRF and
stdio command-injection defenses, and scrubs all tool outputs through `core.security.redact`
with SHA-256 execution receipts.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple, TypeVar, Union

from core.orchestration.mcp import MCPProtocolServer, PROTOCOL_VERSION
from core.platform.mcp_client import McpClientError, call_remote_tool
from core.platform.rbac_webhooks import validate_webhook_url
from core.platform.vault import LocalSecretVault, _resolve_sqlite_target
from core.security.redact import redact_payload, redact_text
from core.storage.ast_index import PythonASTExtractor, TypeScriptRegexExtractor
from core.storage.workspace_fs import WorkspaceFilesystem, WorkspaceSecurityError

BUILTIN_MCP_SERVER_ID = "keelway-core-mcp"
BUILTIN_MCP_SERVER_NAME = "Keelway Core Workspace MCP"
BUILTIN_MCP_ENDPOINT = "builtin://workspace"
VALID_MCP_TRANSPORTS = frozenset({"sse", "stdio"})
RESTRICTED_PRIVACY_TIERS = frozenset({"private", "air_gap", "airgap", "restricted"})
VALID_PRIVACY_TIERS = frozenset({"standard", "public", "internal", "private", "air_gap", "airgap", "restricted"})

_SERVER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_TOOL_NAME_RE = re.compile(r"^(?:\*|[A-Za-z0-9][A-Za-z0-9._:/*-]{0,127})$")
_STDIO_FORBIDDEN_CHARS = (";", "|", "&", "$", "`", ">", "<", "\n", "\r", "\x00")
_KEELWAY_TOKEN_RE = re.compile(r"\bkw_(?:live|test)_[A-Za-z0-9_]{12,}")
_T = TypeVar("_T")


class McpToolArgumentError(WorkspaceSecurityError, ValueError):
    """Raised when an MCP tool receives invalid or path-traversal arguments."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_coro_sync(coro_factory: Callable[[], Awaitable[_T]]) -> _T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro_factory())).result()


def redact_sensitive_text(text: str) -> Tuple[str, int]:
    """Scrub sensitive tokens via `core.security.redact.redact_text` plus `kw_live_*` keys."""
    clean, count = redact_text(text)
    matches = list(_KEELWAY_TOKEN_RE.finditer(clean))
    for match in reversed(matches):
        start, end = match.span()
        clean = clean[:start] + "[REDACTED_KEELWAY_TOKEN]" + clean[end:]
        count += 1
    return clean, count


def _scrub_mcp_result(raw_result: Any) -> Tuple[Any, bool, str]:
    clean_payload, payload_hits = redact_payload(raw_result)
    encoded = json.dumps(clean_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    scrubbed_json, text_hits = redact_sensitive_text(encoded)
    return json.loads(scrubbed_json), (payload_hits + text_hits) > 0, scrubbed_json


class PlatformMcpRegistry:
    """SQLite WAL MCP server registry & JSON-RPC `2025-06-18` tool dispatcher."""

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        workspace_root: Optional[Union[str, Path]] = None,
    ) -> None:
        self._lock = threading.RLock()
        self._db_path, connect_target = _resolve_sqlite_target(db_path)
        self._workspace_root: Optional[Path] = Path(workspace_root).expanduser().resolve() if workspace_root is not None else None
        self._created_at = _utc_now()
        self._conn = sqlite3.connect(connect_target, check_same_thread=False, timeout=30.0)
        self._conn.row_factory = sqlite3.Row
        self._closed = False
        self.mcp_server = MCPProtocolServer()
        self._tool_meta: Dict[str, Dict[str, Any]] = {}

        with self._lock:
            mode_row = self._conn.execute("PRAGMA journal_mode=WAL").fetchone()
            self._journal_mode = str(mode_row[0]).lower() if mode_row else "unknown"
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            with self._conn:
                self._conn.executescript(
                    "CREATE TABLE IF NOT EXISTS platform_mcp_servers ("
                    "id TEXT NOT NULL, workspace_id TEXT NOT NULL, name TEXT NOT NULL, "
                    "transport TEXT NOT NULL, endpoint TEXT NOT NULL, allowed_tools_json TEXT NOT NULL, "
                    "status TEXT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(workspace_id, id)); "
                    "CREATE INDEX IF NOT EXISTS idx_platform_mcp_servers_ws ON platform_mcp_servers(workspace_id);"
                )
        self._register_builtin_tools()

    @property
    def db_path(self) -> Union[str, Path]:
        return self._db_path

    @property
    def journal_mode(self) -> str:
        return self._journal_mode

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._conn.close()
                self._closed = True

    def _fs(self) -> WorkspaceFilesystem:
        return WorkspaceFilesystem(str(self._workspace_root) if self._workspace_root is not None else None)

    def register_tool(
        self,
        name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
        *,
        mutating: bool = False,
        server_id: str = BUILTIN_MCP_SERVER_ID,
    ) -> None:
        self.mcp_server.register_tool(name, description, parameters_schema, handler)
        self._tool_meta[name] = {"mutating": bool(mutating), "server_id": server_id, "builtin": server_id == BUILTIN_MCP_SERVER_ID}

    def _register_builtin_tools(self) -> None:
        async def _tool_list_files(args: Dict[str, Any]) -> Dict[str, Any]:
            subpath = str(args.get("subpath", ".") if args.get("subpath") is not None else ".").strip() or "."
            raw_limit = args.get("limit", 25)
            if isinstance(raw_limit, bool) or not isinstance(raw_limit, int) or raw_limit < 1 or raw_limit > 500:
                raise McpToolArgumentError("Parameter 'limit' must be an integer between 1 and 500.")
            if "\x00" in subpath or ".." in Path(subpath).parts:
                raise McpToolArgumentError(f"Path traversal blocked in subpath '{subpath}'.")
            fs = self._fs()
            try:
                fs.resolve_safe_path(subpath)
                matched = fs.list_files(subpath)
            except WorkspaceSecurityError as exc:
                raise McpToolArgumentError(str(exc)) from exc
            sliced = matched[:raw_limit]
            return {"subpath": subpath, "limit": raw_limit, "count": len(sliced), "files": sliced, "mutating": False}

        async def _tool_search_symbols(args: Dict[str, Any]) -> Dict[str, Any]:
            query = str(args.get("query", "") or "").strip()
            raw_limit = args.get("limit", 15)
            if isinstance(raw_limit, bool) or not isinstance(raw_limit, int) or raw_limit < 1 or raw_limit > 200:
                raise McpToolArgumentError("Parameter 'limit' must be an integer between 1 and 200.")
            fs = self._fs()
            tree = fs.get_file_tree(".", max_depth=4, max_files=150)
            q_low = query.lower()
            symbols_out: List[Dict[str, Any]] = []

            def _walk(node: Dict[str, Any]) -> None:
                if len(symbols_out) >= raw_limit:
                    return
                if node.get("type") == "file":
                    rel = str(node.get("path") or "")
                    if not rel.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                        return
                    try:
                        fdata = fs.read_file(rel, max_bytes=500_000)
                    except Exception:
                        return
                    if fdata.get("is_binary"):
                        return
                    src = str(fdata.get("content") or "")
                    extracted = (
                        PythonASTExtractor.extract_symbols(src, rel)
                        if rel.endswith(".py")
                        else TypeScriptRegexExtractor.extract_symbols(src, rel)
                    )
                    for sym in extracted:
                        hay = f"{sym.name} {sym.signature} {sym.file_path}".lower()
                        if not q_low or q_low in hay:
                            symbols_out.append({
                                "name": sym.name, "kind": sym.kind, "file_path": sym.file_path,
                                "line_number": sym.line_number, "signature": sym.signature, "parent_symbol": sym.parent_symbol,
                            })
                            if len(symbols_out) >= raw_limit:
                                return
                else:
                    for child in node.get("children", []):
                        _walk(child)

            _walk(tree.get("tree", {}))
            return {"query": query, "count": len(symbols_out), "symbols": symbols_out, "mutating": False}

        async def _tool_git_status(_args: Dict[str, Any]) -> Dict[str, Any]:
            fs = self._fs()
            status = fs.get_git_status()
            return {
                "is_git": bool(status.get("is_git", False)),
                "branch": str(status.get("branch", "")),
                "clean": bool(status.get("clean", True)),
                "changed_count": len(status.get("files", [])),
                "files": list(status.get("files", []))[:50],
                "workspace": fs.root.name,
                "mutating": False,
            }

        async def _tool_check_airgap(args: Dict[str, Any]) -> Dict[str, Any]:
            tier = str(args.get("privacy_tier", "standard") or "standard").strip().lower()
            if tier not in VALID_PRIVACY_TIERS:
                raise McpToolArgumentError(f"Unsupported privacy_tier '{tier}'. Expected {sorted(VALID_PRIVACY_TIERS)}.")
            preview = str(args.get("prompt_preview", "") or "")
            clean_preview, redactions = redact_sensitive_text(preview)
            requires_local = tier in RESTRICTED_PRIVACY_TIERS
            return {
                "privacy_tier": tier,
                "cloud_egress_allowed": not requires_local,
                "required_routing": "open_weight" if requires_local else "hybrid",
                "local_open_weight_required": requires_local,
                "prompt_preview": clean_preview[:200],
                "prompt_redactions": redactions,
                "mutating": False,
            }

        async def _tool_vault_list_metadata(args: Dict[str, Any]) -> Dict[str, Any]:
            ws = str(args.get("workspace_id", "default") or "default").strip()
            if not ws:
                raise McpToolArgumentError("Parameter 'workspace_id' must be non-empty.")
            vault = LocalSecretVault(db_path=self._db_path)
            try:
                raw_items = vault.list_secrets(workspace_id=ws)
            finally:
                vault.close()
            sanitized = [
                {
                    "workspace_id": m["workspace_id"], "name": m["name"], "namespace": m["namespace"],
                    "masked_preview": m["masked_preview"], "fingerprint_sha256": m["fingerprint_sha256"],
                    "version": m["version"], "encryption": m["encryption"], "updated_at": m["updated_at"],
                }
                for m in raw_items
            ]
            return {"workspace_id": ws, "count": len(sanitized), "secrets": sanitized, "mutating": False}

        self.register_tool(
            "workspace.list_files",
            "List workspace files safely with path-traversal protection.",
            {"type": "object", "properties": {"subpath": {"type": "string", "default": "."}, "limit": {"type": "integer", "default": 25}}},
            _tool_list_files,
        )
        self.register_tool(
            "workspace.search_symbols",
            "Search Python AST and TypeScript symbols across the workspace.",
            {"type": "object", "properties": {"query": {"type": "string", "default": ""}, "limit": {"type": "integer", "default": 15}}},
            _tool_search_symbols,
        )
        self.register_tool(
            "workspace.git_status",
            "Inspect safe working-tree Git branch and modified file status.",
            {"type": "object", "properties": {}},
            _tool_git_status,
        )
        self.register_tool(
            "governance.check_airgap",
            "Evaluate privacy tier egress policy and enforce local open_weight routing for private/air_gap/restricted.",
            {"type": "object", "properties": {"prompt_preview": {"type": "string", "default": ""}, "privacy_tier": {"type": "string", "default": "standard"}}},
            _tool_check_airgap,
        )
        self.register_tool(
            "vault.list_metadata",
            "Return sanitized AES-256-GCM secret metadata for a workspace without exposing plaintext.",
            {"type": "object", "properties": {"workspace_id": {"type": "string", "default": "default"}}},
            _tool_vault_list_metadata,
        )

    def _builtin_server_entry(self, ws: str) -> Dict[str, Any]:
        builtin_names = [n for n, m in self._tool_meta.items() if m.get("builtin")]
        return {
            "id": BUILTIN_MCP_SERVER_ID,
            "workspace_id": ws,
            "name": BUILTIN_MCP_SERVER_NAME,
            "transport": "builtin",
            "endpoint": BUILTIN_MCP_ENDPOINT,
            "builtin": True,
            "status": "healthy",
            "tools_count": len(builtin_names),
            "allowed_tools": builtin_names,
            "protocol_version": PROTOCOL_VERSION,
            "created_at": self._created_at,
        }

    @staticmethod
    def _validate_stdio_endpoint(endpoint: str) -> str:
        clean = str(endpoint or "").strip()
        if not clean or len(clean) > 1024:
            raise ValueError("MCP stdio 'endpoint' must be a non-empty command string.")
        if any(ch in clean for ch in _STDIO_FORBIDDEN_CHARS):
            raise ValueError("MCP stdio 'endpoint' contains prohibited shell metacharacters.")
        tokens = clean.split()
        if any(".." in tok or ".." in Path(tok).parts for tok in tokens):
            raise ValueError("MCP stdio 'endpoint' must not contain '..' path traversal.")
        return clean

    def register_server(
        self,
        workspace_id: str,
        server_id: str,
        name: str,
        transport: str,
        endpoint: str,
        allowed_tools: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        ws = str(workspace_id or "").strip()
        clean_id = str(server_id or "").strip()
        clean_name = str(name or "").strip()
        clean_transport = str(transport or "").strip().lower()
        if not ws:
            raise ValueError("MCP 'workspace_id' must be non-empty.")
        if clean_id == BUILTIN_MCP_SERVER_ID:
            raise ValueError(f"Built-in MCP server '{BUILTIN_MCP_SERVER_ID}' cannot be overwritten.")
        if not _SERVER_ID_RE.match(clean_id):
            raise ValueError("MCP 'server_id' must be 1..128 alphanumeric/dot/hyphen/underscore characters.")
        if not clean_name:
            raise ValueError("MCP server 'name' must be non-empty.")
        if clean_transport not in VALID_MCP_TRANSPORTS:
            raise ValueError(f"Unsupported MCP transport '{clean_transport}'. Expected one of {sorted(VALID_MCP_TRANSPORTS)}.")

        clean_endpoint = validate_webhook_url(endpoint) if clean_transport == "sse" else self._validate_stdio_endpoint(endpoint)
        clean_tools: List[str] = []
        for raw_tool in allowed_tools or []:
            t_str = str(raw_tool or "").strip()
            if t_str:
                if not _TOOL_NAME_RE.match(t_str):
                    raise ValueError(f"Invalid allowed tool identifier '{t_str}'.")
                clean_tools.append(t_str)

        now = _utc_now()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO platform_mcp_servers VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(workspace_id, id) DO UPDATE SET name=excluded.name, transport=excluded.transport, "
                "endpoint=excluded.endpoint, allowed_tools_json=excluded.allowed_tools_json, status=excluded.status",
                (clean_id, ws, clean_name, clean_transport, clean_endpoint, json.dumps(clean_tools, separators=(",", ":")), "registered", now),
            )
        return {
            "id": clean_id, "workspace_id": ws, "name": clean_name, "transport": clean_transport,
            "endpoint": clean_endpoint, "allowed_tools": clean_tools, "tools_count": len(clean_tools),
            "builtin": False, "status": "registered", "protocol_version": PROTOCOL_VERSION, "created_at": now,
        }

    def list_servers(self, workspace_id: str = "default") -> List[Dict[str, Any]]:
        ws = str(workspace_id or "default").strip() or "default"
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, workspace_id, name, transport, endpoint, allowed_tools_json, status, created_at "
                "FROM platform_mcp_servers WHERE workspace_id=? ORDER BY rowid ASC",
                (ws,),
            ).fetchall()
        custom = []
        for r in rows:
            allowed = json.loads(str(r["allowed_tools_json"]))
            custom.append({
                "id": str(r["id"]), "workspace_id": str(r["workspace_id"]), "name": str(r["name"]),
                "transport": str(r["transport"]), "endpoint": str(r["endpoint"]), "allowed_tools": allowed,
                "tools_count": len(allowed), "builtin": False, "status": str(r["status"]),
                "protocol_version": PROTOCOL_VERSION, "created_at": str(r["created_at"]),
            })
        return [self._builtin_server_entry(ws), *custom]

    def delete_server(self, workspace_id: str, server_id: str) -> Dict[str, Any]:
        ws = str(workspace_id or "default").strip() or "default"
        clean_id = str(server_id or "").strip()
        if clean_id == BUILTIN_MCP_SERVER_ID:
            raise ValueError(f"Built-in MCP server '{BUILTIN_MCP_SERVER_ID}' cannot be deleted.")
        if not clean_id:
            raise KeyError("MCP server '' not found.")
        with self._lock, self._conn:
            cur = self._conn.execute(
                "DELETE FROM platform_mcp_servers WHERE workspace_id=? AND id=?", (ws, clean_id)
            )
            if cur.rowcount == 0:
                raise KeyError(f"MCP server '{clean_id}' not found in workspace '{ws}'.")
        return {"deleted": True, "id": clean_id, "workspace_id": ws}

    def list_tools(self, workspace_id: str = "default") -> Dict[str, Any]:
        ws = str(workspace_id or "default").strip() or "default"
        rpc_resp = _run_coro_sync(
            lambda: self.mcp_server.handle_jsonrpc_request({"jsonrpc": "2.0", "id": "list-1", "method": "tools/list"})
        )
        raw_tools = (rpc_resp or {}).get("result", {}).get("tools", [])
        tools: List[Dict[str, Any]] = []
        for item in raw_tools:
            meta = self._tool_meta.get(item["name"], {"mutating": False, "server_id": BUILTIN_MCP_SERVER_ID, "builtin": True})
            is_mutating = bool(meta["mutating"])
            tools.append({
                "name": item["name"],
                "description": item["description"],
                "inputSchema": item["inputSchema"],
                "parameters_schema": item["inputSchema"],
                "input_schema": item["inputSchema"],
                "mutating": is_mutating,
                "read_only": not is_mutating,
                "server_id": meta["server_id"],
                "builtin": bool(meta["builtin"]),
            })
        return {"workspace_id": ws, "count": len(tools), "total": len(tools), "protocol_version": PROTOCOL_VERSION, "tools": tools}

    def _resolve_remote_server(self, ws: str, tool_name: str) -> Optional[Dict[str, Any]]:
        """Find the registered external server allowed to serve `tool_name`.

        Matches exact tool names in `allowed_tools_json`, or the `*` wildcard.
        Returns the server row dict, or None when no server claims the tool.
        Raises ValueError when multiple servers claim the same tool name.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, workspace_id, name, transport, endpoint, allowed_tools_json, status, created_at "
                "FROM platform_mcp_servers WHERE workspace_id=? ORDER BY rowid ASC",
                (ws,),
            ).fetchall()
        matches: List[Dict[str, Any]] = []
        for r in rows:
            try:
                allowed = json.loads(str(r["allowed_tools_json"]))
            except ValueError:
                continue
            if isinstance(allowed, list) and (tool_name in allowed or "*" in allowed):
                matches.append({
                    "id": str(r["id"]), "workspace_id": str(r["workspace_id"]),
                    "name": str(r["name"]), "transport": str(r["transport"]),
                    "endpoint": str(r["endpoint"]), "status": str(r["status"]),
                })
        if not matches:
            return None
        if len(matches) > 1:
            ids = ", ".join(sorted(m["id"] for m in matches))
            raise ValueError(f"MCP tool '{tool_name}' is claimed by multiple servers ({ids}); qualify or narrow allowed_tools.")
        return matches[0]

    def call_tool(
        self,
        workspace_id: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ws = str(workspace_id or "default").strip()
        clean_tool = str(tool_name or "").strip()
        if not ws:
            raise ValueError("MCP 'workspace_id' must be non-empty.")
        if arguments is not None and not isinstance(arguments, dict):
            raise ValueError("MCP tool 'arguments' must be a JSON object.")
        call_args = dict(arguments or {})
        remote_server: Optional[Dict[str, Any]] = None
        if clean_tool not in self.mcp_server.tools:
            remote_server = self._resolve_remote_server(ws, clean_tool)
        if clean_tool not in self.mcp_server.tools and remote_server is None:
            raise KeyError(f"MCP tool '{clean_tool}' is not registered.")
        if clean_tool == "vault.list_metadata" and "workspace_id" not in call_args:
            call_args["workspace_id"] = ws

        t0 = time.perf_counter()

        if remote_server is not None:
            try:
                raw_res = call_remote_tool(
                    str(remote_server["transport"]),
                    str(remote_server["endpoint"]),
                    clean_tool,
                    call_args,
                )
            except McpClientError as exc:
                raise McpToolArgumentError(f"Remote MCP tool '{clean_tool}' failed: {exc}") from exc
        else:

            async def _invoke() -> Dict[str, Any]:
                rpc = await self.mcp_server.handle_jsonrpc_request(
                    {"jsonrpc": "2.0", "id": "call-1", "method": "tools/call", "params": {"name": clean_tool, "arguments": call_args}}
                )
                res_obj = (rpc or {}).get("result", {})
                content = res_obj.get("content", [])
                text = str(content[0]["text"]) if content else "{}"
                if res_obj.get("isError"):
                    raise McpToolArgumentError(text.removeprefix("Tool execution failed: "))
                return json.loads(text)

            raw_res = _run_coro_sync(_invoke)

        duration_ms = round((time.perf_counter() - t0) * 1000.0, 3)
        scrubbed_result, was_redacted, scrubbed_json = _scrub_mcp_result(raw_res)
        receipt_input = json.dumps(
            {"protocol_version": PROTOCOL_VERSION, "result": scrubbed_json, "tool_name": clean_tool, "workspace_id": ws},
            sort_keys=True, separators=(",", ":"),
        )
        receipt_sha256 = hashlib.sha256(receipt_input.encode("utf-8")).hexdigest()
        return {
            "ok": True,
            "workspace_id": ws,
            "tool_name": clean_tool,
            "protocol_version": PROTOCOL_VERSION,
            "redacted": was_redacted,
            "duration_ms": duration_ms,
            "result": scrubbed_result,
            "receipt_sha256": receipt_sha256,
        }


platform_mcp_registry = PlatformMcpRegistry()
