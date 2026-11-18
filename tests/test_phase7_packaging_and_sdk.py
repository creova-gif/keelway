"""
Phase 7 Packaging, Zero-Friction Distribution & Tri-SDK Parity Verification Suite.

Verifies:
1. `pyproject.toml` `v1.0.0` metadata and `[tool.setuptools.package-data]` glob coverage for
   both `core/studio/` and `core/dev_app_dist/` compiled SPA assets on disk.
2. `scripts/install.sh` zero-write `--dry-run --json` plan, `--help` examples, and deterministic exit codes.
3. `Formula/keelway.rb` Homebrew `Language::Python::Virtualenv` formula (`Apache-2.0`, `python@3.12`).
4. 100% sync (`KeelwayClient.platform`) and async (`AsyncKeelwayClient.platform`) SDK parity across
   all 7 Phase 7 `/v1/platform/mcp/*` and `/v1/platform/evals/*` endpoints via `httpx.MockTransport`.
"""

from __future__ import annotations

import inspect
import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import unquote

import httpx
import pytest

from core.sdk import (
    AsyncKeelwayClient,
    AsyncPlatformClient,
    KeelwayClient,
    KeelwayError,
    PermissionDeniedError,
    SyncPlatformClient,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_package_data_files(pkg_dir: Path, patterns: List[str]) -> List[Path]:
    matched: set[Path] = set()
    for pattern in patterns:
        for candidate in pkg_dir.glob(pattern):
            if candidate.is_file():
                matched.add(candidate.resolve())
    return sorted(matched)


def test_pyproject_wheel_package_data_resolves_studio_and_dev_app_assets() -> None:
    pyproject_path = REPO_ROOT / "pyproject.toml"
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert data["project"]["name"] == "keelway"
    assert data["project"]["version"] == "1.1.0"

    core_patterns = data["tool"]["setuptools"]["package-data"]["core"]
    for required in (
        "studio/*.html",
        "studio/assets/*",
        "studio/assets/**/*",
        "dev_app_dist/*.html",
        "dev_app_dist/assets/*",
        "dev_app_dist/assets/**/*",
    ):
        assert required in core_patterns

    resolved = _resolve_package_data_files(REPO_ROOT / "core", core_patterns)
    rel_paths = {p.relative_to(REPO_ROOT / "core").as_posix() for p in resolved}

    assert "studio/index.html" in rel_paths
    assert "dev_app_dist/index.html" in rel_paths
    assert any(p.startswith("dev_app_dist/assets/") and p.endswith(".js") for p in rel_paths)
    assert any(p.startswith("dev_app_dist/assets/") and p.endswith(".css") for p in rel_paths)


def test_install_script_dry_run_json_zero_writes_and_cli_hygiene(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "install.sh"
    assert script.is_file()
    assert os.access(script, os.X_OK), "scripts/install.sh must be executable"

    help_proc = subprocess.run(
        [str(script), "--help"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_proc.returncode == 0
    assert "Examples:" in help_proc.stdout
    assert "--dry-run" in help_proc.stdout
    assert "--prefix" in help_proc.stdout
    assert "--venv" in help_proc.stdout
    assert "--json" in help_proc.stdout

    planned_prefix = tmp_path / "isolated-prefix"
    planned_venv = tmp_path / "isolated-venv"
    dry_proc = subprocess.run(
        [
            str(script),
            "--dry-run",
            "--json",
            "--prefix",
            str(planned_prefix),
            "--venv",
            str(planned_venv),
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert dry_proc.returncode == 0, dry_proc.stderr
    assert not planned_prefix.exists(), "--dry-run must perform zero filesystem writes"
    assert not planned_venv.exists(), "--dry-run must not create venv directory"

    plan = json.loads(dry_proc.stdout)
    assert plan["ok"] is True
    assert plan["dry_run"] is True
    assert plan["status"] == "planned"
    assert plan["venv_dir"] == str(planned_venv)
    assert plan["binary_path"] == f"{planned_prefix}/bin/keelway"
    assert "keelway dev" in plan["quickstart"]
    assert "keelway doctor" in plan["quickstart"]

    bad_flag = subprocess.run(
        [str(script), "--nonexistent-flag", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad_flag.returncode == 2
    assert json.loads(bad_flag.stdout)["ok"] is False

    bad_py_env = {**os.environ, "KEELWAY_PYTHON": str(tmp_path / "missing-python")}
    bad_py = subprocess.run(
        [str(script), "--dry-run", "--json"],
        cwd=str(REPO_ROOT),
        env=bad_py_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad_py.returncode == 3
    assert json.loads(bad_py.stdout)["exit_code"] == 3


def test_homebrew_formula_structure_and_syntax() -> None:
    formula = REPO_ROOT / "Formula" / "keelway.rb"
    assert formula.is_file()
    content = formula.read_text(encoding="utf-8")

    assert "class Keelway < Formula" in content
    assert "include Language::Python::Virtualenv" in content
    assert "https://github.com/creova-gif/keelway.git" in content
    assert 'license "Apache-2.0"' in content
    assert 'depends_on "python@3.12"' in content
    assert 'system "#{bin}/keelway", "--help"' in content

    ruby_bin = shutil.which("ruby")
    if ruby_bin:
        chk = subprocess.run([ruby_bin, "-c", str(formula)], capture_output=True, text=True, check=False)
        assert chk.returncode == 0, chk.stderr


def _make_phase7_mock_transport() -> Tuple[httpx.MockTransport, List[Dict[str, Any]]]:
    recorded: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else None
        raw_path = request.url.raw_path.decode("utf-8").split("?", 1)[0]
        path = request.url.path
        params = dict(request.url.params)
        recorded.append(
            {
                "method": request.method,
                "path": path,
                "raw_path": raw_path,
                "params": params,
                "headers": dict(request.headers),
                "json": body,
            }
        )

        if request.method == "GET" and path == "/v1/platform/mcp/servers":
            return httpx.Response(
                200,
                json={
                    "workspace_id": params.get("workspace_id", "default"),
                    "servers": [{"id": "keelway-core-mcp", "transport": "builtin", "builtin": True}],
                    "total": 1,
                },
            )
        if request.method == "POST" and path == "/v1/platform/mcp/servers":
            if "169.254.169.254" in str(body.get("endpoint", "")):
                return httpx.Response(400, json={"detail": "SSRF blocked"})
            return httpx.Response(201, json={**body, "status": "registered"})
        if request.method == "DELETE" and path.startswith("/v1/platform/mcp/servers/"):
            server_id = unquote(raw_path.removeprefix("/v1/platform/mcp/servers/"))
            return httpx.Response(
                200,
                json={"deleted": True, "server_id": server_id, "workspace_id": params.get("workspace_id", "default")},
            )
        if request.method == "GET" and path == "/v1/platform/mcp/tools":
            return httpx.Response(
                200,
                json={
                    "workspace_id": params.get("workspace_id", "default"),
                    "tools": [{"name": "workspace.list_files", "server_id": "keelway-core-mcp"}],
                    "total": 1,
                },
            )
        if request.method == "POST" and path == "/v1/platform/mcp/call":
            if request.headers.get("authorization") == "Bearer kw_live_viewer":
                return httpx.Response(403, json={"detail": "Forbidden for viewer"})
            return httpx.Response(
                200,
                json={
                    "workspace_id": body["workspace_id"],
                    "tool_name": body["tool_name"],
                    "arguments": body["arguments"],
                    "ok": True,
                    "redacted": True,
                    "receipt_sha256": "c" * 64,
                },
            )
        if request.method == "POST" and path == "/v1/platform/evals/golden":
            return httpx.Response(
                200,
                json={
                    "eval_run_id": "eval-py-01",
                    "workspace_id": body["workspace_id"],
                    "category": body["category"],
                    "passed_count": 16,
                    "total_probes": 16,
                    "pass_rate_pct": 100.0,
                },
            )
        if request.method == "GET" and path == "/v1/platform/evals/latest":
            return httpx.Response(
                200,
                json={
                    "eval_run_id": "eval-py-01",
                    "workspace_id": params.get("workspace_id", "default"),
                    "category": "all",
                    "passed_count": 16,
                    "total_probes": 16,
                    "pass_rate_pct": 100.0,
                },
            )
        return httpx.Response(404, json={"detail": f"Unhandled {request.method} {path}"})

    return httpx.MockTransport(handler), recorded


def test_python_sync_sdk_phase7_mcp_and_golden_evals() -> None:
    phase7_methods = (
        "list_mcp_servers",
        "register_mcp_server",
        "delete_mcp_server",
        "list_mcp_tools",
        "call_mcp_tool",
        "run_golden_evals",
        "get_latest_golden_evals",
    )
    for name in phase7_methods:
        sync_sig = inspect.signature(getattr(SyncPlatformClient, name))
        async_sig = inspect.signature(getattr(AsyncPlatformClient, name))
        assert list(sync_sig.parameters.values()) == list(async_sig.parameters.values())

    transport, recorded = _make_phase7_mock_transport()
    with KeelwayClient(token="kw_live_py_sync", transport=transport) as client:
        servers = client.platform.list_mcp_servers("ws-alpha")
        assert servers["workspace_id"] == "ws-alpha"
        assert recorded[-1]["headers"]["authorization"] == "Bearer kw_live_py_sync"

        with pytest.raises(KeelwayError):
            client.platform.register_mcp_server("bad", "Bad", "sse", "http://169.254.169.254/latest")

        reg = client.platform.register_mcp_server(
            "local/docs",
            "Local Docs MCP",
            "sse",
            "http://127.0.0.1:8910/sse",
            workspace_id="ws-alpha",
            allowed_tools=["docs.read"],
        )
        assert reg["status"] == "registered"
        assert recorded[-1]["json"] == {
            "id": "local/docs",
            "name": "Local Docs MCP",
            "transport": "sse",
            "endpoint": "http://127.0.0.1:8910/sse",
            "workspace_id": "ws-alpha",
            "allowed_tools": ["docs.read"],
        }

        tools = client.platform.list_mcp_tools("ws-alpha")
        assert tools["total"] == 1

        call_default = client.platform.call_mcp_tool("workspace.list_files")
        assert call_default["ok"] is True
        assert recorded[-1]["json"] == {
            "workspace_id": "default",
            "tool_name": "workspace.list_files",
            "arguments": {},
        }

        eval_res = client.platform.run_golden_evals(category="security_redteam", workspace_id="ws-alpha")
        assert eval_res["passed_count"] == 16
        assert recorded[-1]["json"] == {"workspace_id": "ws-alpha", "category": "security_redteam"}

        latest = client.platform.get_latest_golden_evals("ws-alpha")
        assert latest["eval_run_id"] == "eval-py-01"
        assert recorded[-1]["params"] == {"workspace_id": "ws-alpha"}

        deleted = client.platform.delete_mcp_server("local/docs", workspace_id="ws-alpha")
        assert deleted["deleted"] is True
        assert recorded[-1]["raw_path"] == "/v1/platform/mcp/servers/local%2Fdocs"
        assert recorded[-1]["params"] == {"workspace_id": "ws-alpha"}


async def test_python_async_sdk_phase7_mcp_and_golden_evals() -> None:
    transport, recorded = _make_phase7_mock_transport()
    async with AsyncKeelwayClient(token="kw_live_py_async", transport=transport) as client:
        assert (await client.platform.list_mcp_servers())["workspace_id"] == "default"

        reg = await client.platform.register_mcp_server(
            id="stdio-git",
            name="Git MCP",
            transport="stdio",
            endpoint="npx -y @modelcontextprotocol/server-git",
        )
        assert reg["id"] == "stdio-git"
        assert "allowed_tools" not in recorded[-1]["json"]

        assert (await client.platform.list_mcp_tools("ws-beta"))["workspace_id"] == "ws-beta"

        call_res = await client.platform.call_mcp_tool(
            "workspace.list_files",
            arguments={"pattern": "*.py"},
            workspace_id="ws-beta",
        )
        assert call_res["arguments"] == {"pattern": "*.py"}

        eval_all = await client.platform.run_golden_evals()
        assert eval_all["category"] == "all"
        assert recorded[-1]["json"] == {"workspace_id": "default", "category": "all"}

        latest = await client.platform.get_latest_golden_evals()
        assert latest["pass_rate_pct"] == 100.0

        deleted = await client.platform.delete_mcp_server("stdio-git")
        assert deleted["deleted"] is True

    viewer_transport, _ = _make_phase7_mock_transport()
    async with AsyncKeelwayClient(
        token="kw_live_viewer",
        transport=viewer_transport,
    ) as viewer_client:
        with pytest.raises(PermissionDeniedError):
            await viewer_client.platform.call_mcp_tool("workspace.list_files")


async def test_python_sdk_live_asgi_roundtrip_with_mcp_and_golden_routes(tmp_path: Path) -> None:
    from httpx import ASGITransport

    from core.api.platform_mcp_routes import get_golden_eval_suite, get_mcp_registry
    from core.api.platform_runtime_routes import get_rbac_controller
    from core.eval.golden_suite import GoldenEvalSuite
    from core.main import app
    from core.platform.mcp_registry import PlatformMcpRegistry
    from core.platform.rbac_webhooks import WorkspaceRbacController
    from core.security.auth import launch_token

    db_file = tmp_path / "phase7_live_sdk.db"
    registry = PlatformMcpRegistry(db_path=db_file)
    suite = GoldenEvalSuite(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)
    app.dependency_overrides[get_mcp_registry] = lambda: registry
    app.dependency_overrides[get_golden_eval_suite] = lambda: suite
    app.dependency_overrides[get_rbac_controller] = lambda: rbac
    try:
        async with AsyncKeelwayClient(
            base_url="http://localhost",
            token=launch_token(),
            transport=ASGITransport(app=app),
        ) as client:
            servers = await client.platform.list_mcp_servers("ws-live")
            assert servers["servers"][0]["id"] == "keelway-core-mcp"

            reg = await client.platform.register_mcp_server(
                "local-sse-docs",
                "Local Docs MCP",
                "sse",
                "http://127.0.0.1:8910/sse",
                workspace_id="ws-live",
                allowed_tools=["docs.search"],
            )
            assert reg["id"] == "local-sse-docs"

            tools = await client.platform.list_mcp_tools("ws-live")
            assert tools["count"] >= 5

            call_res = await client.platform.call_mcp_tool(
                "workspace.list_files",
                arguments={"limit": 3},
                workspace_id="ws-live",
            )
            assert call_res["ok"] is True
            assert len(call_res["receipt_sha256"]) == 64

            eval_res = await client.platform.run_golden_evals(category="workspace_ast", workspace_id="ws-live")
            assert eval_res["total_cases"] == 4
            assert eval_res["passed_cases"] == 4

            latest = await client.platform.get_latest_golden_evals("ws-live")
            assert latest["has_run"] is True
            assert latest["latest"]["eval_run_id"] == eval_res["eval_run_id"]

            deleted = await client.platform.delete_mcp_server("local-sse-docs", workspace_id="ws-live")
            assert deleted["deleted"] is True
    finally:
        app.dependency_overrides.pop(get_mcp_registry, None)
        app.dependency_overrides.pop(get_golden_eval_suite, None)
        app.dependency_overrides.pop(get_rbac_controller, None)
        registry.close()
        suite.close()
        rbac.close()
