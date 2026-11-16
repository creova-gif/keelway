"""
Phase 6C Verification Suite — Sovereign CLI Runtime (`vault`, `workspace`, `run`, `pricing-eval`)
and Python SDK `simulate_pricing` Sync + Async Parity.
"""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest

from cli import build_parser, main
from core.sdk import AsyncKeelwayClient, AsyncPlatformClient, KeelwayClient, SyncPlatformClient


def test_cli_vault_lifecycle_zero_plaintext_leak(capsys, tmp_path: Path):
    """Verify `cli.py vault <put|list|rotate|delete>` never leaks plaintext secret values."""
    db_file = str(tmp_path / "phase6_vault.db")
    secret_v1 = "sk-live-SUPER-SENSITIVE-BYOM-SECRET-987654"
    secret_v2 = "sk-live-ROTATED-ULTRA-SECRET-KEY-112233"

    # 1. Put (JSON)
    assert main(["vault", "put", "OPENAI_API_KEY", secret_v1, "--namespace", "byom", "--workspace-id", "ws-sec", "--db-path", db_file, "--json"]) == 0
    put_raw = capsys.readouterr().out
    assert secret_v1 not in put_raw
    put_meta = json.loads(put_raw)
    assert put_meta["name"] == "OPENAI_API_KEY"
    assert put_meta["masked_preview"] == "sk-l****7654"
    assert len(put_meta["fingerprint_sha256"]) == 64
    assert put_meta["version"] == 1
    assert put_meta["cipher"] == "AES-256-GCM"
    assert "secret_value" not in put_meta

    # 2. Put second secret (Human text output — also must never print plaintext)
    plugin_secret = "ghp_TopSecretGitHubPluginToken00009999"
    assert main(["vault", "put", "GH_TOKEN", plugin_secret, "--namespace", "plugin", "--workspace-id", "ws-sec", "--db-path", db_file]) == 0
    human_put = capsys.readouterr().out
    assert plugin_secret not in human_put
    assert "AES-256-GCM" in human_put and "ghp_****9999" in human_put

    # 3. List (JSON + namespace filter + human text)
    assert main(["vault", "list", "--workspace-id", "ws-sec", "--db-path", db_file, "--json"]) == 0
    list_raw = capsys.readouterr().out
    assert secret_v1 not in list_raw and plugin_secret not in list_raw
    listed = json.loads(list_raw)
    assert listed["count"] == 2
    assert all(item["cipher"] == "AES-256-GCM" for item in listed["secrets"])

    assert main(["vault", "list", "--workspace-id", "ws-sec", "--namespace", "byom", "--db-path", db_file, "--json"]) == 0
    filtered = json.loads(capsys.readouterr().out)
    assert filtered["count"] == 1 and filtered["secrets"][0]["name"] == "OPENAI_API_KEY"

    assert main(["vault", "list", "--workspace-id", "ws-sec", "--db-path", db_file]) == 0
    human_list = capsys.readouterr().out
    assert secret_v1 not in human_list and plugin_secret not in human_list
    assert "OPENAI_API_KEY" in human_list

    # 4. Rotate (JSON)
    assert main(["vault", "rotate", "OPENAI_API_KEY", secret_v2, "--workspace-id", "ws-sec", "--db-path", db_file, "--json"]) == 0
    rot_raw = capsys.readouterr().out
    assert secret_v2 not in rot_raw and secret_v1 not in rot_raw
    rot_meta = json.loads(rot_raw)
    assert rot_meta["version"] == 2
    assert rot_meta["masked_preview"] == "sk-l****2233"
    assert rot_meta["fingerprint_sha256"] != put_meta["fingerprint_sha256"]
    assert rot_meta["cipher"] == "AES-256-GCM"

    # 5. Delete + verify missing delete returns exit code 1
    assert main(["vault", "delete", "OPENAI_API_KEY", "--workspace-id", "ws-sec", "--db-path", db_file, "--json"]) == 0
    del_res = json.loads(capsys.readouterr().out)
    assert del_res["deleted"] is True

    assert main(["vault", "delete", "OPENAI_API_KEY", "--workspace-id", "ws-sec", "--db-path", db_file, "--json"]) == 1
    capsys.readouterr()


