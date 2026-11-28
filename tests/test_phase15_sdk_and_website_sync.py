"""
Phase 15B & Integration Verification Suite — Tri-Language SDK Parity (`Python`, `TypeScript`, `Go`)
for Bounded Cyclic & Conditional KFlow Sub-Graphs + Pre-Run Hybrid Cost/Privacy Autopilot,
Module-Size & Public-Hygiene Ratchets, and Website `286`-Route OpenAPI + `23`-Feature Facts Sync.
"""

from __future__ import annotations

import inspect
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest
from httpx import ASGITransport

from core.main import app
from core.sdk import (
    AsyncKeelwayClient,
    AsyncPlatformClient,
    KeelwayClient,
    KeelwayError,
    PermissionDeniedError,
    SyncPlatformClient,
)
from core.security.auth import launch_token

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "web-next"

PHASE15_PYTHON_METHODS = (
    "validate_cyclic_kflow",
    "execute_cyclic_kflow",
    "list_cyclic_kflow_runs",
    "get_cyclic_kflow_run",
    "simulate_kflow_autopilot",
    "list_kflow_autopilot_simulations",
)

PHASE15_TS_METHODS = (
    "validateCyclicKflow",
    "executeCyclicKflow",
    "listCyclicKflowRuns",
    "getCyclicKflowRun",
    "simulateKflowAutopilot",
    "listKflowAutopilotSimulations",
)

PHASE15_GO_METHODS = (
    "ValidateCyclicKFlow",
    "ExecuteCyclicKFlow",
    "ListCyclicKFlowRuns",
    "GetCyclicKFlowRun",
    "SimulateKFlowAutopilot",
    "ListKFlowAutopilotSimulations",
)

FORBIDDEN_PRIVATE_TOKENS = (
    # NOTE: "creova-gif" removed in KEEL-WEB-055 — the public open-core org
    # is deliberately linked from the shipped site; "creovas-projects" stays forbidden.
    "creovas-projects",
    "keelway.git",
    "KEEL-",
    "verify_engineering_gates.sh",
    "Antigravity",
    "gstack",
)


def _make_sync_mock_transport() -> httpx.MockTransport:
    runs_store: Dict[str, Dict[str, Any]] = {}
    sims_store: List[Dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else {}
        path, params = request.url.path, dict(request.url.params)
        role = request.headers.get("X-Keelway-Role", "owner")

        if role == "viewer" and request.method == "POST" and path != "/v1/platform/kflow/cyclic/validate":
            return httpx.Response(403, json={"detail": "Permission denied for viewer role"})

        if path == "/v1/platform/kflow/cyclic/validate" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "workspace_id": body.get("workspace_id", "default"),
                    "workflow_id": body.get("workflow_id", "WF-CYCLIC-01"),
                    "valid": True,
                    "node_count": 3,
                    "loop_edge_count": 1,
                    "max_worst_case_steps": 7,
                    "topological_spine": ["draft_patch", "critic_verify", "publish_release"],
                    "compensation_handlers": ["revert_worktree", "discard_candidate", "rollback_tag"],
                    "spec_sha256": "a" * 64,
                },
            )

        if path == "/v1/platform/kflow/cyclic/execute" and request.method == "POST":
            init_state = json.dumps(body.get("initial_state") or {})
            if "sk-live-" in init_state:
                return httpx.Response(422, json={"detail": "DLP secret detected in initial_state"})
            status_val = "COMPENSATED" if body.get("simulate_timeout") else "CONVERGED"
            rid = f"crun-{len(runs_store) + 1}"
            rec = {
                "run_id": rid,
                "workspace_id": body.get("workspace_id", "default"),
                "workflow_id": body.get("workflow_id", "WF-CYCLIC-01"),
                "status": status_val,
                "iterations_executed": 2,
                "max_iterations": body.get("max_iterations_override") or 3,
                "converged": status_val == "CONVERGED",
                "final_critic_score": 0.90,
                "critic_threshold": body.get("critic_threshold", 0.85),
                "fan_out_shards": body.get("fan_out_shards") or 3,
                "total_cost_usd": 0.16,
                "total_latency_ms": 1260,
                "iteration_trace": [],
                "compensation_log": [{"node_id": "draft_patch", "handler": "revert_worktree", "reason": "timeout_exceeded", "status": "ROLLED_BACK"}] if status_val == "COMPENSATED" else [],
                "held_node_id": None,
                "run_sha256": "b" * 64,
                "created_at": "2026-11-15T00:00:00+00:00",
            }
            runs_store[rid] = rec
            return httpx.Response(200, json=rec)

        if path == "/v1/platform/kflow/cyclic/runs" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            matched = [r for r in runs_store.values() if r["workspace_id"] == ws]
            return httpx.Response(200, json={"workspace_id": ws, "count": len(matched), "runs": matched})

        if path.startswith("/v1/platform/kflow/cyclic/runs/") and request.method == "GET":
            rid = path.rsplit("/", 1)[-1]
            if rid not in runs_store:
                return httpx.Response(404, json={"detail": "Not found"})
            return httpx.Response(200, json=runs_store[rid])

        if path == "/v1/platform/kflow/autopilot/simulate" and request.method == "POST":
            sim = {
                "simulation_id": f"apsim-{len(sims_store) + 1}",
                "workspace_id": body.get("workspace_id", "default"),
                "workflow_id": body.get("workflow_id", "WF-CYCLIC-01"),
                "privacy_policy": body.get("privacy_policy", "hybrid_balanced"),
                "budget_cap_usd": body.get("budget_cap_usd", 0.15),
                "baseline_p50_usd": 0.08,
                "baseline_p95_usd": 0.24,
                "optimized_p50_usd": 0.0,
                "optimized_p95_usd": 0.0,
                "savings_pct": 100.0,
                "baseline_ttft_ms": 765,
                "optimized_ttft_ms": 405,
                "privacy_compliant": True,
                "violations_resolved": 2,
                "node_plan": [],
                "simulation_sha256": "c" * 64,
                "created_at": "2026-11-15T00:00:00+00:00",
            }
            sims_store.append(sim)
            return httpx.Response(200, json=sim)

        if path == "/v1/platform/kflow/autopilot/simulations" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            matched = [s for s in sims_store if s["workspace_id"] == ws]
            return httpx.Response(200, json={"workspace_id": ws, "count": len(matched), "simulations": matched})

        return httpx.Response(404, json={"detail": f"Unhandled mock route {request.method} {path}"})

    return httpx.MockTransport(handler)


