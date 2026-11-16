"""
Phase 15A Verification Suite — Cyclic KFlow Bounded Reflection Loops, Dynamic Fan-Out Shards,
Saga Compensation, Pre-Storage DLP Secret Guards, Cost-Latency-Privacy Autopilot, 5-Role RBAC
FastAPI Routes (`286` OpenAPI paths), and Sovereign `keelway kflow-cyclic` & `autopilot` CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from cli import main as cli_main
from core.api.platform_cyclic_routes import (
    get_cyclic_kflow_engine,
    platform_cyclic_router,
)
from core.api.platform_runtime_routes import (
    get_rbac_controller,
    router as platform_runtime_router,
)
from core.main import app as live_app
from core.platform.kflow_cyclic_autopilot import (
    CyclicKFlowPolicyViolationError,
    CyclicKFlowValidationError,
    SQLiteCyclicKFlowEngine,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import launch_token


def test_validate_cyclic_graph_bounds_cycles_and_errors(tmp_path: Path) -> None:
    eng = SQLiteCyclicKFlowEngine(db_path=tmp_path / "cyclic_val.db")
    try:
        valid = eng.validate_cyclic_graph(workspace_id="ws-alpha", workflow_id="WF-CYCLIC-01")
        assert valid["valid"] is True
        assert valid["node_count"] == 3
        assert valid["loop_edge_count"] == 1
        assert valid["max_worst_case_steps"] == 7
        assert valid["topological_spine"] == ["draft_patch", "critic_verify", "publish_release"]
        assert valid["compensation_handlers"] == ["revert_worktree", "discard_candidate", "rollback_tag"]
        assert len(valid["spec_sha256"]) == 64

        with pytest.raises(CyclicKFlowValidationError):
            eng.validate_cyclic_graph(nodes=[])

        with pytest.raises(CyclicKFlowValidationError):
            eng.validate_cyclic_graph(nodes=[{"id": "dup"}, {"id": "dup"}])

        with pytest.raises(CyclicKFlowValidationError):
            eng.validate_cyclic_graph(nodes=[{"id": "n1", "depends_on": ["ghost"]}])

        with pytest.raises(CyclicKFlowValidationError):
            eng.validate_cyclic_graph(
                nodes=[{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}],
                loop_edges=[],
            )

        for bad_iter in (0, 11):
            with pytest.raises(CyclicKFlowValidationError):
                eng.validate_cyclic_graph(
                    loop_edges=[{"from_node": "critic_verify", "to_node": "draft_patch", "condition": "critic_score_lt", "max_iterations": bad_iter}]
                )

        with pytest.raises(CyclicKFlowValidationError):
            eng.validate_cyclic_graph(
                loop_edges=[{"from_node": "unknown", "to_node": "draft_patch", "condition": "critic_score_lt", "max_iterations": 2}]
            )

        with pytest.raises(CyclicKFlowValidationError):
            eng.validate_cyclic_graph(
                loop_edges=[{"from_node": "critic_verify", "to_node": "draft_patch", "condition": "bad_cond", "max_iterations": 2}]
            )

        for bad_fan in (0, 17):
            with pytest.raises(CyclicKFlowValidationError):
                eng.validate_cyclic_graph(nodes=[{"id": "s1", "fan_out_items": bad_fan}], loop_edges=[])
    finally:
        eng.close()


def test_execute_cyclic_convergence_saga_p10_dlp_and_wal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "cyclic_wal.db"
    monkeypatch.setenv("KEELWAY_PLATFORM_DB_PATH", str(db_file))
    eng = SQLiteCyclicKFlowEngine()
    raw_secrets = [
        "sk-proj-secret1234567890abcdef",
        "AKIAIOSFODNN7EXAMPLE",
        "ghp_1234567890abcdef1234567890",
        "-----BEGIN RSA PRIVATE KEY-----",
    ]
    try:
        # 1. Default reflection loop converges on iteration 2 (0.74 -> 0.90 >= 0.85)
        conv = eng.execute_cyclic_graph(workspace_id="ws-cyc", workflow_id="WF-CYCLIC-01")
        assert conv["status"] == "CONVERGED"
        assert conv["converged"] is True
        assert conv["iterations_executed"] == 2
        assert conv["final_critic_score"] == 0.90
        assert conv["fan_out_shards"] == 3
        assert conv["compensation_log"] == []
        assert len(conv["run_sha256"]) == 64
        assert conv["iteration_trace"][-1]["node_id"] == "publish_release"

        # 2. Timeout simulation triggers reverse-order saga compensation
        timed_out = eng.execute_cyclic_graph(workspace_id="ws-cyc", workflow_id="WF-CYCLIC-01", simulate_timeout=True)
        assert timed_out["status"] == "COMPENSATED"
        assert timed_out["converged"] is False
        assert [c["node_id"] for c in timed_out["compensation_log"]] == ["critic_verify", "draft_patch"]
        assert all(c["reason"] == "timeout_exceeded" and c["status"] == "ROLLED_BACK" for c in timed_out["compensation_log"])

        # 3. Exhausted max_iterations triggers saga compensation
        exhausted = eng.execute_cyclic_graph(
            workspace_id="ws-cyc", workflow_id="WF-CYCLIC-01", max_iterations_override=2, critic_threshold=0.99
        )
        assert exhausted["status"] == "COMPENSATED"
        assert exhausted["converged"] is False
        assert exhausted["iterations_executed"] == 2
        assert all(c["reason"] == "max_iterations_exhausted" for c in exhausted["compensation_log"])

        # 4. P-10 hold & approval release
        p10_nodes = [
            {"id": "draft_patch", "model": "claude-3-7-sonnet", "fan_out_items": 2},
            {"id": "critic_verify", "model": "gpt-4.1", "depends_on": ["draft_patch"]},
            {"id": "publish_release", "model": "keelway-core:7b", "depends_on": ["critic_verify"], "requires_p10": True},
        ]
        held = eng.execute_cyclic_graph(workspace_id="ws-cyc", workflow_id="WF-P10", nodes=p10_nodes)
        assert held["status"] == "HELD_P10" and held["held_node_id"] == "publish_release" and held["converged"] is False

        approved = eng.execute_cyclic_graph(
            workspace_id="ws-cyc", workflow_id="WF-P10", nodes=p10_nodes, approved_node_ids=["publish_release"]
        )
        assert approved["status"] == "CONVERGED" and approved["held_node_id"] is None

        # 5. DLP blocks all 4 secret classes before SQLite write
        for secret in raw_secrets:
            with pytest.raises(CyclicKFlowPolicyViolationError):
                eng.execute_cyclic_graph(workspace_id="ws-cyc", initial_state={"token": secret})
    finally:
        eng.close()

    eng2 = SQLiteCyclicKFlowEngine(db_path=db_file)
    try:
        listed = eng2.list_cyclic_runs(workspace_id="ws-cyc")
        assert listed["count"] == 5
        assert eng2.list_cyclic_runs(workspace_id="ws-other")["count"] == 0
        fetched = eng2.get_cyclic_run(workspace_id="ws-cyc", run_id=conv["run_id"])
        assert fetched is not None and fetched["run_sha256"] == conv["run_sha256"]
        assert eng2.get_cyclic_run(workspace_id="ws-other", run_id=conv["run_id"]) is None

        with sqlite3.connect(str(db_file)) as raw_conn:
            assert str(raw_conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
            dump_text = "\n".join(raw_conn.iterdump())
            for secret in raw_secrets:
                assert secret not in dump_text
    finally:
        eng2.close()


def test_simulate_autopilot_budget_airgap_and_eu_residency(tmp_path: Path) -> None:
    eng = SQLiteCyclicKFlowEngine(db_path=tmp_path / "autopilot.db")
    try:
        # 1. hybrid_balanced with $0.15 cap (baseline P95 = $0.16 -> rewrites draft_patch to qwen2.5-coder:7b -> P95 = $0.07)
        bal = eng.simulate_autopilot(workspace_id="ws-ap", budget_cap_usd=0.15, privacy_policy="hybrid_balanced")
        assert bal["baseline_p50_usd"] == 0.08 and bal["baseline_p95_usd"] == 0.16
        assert bal["optimized_p50_usd"] == 0.035 and bal["optimized_p95_usd"] == 0.07
        assert bal["savings_pct"] == 56.25
        assert bal["privacy_compliant"] is True and bal["violations_resolved"] == 1
        assert bal["node_plan"][0]["selected_model"] == "qwen2.5-coder:7b"
        assert "budget_cap_usd" in bal["node_plan"][0]["reason"]
        assert len(bal["simulation_sha256"]) == 64

        # 2. airgap_strict -> zero-egress OpenCore across all nodes (100% token savings)
        air = eng.simulate_autopilot(workspace_id="ws-ap", budget_cap_usd=1.0, privacy_policy="airgap_strict")
        assert air["optimized_p95_usd"] == 0.0 and air["savings_pct"] == 100.0
        assert air["violations_resolved"] == 2
        assert all(n["data_boundary"] == "local_metal_zero_egress" for n in air["node_plan"])
        assert all("airgap_strict" in n["reason"] for n in air["node_plan"][:2])

        # 3. eu_residency -> rewrites US-only frontier checkpoints
        eu = eng.simulate_autopilot(workspace_id="ws-ap", budget_cap_usd=1.0, privacy_policy="eu_residency")
        assert eu["optimized_p95_usd"] == 0.0 and eu["violations_resolved"] == 2
        assert all("eu_residency" in n["reason"] for n in eu["node_plan"][:2])

        assert eng.list_autopilot_simulations(workspace_id="ws-ap")["count"] == 3
        with pytest.raises(CyclicKFlowValidationError):
            eng.simulate_autopilot(privacy_policy="public_open")
        with pytest.raises(CyclicKFlowValidationError):
            eng.simulate_autopilot(budget_cap_usd=-0.01)
    finally:
        eng.close()


@pytest.mark.asyncio
async def test_fastapi_cyclic_routes_5_role_rbac_dlp_and_openapi_286(tmp_path: Path) -> None:
    db_file = tmp_path / "api_phase15.db"
    cyc_eng = SQLiteCyclicKFlowEngine(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_cyclic_router)
    test_app.dependency_overrides[get_cyclic_kflow_engine] = lambda: cyc_eng
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac

    token = launch_token()
    role_headers = {
        r: {"Authorization": f"Bearer {token}", "X-Keelway-Role": r, "X-Keelway-Actor": f"{r}-actor"}
        for r in ("owner", "admin", "builder", "operator", "viewer")
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Viewer allowed on validate (read:all), blocked on execute & autopilot/simulate (workflows:run)
            val_res = await client.post("/v1/platform/kflow/cyclic/validate", headers=role_headers["viewer"], json={"workspace_id": "default"})
            assert val_res.status_code == 200 and val_res.json()["valid"] is True
            assert (await client.post("/v1/platform/kflow/cyclic/validate", headers=role_headers["viewer"], json={"workspace_id": "default", "nodes": []})).status_code == 422
            assert (await client.post("/v1/platform/kflow/cyclic/execute", headers=role_headers["viewer"], json={"workspace_id": "default"})).status_code == 403
            assert (await client.post("/v1/platform/kflow/autopilot/simulate", headers=role_headers["viewer"], json={"workspace_id": "default"})).status_code == 403

            # Builder executes cyclic workflow (200), but blocked when passing approved_node_ids (requires p10:approve -> 403)
            exec_res = await client.post(
                "/v1/platform/kflow/cyclic/execute",
                headers=role_headers["builder"],
                json={"workspace_id": "default", "fan_out_shards": 4},
            )
            assert exec_res.status_code == 200 and exec_res.json()["status"] == "CONVERGED"
            run_id = exec_res.json()["run_id"]

            assert (
                await client.post(
                    "/v1/platform/kflow/cyclic/execute",
                    headers=role_headers["builder"],
                    json={"workspace_id": "default", "approved_node_ids": ["publish_release"]},
                )
            ).status_code == 403

            # Operator has p10:approve -> 200
            op_res = await client.post(
                "/v1/platform/kflow/cyclic/execute",
                headers=role_headers["operator"],
                json={"workspace_id": "default", "approved_node_ids": ["publish_release"]},
            )
            assert op_res.status_code == 200

            # DLP secret -> 422 policy_violation
            dlp_res = await client.post(
                "/v1/platform/kflow/cyclic/execute",
                headers=role_headers["admin"],
                json={"workspace_id": "default", "initial_state": {"secret": "sk-live-abcdef1234567890"}},
            )
            assert dlp_res.status_code == 422 and dlp_res.json()["code"] == "policy_violation"

            # Runs list, get by id, and 404
            assert (await client.get("/v1/platform/kflow/cyclic/runs?workspace_id=default", headers=role_headers["viewer"])).json()["count"] == 2
            assert (await client.get(f"/v1/platform/kflow/cyclic/runs/{run_id}?workspace_id=default", headers=role_headers["viewer"])).status_code == 200
            assert (await client.get("/v1/platform/kflow/cyclic/runs/cyc-missing?workspace_id=default", headers=role_headers["viewer"])).status_code == 404

            # Autopilot simulate & list
            sim_res = await client.post(
                "/v1/platform/kflow/autopilot/simulate",
                headers=role_headers["builder"],
                json={"workspace_id": "default", "privacy_policy": "airgap_strict", "budget_cap_usd": 0.15},
            )
            assert sim_res.status_code == 200 and sim_res.json()["savings_pct"] == 100.0
            assert (await client.post("/v1/platform/kflow/autopilot/simulate", headers=role_headers["owner"], json={"workspace_id": "default", "privacy_policy": "invalid"})).status_code == 422
            assert (await client.get("/v1/platform/kflow/autopilot/simulations?workspace_id=default", headers=role_headers["viewer"])).json()["count"] == 1

        openapi_paths = live_app.openapi()["paths"]
        assert len(openapi_paths) >= 286
        for route in (
            "/v1/platform/kflow/cyclic/validate",
            "/v1/platform/kflow/cyclic/execute",
            "/v1/platform/kflow/cyclic/runs",
            "/v1/platform/kflow/cyclic/runs/{run_id}",
            "/v1/platform/kflow/autopilot/simulate",
            "/v1/platform/kflow/autopilot/simulations",
        ):
            assert route in openapi_paths
    finally:
        cyc_eng.close()
        rbac.close()


def test_sovereign_cli_kflow_cyclic_and_autopilot_end_to_end(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    db_file = str(tmp_path / "cli_phase15.db")

    assert cli_main(["kflow-cyclic", "validate", "--workflow-id", "WF-CLI-15", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    val_out = json.loads(capsys.readouterr().out)
    assert val_out["valid"] is True and val_out["node_count"] == 3

    assert cli_main(["kflow-cyclic", "execute", "--workflow-id", "WF-CLI-15", "--fan-out-shards", "4", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    exec_out = json.loads(capsys.readouterr().out)
    assert exec_out["status"] == "CONVERGED" and exec_out["fan_out_shards"] == 4

    assert cli_main(["kflow-cyclic", "execute", "--simulate-timeout", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    comp_out = json.loads(capsys.readouterr().out)
    assert comp_out["status"] == "COMPENSATED" and len(comp_out["compensation_log"]) == 2

    # DLP error & validation error return exit code 1 with JSON payload
    assert cli_main(["kflow-cyclic", "execute", "--initial-state-json", '{"k":"sk-live-secret1234567890"}', "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "policy_violation"

    assert cli_main(["kflow-cyclic", "execute", "--max-iterations", "99", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "cyclic_validation_error"

    assert cli_main(["kflow-cyclic", "runs", "--limit", "10", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 2

    assert cli_main(["autopilot", "simulate", "--workflow-id", "WF-CLI-15", "--budget-usd", "0.15", "--privacy-policy", "airgap_strict", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    sim_out = json.loads(capsys.readouterr().out)
    assert sim_out["privacy_policy"] == "airgap_strict" and sim_out["savings_pct"] == 100.0

    assert cli_main(["autopilot", "simulate", "--privacy-policy", "bad_policy", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "cyclic_validation_error"

    assert cli_main(["autopilot", "list", "--workspace", "ws-cli", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1