def test_cli_workspace_create_list_and_rbac_exit_codes(capsys, tmp_path: Path):
    """Verify `cli.py workspace <list|create|rbac-check>` manages workspaces and returns 0/1 on RBAC."""
    db_file = str(tmp_path / "phase6_ws.db")

    assert main(["workspace", "create", "finops-prod", "--name", "FinOps Sovereign", "--branch", "release/v6", "--isolation-mode", "airgap_strict", "--db-path", db_file, "--json"]) == 0
    created = json.loads(capsys.readouterr().out)
    assert created["id"] == "finops-prod"
    assert created["branch"] == "release/v6"
    assert created["isolation_mode"] == "airgap_strict"

    assert main(["workspace", "list", "--db-path", db_file, "--json"]) == 0
    ws_list = json.loads(capsys.readouterr().out)
    assert any(w["id"] == "finops-prod" for w in ws_list["workspaces"])

    assert main(["workspace", "list", "--db-path", db_file]) == 0
    assert "finops-prod" in capsys.readouterr().out

    # Allowed check -> exit code 0
    rc_allow = main(["workspace", "rbac-check", "--actor", "lead-sec", "--permission", "secrets:write", "--role", "admin", "--workspace-id", "finops-prod", "--db-path", db_file, "--json"])
    assert rc_allow == 0
    verdict_allow = json.loads(capsys.readouterr().out)
    assert verdict_allow["allowed"] is True

    # Denied check -> exit code 1
    rc_deny = main(["workspace", "rbac-check", "--actor", "guest-auditor", "--permission", "secrets:write", "--role", "viewer", "--workspace-id", "finops-prod", "--db-path", db_file, "--json"])
    assert rc_deny == 1
    verdict_deny = json.loads(capsys.readouterr().out)
    assert verdict_deny["allowed"] is False

    # Human text mode RBAC check
    assert main(["workspace", "rbac-check", "--actor", "guest-auditor", "--permission", "p10:approve", "--role", "viewer", "--workspace-id", "finops-prod", "--db-path", db_file]) == 1
    assert "[DENIED]" in capsys.readouterr().out


def test_cli_run_streams_ordered_events_with_and_without_p10(capsys, tmp_path: Path):
    """Verify `cli.py run` streams `[seq] type: detail` lines and supports `--no-p10` and `--json`."""
    db_file = str(tmp_path / "phase6_exec.db")

    # Default P-10 gated stream (human text)
    assert main(["run", "--kind", "agent", "--target", "security-auditor", "--objective", "Verify vault cipher tags", "--workspace-id", "ws-exec", "--db-path", db_file]) == 0
    stream_out = capsys.readouterr().out
    assert "[1] run.started:" in stream_out
    assert "[2] step.tool_call:" in stream_out
    assert "[3] step.completed:" in stream_out
    assert "[4] p10.held:" in stream_out

    # Non-P10 workflow run (--no-p10 --json)
    assert main(["run", "--kind", "workflow", "--target", "WF-CI-GATE", "--objective", "Run deterministic lint gate", "--no-p10", "--workspace-id", "ws-exec", "--db-path", db_file, "--json"]) == 0
    snap = json.loads(capsys.readouterr().out)
    assert snap["kind"] == "workflow"
    assert snap["requires_p10"] is False
    assert snap["status"] == "completed"
    assert [e["type"] for e in snap["events"]] == ["run.started", "step.tool_call", "step.completed", "run.completed"]