def test_python_sdk_phase15_sync_async_signature_and_mock_parity() -> None:
    for method_name in PHASE15_PYTHON_METHODS:
        sync_fn = getattr(SyncPlatformClient, method_name, None)
        async_fn = getattr(AsyncPlatformClient, method_name, None)
        assert callable(sync_fn), f"Missing SyncPlatformClient.{method_name}"
        assert callable(async_fn), f"Missing AsyncPlatformClient.{method_name}"
        assert inspect.iscoroutinefunction(async_fn)
        assert list(inspect.signature(sync_fn).parameters.keys()) == list(inspect.signature(async_fn).parameters.keys())

    with KeelwayClient(
        base_url="http://127.0.0.1:7420",
        token="test-token",
        transport=_make_sync_mock_transport(),
    ) as client:
        val = client.platform.validate_cyclic_kflow(workspace_id="ws-p15", workflow_id="WF-CYCLIC-01")
        assert val["valid"] is True and len(val["spec_sha256"]) == 64

        sim = client.platform.simulate_kflow_autopilot(
            workspace_id="ws-p15",
            workflow_id="WF-CYCLIC-01",
            budget_cap_usd=0.10,
            privacy_policy="airgap_strict",
        )
        assert sim["privacy_compliant"] is True and sim["optimized_p95_usd"] == 0.0

        sims = client.platform.list_kflow_autopilot_simulations(workspace_id="ws-p15")
        assert sims["count"] == 1

        run_ok = client.platform.execute_cyclic_kflow(workspace_id="ws-p15", workflow_id="WF-CYCLIC-01", critic_threshold=0.85)
        assert run_ok["status"] == "CONVERGED" and run_ok["converged"] is True

        fetched = client.platform.get_cyclic_kflow_run(run_ok["run_id"], workspace_id="ws-p15")
        assert fetched["run_id"] == run_ok["run_id"]

        run_comp = client.platform.execute_cyclic_kflow(workspace_id="ws-p15", workflow_id="WF-CYCLIC-01", simulate_timeout=True)
        assert run_comp["status"] == "COMPENSATED" and len(run_comp["compensation_log"]) >= 1

        listed = client.platform.list_cyclic_kflow_runs(workspace_id="ws-p15")
        assert listed["count"] == 2

        with pytest.raises(KeelwayError):
            client.platform.execute_cyclic_kflow(
                workspace_id="ws-p15",
                initial_state={"api_key": "sk-live-secret9999999999"},
            )


