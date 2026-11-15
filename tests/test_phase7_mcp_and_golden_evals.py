"""
Phase 7A + 7B Verification Suite — Workspace MCP Registry (`2025-06-18`), Built-in Sovereign Tools,
DLP Secret Redaction, 16-Case Production Golden Evaluation & Adversarial Red-Team Suite,
FastAPI `/v1/platform/mcp/*` + `/v1/platform/evals/*` RBAC Routes, and Sovereign CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
from typing import Any, Dict

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from cli import build_parser, main as cli_main
from core.api.platform_mcp_routes import (
    get_golden_eval_suite,
    get_mcp_registry,
    router as platform_mcp_router,
)
from core.api.platform_runtime_routes import (
    get_rbac_controller,
    router as platform_runtime_router,
)
from core.eval.golden_suite import EVAL_CATEGORY_ORDER, GoldenEvalSuite
from core.main import app as live_app
from core.orchestration.mcp import PROTOCOL_VERSION
from core.platform.execution_stream import LiveExecutionStreamer
from core.platform.mcp_registry import BUILTIN_MCP_SERVER_ID, PlatformMcpRegistry
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.vault import LocalSecretVault
from core.security.auth import launch_token
from core.storage.workspace_fs import WorkspaceSecurityError


def test_mcp_registry_crud_persistence_and_ssrf_stdio_guards(tmp_path: Path) -> None:
    db_file = tmp_path / "mcp_reg.db"
    reg = PlatformMcpRegistry(db_path=db_file, workspace_root=tmp_path)
    assert reg.journal_mode == "wal"

    initial = reg.list_servers("default")
    assert len(initial) == 1
    builtin = initial[0]
    assert builtin["id"] == BUILTIN_MCP_SERVER_ID
    assert builtin["name"] == "Keelway Core Workspace MCP"
    assert builtin["transport"] == "builtin"
    assert builtin["endpoint"] == "builtin://workspace"
    assert builtin["builtin"] is True
    assert builtin["status"] == "healthy"
    assert builtin["tools_count"] == 5

    sse_srv = reg.register_server(
        "default",
        "linear-sse",
        "Linear Issue MCP",
        "sse",
        "https://mcp.linear.example/sse",
        allowed_tools=["issues.list", "issues.get"],
    )
    assert sse_srv["id"] == "linear-sse" and sse_srv["tools_count"] == 2

    stdio_srv = reg.register_server(
        "default",
        "local-sqlite-mcp",
        "Local SQLite MCP",
        "stdio",
        "uvx mcp-server-sqlite --readonly",
        allowed_tools=["sql.query"],
    )
    assert stdio_srv["transport"] == "stdio" and stdio_srv["builtin"] is False

    reg.close()
    reopened = PlatformMcpRegistry(db_path=db_file, workspace_root=tmp_path)
    listed = reopened.list_servers("default")
    assert [s["id"] for s in listed] == [BUILTIN_MCP_SERVER_ID, "linear-sse", "local-sqlite-mcp"]

    # Built-in server cannot be overwritten or deleted
    with pytest.raises(ValueError):
        reopened.register_server("default", BUILTIN_MCP_SERVER_ID, "Fake", "sse", "https://mcp.example/sse")
    with pytest.raises(ValueError):
        reopened.delete_server("default", BUILTIN_MCP_SERVER_ID)
    with pytest.raises(ValueError):
        reopened.register_server("default", "bad-transport", "Bad", "websocket", "wss://mcp.example/ws")

    # SSRF & cleartext non-loopback rejection on SSE transport
    for bad_sse in (
        "http://169.254.169.254/latest/meta-data/",
        "https://[::ffff:169.254.169.254]/latest",
        "https://10.12.34.56/mcp",
        "http://remote-mcp.example.com/sse",
    ):
        with pytest.raises(ValueError):
            reopened.register_server("default", "ssrf-srv", "SSRF", "sse", bad_sse)

    # Shell metacharacters & traversal rejection on stdio transport
    for bad_stdio in (
        "",
        "npx server; rm -rf /",
        "npx server | cat /etc/passwd",
        "npx server && whoami",
        "npx $SECRET_CMD",
        "npx `id`",
        "npx server > /tmp/out",
        "npx server < /etc/hosts",
        "npx server\nwhoami",
        "../../bin/evil-mcp",
    ):
        with pytest.raises(ValueError):
            reopened.register_server("default", "inj-srv", "Inj", "stdio", bad_stdio)

    deleted = reopened.delete_server("default", "linear-sse")
    assert deleted == {"deleted": True, "id": "linear-sse", "workspace_id": "default"}
    with pytest.raises(KeyError):
        reopened.delete_server("default", "linear-sse")
    reopened.close()


def test_mcp_builtin_tools_traversal_vault_safety_and_secret_redaction(tmp_path: Path) -> None:
    ws_dir = tmp_path / "sample_repo"
    ws_dir.mkdir()
    (ws_dir / "pkg").mkdir()
    (ws_dir / "pkg" / "engine.py").write_text(
        "class QuantumRouter:\n"
        "    def select_lane(self, tier: str) -> str:\n"
        "        return tier\n",
        encoding="utf-8",
    )
    (ws_dir / "pkg" / "ui.ts").write_text(
        "export function renderMcpBadge(name: string) { return name; }\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=str(ws_dir), check=True)

    db_file = tmp_path / "mcp_tools.db"
    raw_secret = "sk-proj-UltraSecretVaultCredential9876543210"
    vault = LocalSecretVault(db_path=db_file, master_key="phase7-test-master")
    vault.put_secret("ws-alpha", "OPENAI_API_KEY", raw_secret, namespace="byom")
    vault.close()

    reg = PlatformMcpRegistry(db_path=db_file, workspace_root=ws_dir)
    try:
        tools_info = reg.list_tools("ws-alpha")
        assert tools_info["protocol_version"] == PROTOCOL_VERSION == "2025-06-18"
        assert tools_info["count"] == 5
        tool_names = {t["name"] for t in tools_info["tools"]}
        assert tool_names == {
            "workspace.list_files",
            "workspace.search_symbols",
            "workspace.git_status",
            "governance.check_airgap",
            "vault.list_metadata",
        }
        assert all(t["mutating"] is False for t in tools_info["tools"])

        # 1. workspace.list_files + path traversal block
        lf = reg.call_tool("ws-alpha", "workspace.list_files", {"subpath": "pkg", "limit": 10})
        assert lf["ok"] is True and len(lf["receipt_sha256"]) == 64
        assert "pkg/engine.py" in lf["result"]["files"]

        with pytest.raises(ValueError) as exc_info:
            reg.call_tool("ws-alpha", "workspace.list_files", {"subpath": "../../etc/passwd"})
        assert isinstance(exc_info.value, WorkspaceSecurityError)

        # 2. workspace.search_symbols (Python AST + TS)
        py_sym = reg.call_tool("ws-alpha", "workspace.search_symbols", {"query": "QuantumRouter"})
        assert any(s["name"] == "QuantumRouter" and s["kind"] == "class" for s in py_sym["result"]["symbols"])
        ts_sym = reg.call_tool("ws-alpha", "workspace.search_symbols", {"query": "renderMcpBadge"})
        assert any(s["name"] == "renderMcpBadge" for s in ts_sym["result"]["symbols"])

        # 3. workspace.git_status
        gs = reg.call_tool("ws-alpha", "workspace.git_status", {})
        assert gs["result"]["is_git"] is True
        assert gs["result"]["clean"] is False
        assert gs["result"]["changed_count"] >= 1

        # 4. governance.check_airgap + prompt secret redaction
        ag_priv = reg.call_tool(
            "ws-alpha",
            "governance.check_airgap",
            {"privacy_tier": "air_gap", "prompt_preview": "Use sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"},
        )
        assert ag_priv["result"]["cloud_egress_allowed"] is False
        assert ag_priv["result"]["required_routing"] == "open_weight"
        assert "sk-ant-api03-" not in json.dumps(ag_priv)

        ag_std = reg.call_tool("ws-alpha", "governance.check_airgap", {"privacy_tier": "standard"})
        assert ag_std["result"]["cloud_egress_allowed"] is True

        # 5. vault.list_metadata never leaks plaintext
        vm = reg.call_tool("ws-alpha", "vault.list_metadata", {})
        assert vm["result"]["count"] == 1
        assert vm["result"]["secrets"][0]["name"] == "OPENAI_API_KEY"
        assert raw_secret not in json.dumps(vm)

        # Custom tool output secret redaction (OpenAI, Anthropic, kw_live_)
        leaked_oa = "sk-proj-" + "X1y2Z3a4B5c6D7e8F9g0H1i2J3k4L5m6N7o8"
        leaked_kw = "kw_live_112233_abcdef0123456789abcdef0123456789"

        async def _leaky_tool(_args: Dict[str, Any]) -> Dict[str, Any]:
            return {"stdout": f"auth={leaked_oa} keelway={leaked_kw}", "api_key": leaked_kw}

        reg.register_tool("diag.leaky", "Test redaction", {"type": "object", "properties": {}}, _leaky_tool)
        scrubbed = reg.call_tool("ws-alpha", "diag.leaky", {})
        assert scrubbed["redacted"] is True
        dumped = json.dumps(scrubbed)
        assert leaked_oa not in dumped and leaked_kw not in dumped

        with pytest.raises(KeyError):
            reg.call_tool("ws-alpha", "unknown.nonexistent_tool", {})
    finally:
        reg.close()


def test_golden_eval_suite_16_real_probes_categories_and_persistence(tmp_path: Path) -> None:
    db_file = tmp_path / "golden_evals.db"
    suite = GoldenEvalSuite(db_path=db_file)
    assert suite.journal_mode == "wal"
    assert suite.get_latest("ws-bench") == {"workspace_id": "ws-bench", "has_run": False, "latest": None}

    full = suite.run_suite(workspace_id="ws-bench", category="all")
    assert full["eval_run_id"].startswith("eval-")
    assert full["total_cases"] == 16
    assert full["passed_cases"] == 16
    assert full["failed_cases"] == 0
    assert full["pass_rate"] == 1.0
    assert full["duration_ms"] < 1000.0
    assert set(full["categories"].keys()) == set(EVAL_CATEGORY_ORDER)
    assert all(full["categories"][c]["passed"] == 4 for c in EVAL_CATEGORY_ORDER)
    assert len(full["receipt_sha256"]) == 64

    for single_cat in EVAL_CATEGORY_ORDER:
        sub = suite.run_suite(workspace_id="ws-bench", category=single_cat)
        assert sub["total_cases"] == 4 and sub["passed_cases"] == 4 and sub["pass_rate"] == 1.0

    with pytest.raises(ValueError):
        suite.run_suite(workspace_id="ws-bench", category="invalid_cat")

    suite.close()
    reopened = GoldenEvalSuite(db_path=db_file)
    latest = reopened.get_latest("ws-bench")
    assert latest["has_run"] is True
    assert latest["latest"]["category"] == "routing_pricing"
    assert latest["latest"]["passed_cases"] == 4
    reopened.close()


@pytest.mark.asyncio
async def test_fastapi_mcp_and_eval_routes_rbac_and_live_app_wiring(tmp_path: Path) -> None:
    rbac = WorkspaceRbacController(db_path=tmp_path / "api_rbac.db")
    mcp_reg = PlatformMcpRegistry(db_path=tmp_path / "api_mcp.db", workspace_root=tmp_path)
    eval_suite = GoldenEvalSuite(db_path=tmp_path / "api_evals.db")
    (tmp_path / "hello.py").write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_mcp_router)
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac
    test_app.dependency_overrides[get_mcp_registry] = lambda: mcp_reg
    test_app.dependency_overrides[get_golden_eval_suite] = lambda: eval_suite

    owner_headers = {"Authorization": f"Bearer {launch_token()}"}
    viewer_headers = {**owner_headers, "X-Keelway-Role": "viewer"}
    builder_headers = {**owner_headers, "X-Keelway-Role": "builder"}

    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
            # Viewer can read servers, tools, and latest evals
            assert (await client.get("/v1/platform/mcp/servers", headers=viewer_headers)).status_code == 200
            assert (await client.get("/v1/platform/mcp/tools", headers=viewer_headers)).status_code == 200
            lat0 = await client.get("/v1/platform/evals/latest", headers=viewer_headers)
            assert lat0.status_code == 200 and lat0.json()["has_run"] is False

            # Viewer gets 403 on write/run endpoints; builder gets 403 on webhooks:manage
            assert (
                await client.post(
                    "/v1/platform/mcp/servers",
                    headers=viewer_headers,
                    json={"id": "ext-mcp", "name": "Ext", "transport": "sse", "endpoint": "https://mcp.example/sse"},
                )
            ).status_code == 403
            assert (
                await client.post(
                    "/v1/platform/mcp/servers",
                    headers=builder_headers,
                    json={"id": "ext-mcp", "name": "Ext", "transport": "sse", "endpoint": "https://mcp.example/sse"},
                )
            ).status_code == 403
            assert (
                await client.post(
                    "/v1/platform/mcp/call",
                    headers=viewer_headers,
                    json={"tool_name": "workspace.list_files", "arguments": {"subpath": "."}},
                )
            ).status_code == 403
            assert (
                await client.post("/v1/platform/evals/golden", headers=viewer_headers, json={"category": "all"})
            ).status_code == 403

            # Owner/Admin registers & deletes MCP server + SSRF returns 400
            bad_ssrf = await client.post(
                "/v1/platform/mcp/servers",
                headers=owner_headers,
                json={"id": "bad", "name": "Bad", "transport": "sse", "endpoint": "http://169.254.169.254/latest"},
            )
            assert bad_ssrf.status_code == 400

            created = await client.post(
                "/v1/platform/mcp/servers",
                headers=owner_headers,
                json={"id": "ext-mcp", "name": "Ext MCP", "transport": "sse", "endpoint": "https://mcp.example/sse"},
            )
            assert created.status_code == 201 and created.json()["id"] == "ext-mcp"

            # Builder can invoke MCP tools and run Golden Evals
            call_ok = await client.post(
                "/v1/platform/mcp/call",
                headers=builder_headers,
                json={"tool_name": "workspace.list_files", "arguments": {"subpath": "."}},
            )
            assert call_ok.status_code == 200 and "hello.py" in call_ok.json()["result"]["files"]

            call_trav = await client.post(
                "/v1/platform/mcp/call",
                headers=builder_headers,
                json={"tool_name": "workspace.list_files", "arguments": {"subpath": "../../etc/passwd"}},
            )
            assert call_trav.status_code == 400

            call_404 = await client.post(
                "/v1/platform/mcp/call",
                headers=builder_headers,
                json={"tool_name": "missing.tool"},
            )
            assert call_404.status_code == 404

            eval_resp = await client.post(
                "/v1/platform/evals/golden",
                headers=builder_headers,
                json={"workspace_id": "default", "category": "security_redteam"},
            )
            assert eval_resp.status_code == 200 and eval_resp.json()["passed_cases"] == 4

            lat1 = await client.get("/v1/platform/evals/latest", headers=viewer_headers)
            assert lat1.status_code == 200 and lat1.json()["has_run"] is True

            assert (await client.delete("/v1/platform/mcp/servers/keelway-core-mcp", headers=owner_headers)).status_code == 400
            assert (await client.delete("/v1/platform/mcp/servers/ext-mcp", headers=viewer_headers)).status_code == 403
            assert (await client.delete("/v1/platform/mcp/servers/ext-mcp", headers=owner_headers)).status_code == 200
            assert (await client.delete("/v1/platform/mcp/servers/ext-mcp", headers=owner_headers)).status_code == 404

        live_paths = live_app.openapi()["paths"]
        for expected_path in (
            "/v1/platform/mcp/servers",
            "/v1/platform/mcp/servers/{server_id}",
            "/v1/platform/mcp/tools",
            "/v1/platform/mcp/call",
            "/v1/platform/evals/golden",
            "/v1/platform/evals/latest",
        ):
            assert expected_path in live_paths
    finally:
        mcp_reg.close()
        eval_suite.close()
        rbac.close()


def test_cli_mcp_eval_suite_and_execution_stream_workspace_enrichment(capsys, tmp_path: Path) -> None:
    db_file = str(tmp_path / "cli_p7.db")
    ws_dir = tmp_path / "exec_ws"
    ws_dir.mkdir()
    (ws_dir / "a.py").write_text("x = 1\n", encoding="utf-8")
    (ws_dir / "b.py").write_text("y = 2\n", encoding="utf-8")

    # Standalone `cli.py mcp --workspace ...` stdio parser remains intact
    parsed_stdio = build_parser().parse_args(["mcp", "--workspace", str(ws_dir)])
    assert parsed_stdio.command == "mcp" and getattr(parsed_stdio, "mcp_command", None) is None

    assert cli_main(["mcp", "servers", "--workspace-id", "ws-cli", "--db-path", db_file, "--json"]) == 0
    srv_json = json.loads(capsys.readouterr().out)
    assert srv_json["count"] == 1 and srv_json["servers"][0]["id"] == BUILTIN_MCP_SERVER_ID

    assert cli_main(["mcp", "tools", "--workspace-id", "ws-cli", "--db-path", db_file, "--json"]) == 0
    tools_json = json.loads(capsys.readouterr().out)
    assert tools_json["count"] == 5 and tools_json["protocol_version"] == "2025-06-18"

    assert (
        cli_main(
            [
                "mcp",
                "--workspace",
                str(ws_dir),
                "call",
                "workspace.list_files",
                "--args",
                '{"subpath":"."}',
                "--workspace-id",
                "ws-cli",
                "--db-path",
                db_file,
                "--json",
            ]
        )
        == 0
    )
    call_json = json.loads(capsys.readouterr().out)
    assert call_json["ok"] is True and sorted(call_json["result"]["files"]) == ["a.py", "b.py"]

    assert cli_main(["mcp", "call", "missing.tool", "--db-path", db_file, "--json"]) == 1
    capsys.readouterr()

    assert cli_main(["eval-suite", "--category", "all", "--workspace-id", "ws-cli", "--db-path", db_file, "--json"]) == 0
    eval_json = json.loads(capsys.readouterr().out)
    assert eval_json["total_cases"] == 16 and eval_json["passed_cases"] == 16

    # LiveExecutionStreamer workspace_root enrichment + backward compatibility
    streamer = LiveExecutionStreamer(db_path=tmp_path / "stream_ws.db")
    try:
        enriched = streamer.start_run("default", "agent", "code-architect", "Inspect repo", workspace_root=ws_dir)
        assert enriched["events"][1]["step"] == "inspect_context"
        assert enriched["events"][1]["workspace_file_count"] == 2

        plain = streamer.start_run("default", "agent", "code-architect", "Inspect without root")
        assert plain["events"][1]["step"] == "inspect_context"
        assert "workspace_file_count" not in plain["events"][1]
    finally:
        streamer.close()