def test_cli_pricing_eval_live_and_deterministic_fallback(capsys, monkeypatch):
    """Verify `cli.py pricing-eval` evaluates schedules and falls back cleanly when module is absent."""
    parser = build_parser()
    parsed = parser.parse_args(["pricing-eval", "--schedule", "compare", "--seats", "10", "--api-spend", "1800", "--json"])
    assert parsed.command == "pricing-eval"
    assert parsed.seats == 10
    assert parsed.api_spend == 1800.0

    # Test deterministic fallback explicitly
    monkeypatch.setitem(sys.modules, "core.eval.pricing_mirofish", None)
    assert main(["pricing-eval", "--schedule", "compare", "--seats", "8", "--api-spend", "1200", "--json"]) == 0
    fb = json.loads(capsys.readouterr().out)
    assert fb["schedule"] == "compare"
    assert fb["calibrated"]["pro_annual_usd"] == 29
    assert fb["calibrated"]["byom_annual_usd"] == 15
    assert fb["calibrated"]["pricing_health_score"] == 96.5
    assert fb["legacy"]["pro_annual_usd"] == 39
    assert fb["legacy"]["hidden_fee_distrust_score"] == 0.68

    assert main(["pricing-eval", "--schedule", "calibrated", "--seats", "12", "--api-spend", "2400"]) == 0
    human_out = capsys.readouterr().out
    assert "Calibrated:" in human_out and "$29/mo" in human_out

    # Test live module path if available in workspace
    monkeypatch.delitem(sys.modules, "core.eval.pricing_mirofish", raising=False)
    assert main(["pricing-eval", "--schedule", "compare", "--json"]) == 0
    live_or_fb = json.loads(capsys.readouterr().out)
    assert live_or_fb["schedule"] == "compare"
    assert "calibrated" in live_or_fb and "legacy" in live_or_fb


@pytest.mark.asyncio
async def test_python_sdk_simulate_pricing_sync_and_async_parity():
    """Verify `KeelwayClient.platform.simulate_pricing` & `AsyncKeelwayClient.platform.simulate_pricing`."""
    sync_sig = inspect.signature(SyncPlatformClient.simulate_pricing)
    async_sig = inspect.signature(AsyncPlatformClient.simulate_pricing)
    assert list(sync_sig.parameters.values()) == list(async_sig.parameters.values())

    recorded: List[Dict[str, Any]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        recorded.append({"method": request.method, "path": request.url.path, "json": payload})
        assert request.method == "POST"
        assert request.url.path == "/v1/platform/pricing/simulate"
        return httpx.Response(
            200,
            json={
                **payload,
                "calibrated": {"pro_annual_usd": 29, "byom_annual_usd": 15, "pricing_health_score": 96.5},
                "legacy": {"pro_annual_usd": 39, "pricing_health_score": 54.0},
            },
        )

    class _AsyncTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            await request.aread()
            return _handler(request)

    with KeelwayClient(token="kw_sync_p6", transport=httpx.MockTransport(_handler)) as sync_client:
        res_sync = sync_client.platform.simulate_pricing()
        assert res_sync["schedule"] == "compare"
        assert res_sync["seats"] == 8
        assert res_sync["monthly_api_spend_usd"] == 1200.0
        assert res_sync["run_swarm"] is True
        assert res_sync["calibrated"]["pro_annual_usd"] == 29

    async with AsyncKeelwayClient(token="kw_async_p6", transport=_AsyncTransport()) as async_client:
        res_async = await async_client.platform.simulate_pricing(
            schedule="calibrated", seats=14, monthly_api_spend_usd=2100.0, run_swarm=False
        )
        assert res_async["schedule"] == "calibrated"
        assert res_async["seats"] == 14
        assert res_async["monthly_api_spend_usd"] == 2100.0
        assert res_async["run_swarm"] is False

    assert len(recorded) == 2
    assert recorded[0]["json"] == {"schedule": "compare", "seats": 8, "monthly_api_spend_usd": 1200.0, "run_swarm": True}
    assert recorded[1]["json"] == {"schedule": "calibrated", "seats": 14, "monthly_api_spend_usd": 2100.0, "run_swarm": False}


@pytest.mark.asyncio
async def test_python_sdk_simulate_pricing_live_asgi_roundtrip():
    """Verify `AsyncKeelwayClient.platform.simulate_pricing` against live FastAPI `/v1/platform/pricing/simulate`."""
    from httpx import ASGITransport
    from core.main import app
    from core.security.auth import launch_token

    async with AsyncKeelwayClient(
        base_url="http://localhost",
        token=launch_token(),
        transport=ASGITransport(app=app),
    ) as client:
        res = await client.platform.simulate_pricing(
            schedule="compare", seats=8, monthly_api_spend_usd=1200.0, run_swarm=False
        )
        assert res["mode"] == "compare"
        assert res["calibrated"]["pricing_health_score"] > res["legacy"]["pricing_health_score"]