@pytest.mark.asyncio
async def test_python_async_sdk_live_asgi_cyclic_kflow_and_autopilot() -> None:
    ws_id = f"ws-p15-asgi-{uuid.uuid4().hex[:8]}"
    token = launch_token()

    async with AsyncKeelwayClient(
        base_url="http://127.0.0.1:7420",
        token=token,
        transport=ASGITransport(app=app),
    ) as client:
        val = await client.platform.validate_cyclic_kflow(workspace_id=ws_id, workflow_id="WF-CYCLIC-01")
        assert val["valid"] is True and val["loop_edge_count"] >= 1

        sim = await client.platform.simulate_kflow_autopilot(
            workspace_id=ws_id,
            workflow_id="WF-CYCLIC-01",
            budget_cap_usd=0.10,
            privacy_policy="airgap_strict",
        )
        assert sim["privacy_compliant"] is True
        assert sim["optimized_p95_usd"] <= sim["baseline_p95_usd"]
        assert len(sim["simulation_sha256"]) == 64

        sims = await client.platform.list_kflow_autopilot_simulations(workspace_id=ws_id)
        assert sims["count"] >= 1

        executed = await client.platform.execute_cyclic_kflow(
            workspace_id=ws_id,
            workflow_id="WF-CYCLIC-01",
            critic_threshold=0.85,
            fan_out_shards=4,
        )
        assert executed["status"] == "CONVERGED"
        assert executed["converged"] is True
        assert len(executed["run_sha256"]) == 64

        fetched = await client.platform.get_cyclic_kflow_run(executed["run_id"], workspace_id=ws_id)
        assert fetched["run_id"] == executed["run_id"]

        runs = await client.platform.list_cyclic_kflow_runs(workspace_id=ws_id)
        assert runs["count"] >= 1

    async with AsyncKeelwayClient(
        base_url="http://127.0.0.1:7420",
        token=token,
        transport=ASGITransport(app=app),
    ) as viewer_client:
        http_attr = getattr(viewer_client, "_http", None) or viewer_client._client
        http_attr.headers["X-Keelway-Role"] = "viewer"
        http_attr.headers["X-Keelway-Actor"] = "viewer-actor"
        with pytest.raises(PermissionDeniedError):
            await viewer_client.platform.execute_cyclic_kflow(workspace_id=ws_id)
        with pytest.raises(PermissionDeniedError):
            await viewer_client.platform.simulate_kflow_autopilot(workspace_id=ws_id)


def test_tri_sdk_module_caps_and_website_286_route_23_feature_parity() -> None:
    new_phase15_files = (
        REPO_ROOT / "core" / "platform" / "kflow_cyclic_autopilot.py",
        REPO_ROOT / "core" / "api" / "platform_cyclic_routes.py",
        REPO_ROOT / "core" / "cli_cyclic.py",
        REPO_ROOT / "core" / "sdk" / "platform_cyclic_client.py",
        REPO_ROOT / "sdk" / "typescript" / "src" / "platformCyclic.ts",
        REPO_ROOT / "sdk" / "go" / "platform_phase15.go",
        REPO_ROOT / "dev-app" / "src" / "lib" / "platformCyclicApi.ts",
        REPO_ROOT / "dev-app" / "src" / "components" / "platform" / "CyclicKflowAndAutopilotPanel.tsx",
    )
    for fpath in new_phase15_files:
        assert fpath.exists(), f"Expected Phase 15 module {fpath}"
        lines = fpath.read_text(encoding="utf-8").splitlines()
        assert len(lines) < 480, f"{fpath} exceeds 480-line cap ({len(lines)} lines)"

    ts_src = (REPO_ROOT / "sdk" / "typescript" / "src" / "platformCyclic.ts").read_text(encoding="utf-8")
    go_src = (REPO_ROOT / "sdk" / "go" / "platform_phase15.go").read_text(encoding="utf-8")
    for ts_m in PHASE15_TS_METHODS:
        assert ts_m in ts_src, f"Missing TypeScript SDK method {ts_m}"
    for go_m in PHASE15_GO_METHODS:
        assert f"func (p *PlatformService) {go_m}(" in go_src, f"Missing Go SDK method {go_m}"

    openapi_raw = (SITE_DIR / "openapi.json").read_text(encoding="utf-8")
    pub_openapi_raw = (SITE_DIR / "public" / "openapi.json").read_text(encoding="utf-8")
    assert openapi_raw == pub_openapi_raw
    openapi_doc = json.loads(openapi_raw)
    assert len(openapi_doc["paths"]) >= 286
    assert len(app.openapi()["paths"]) >= 286
    for route in (
        "/v1/platform/kflow/cyclic/validate",
        "/v1/platform/kflow/cyclic/execute",
        "/v1/platform/kflow/cyclic/runs",
        "/v1/platform/kflow/cyclic/runs/{run_id}",
        "/v1/platform/kflow/autopilot/simulate",
        "/v1/platform/kflow/autopilot/simulations",
    ):
        assert route in openapi_doc["paths"], f"Missing OpenAPI route {route}"

    facts_raw = (SITE_DIR / "product-facts.json").read_text(encoding="utf-8")
    pub_facts_raw = (SITE_DIR / "public" / "product-facts.json").read_text(encoding="utf-8")
    assert facts_raw == pub_facts_raw
    for tok in FORBIDDEN_PRIVATE_TOKENS:
        assert tok not in facts_raw, f"Private token '{tok}' leaked in product-facts.json"
    facts = json.loads(facts_raw)
    assert len(facts["features"]) >= 23
    feat = facts["features"]["cyclic_kflow_subgraphs_and_cost_privacy_autopilot"]
    assert feat["status"] == "AVAILABLE"
    assert "core/platform/kflow_cyclic_autopilot.py" in feat["code_path"]
