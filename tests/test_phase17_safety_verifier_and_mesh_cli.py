"""
Phase 17A Verification Suite — Formal Safety State-Machine Verifier (`/v1/platform/safety/*`),
Federated Edge-to-Cluster Agent Mesh (`/v1/platform/mesh/*`), 5-Role RBAC FastAPI Routes
(`298` OpenAPI paths), Pre-Storage DLP Scrubbing, SQLite WAL Persistence, and Sovereign CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from cli import main as cli_main
from core.api.platform_runtime_routes import get_rbac_controller, router as platform_runtime_router
from core.api.platform_safety_mesh_routes import get_safety_and_mesh_engine, platform_safety_mesh_router
from core.main import app as live_app
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.safety_and_mesh import (
    MeshSovereigntyViolationError,
    SafetyMeshValidationError,
    SafetyVerificationNotFoundError,
    SQLiteSafetyAndMeshEngine,
)
from core.security.auth import launch_token


def test_default_unguarded_workflow_and_p10_guard_injection_remediation(tmp_path: Path) -> None:
    db_file = tmp_path / "safety_default.db"
    eng = SQLiteSafetyAndMeshEngine(db_path=db_file)
    secret_tok = "sk-live-secret9876543210fedcba"
    try:
        unguarded = eng.verify_workflow(workspace_id="ws-safety", workflow_name=f"treasury-wire-{secret_tok}")
        assert unguarded["status"] == "VIOLATION_FOUND" and unguarded["states_explored"] >= 3
        assert [i["invariant_id"] for i in unguarded["invariants_checked"]] == [
            "no_unguarded_destructive_tool",
            "no_privilege_escalation",
            "bounded_termination",
            "airgap_zero_egress",
        ]
        inv_map = {i["invariant_id"]: i["passed"] for i in unguarded["invariants_checked"]}
        assert inv_map == {
            "no_unguarded_destructive_tool": False,
            "no_privilege_escalation": True,
            "bounded_termination": True,
            "airgap_zero_egress": True,
        }
        assert len(unguarded["violations"]) == 1
        viol = unguarded["violations"][0]
        assert viol["invariant_id"] == "no_unguarded_destructive_tool" and viol["severity"] == "CRITICAL"
        assert viol["offending_node"] == "execute_wire_transfer"
        assert viol["counterexample_path"] == ["ingest_invoice", "validate_vendor", "execute_wire_transfer"]
        assert unguarded["dlp_redactions"] >= 1 and secret_tok not in json.dumps(unguarded)
        assert unguarded["proof_sha256"].startswith("sha256:")

        remediated = eng.verify_workflow(workspace_id="ws-safety", inject_p10_guards=True)
        assert remediated["status"] == "VERIFIED_SAFE" and remediated["violations"] == []
        assert remediated["p10_guards_injected"] == ["execute_wire_transfer"]
        assert all(i["passed"] for i in remediated["invariants_checked"])
        assert remediated["proof_sha256"].startswith("sha256:")

        assert eng.get_verification("ws-safety", remediated["verification_id"])["verification_id"] == remediated["verification_id"]
        listed = eng.list_verifications("ws-safety", limit=10)
        assert listed["count"] == 2 and listed["verifications"][0]["verification_id"] == remediated["verification_id"]

        with sqlite3.connect(db_file) as raw_conn:
            assert raw_conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
            assert secret_tok not in "\n".join(raw_conn.iterdump())
    finally:
        eng.close()


def test_privilege_escalation_unbounded_cycle_and_airgap_zero_egress_invariants(tmp_path: Path) -> None:
    eng = SQLiteSafetyAndMeshEngine(db_path=tmp_path / "safety_invariants.db")
    try:
        priv_nodes = [
            {"node_id": "parse_webhook", "role": "viewer", "tool_kind": "read_only", "requires_p10": False},
            {"node_id": "rm_prod_dir", "role": "agent", "tool_kind": "destructive_shell", "requires_p10": False},
        ]
        priv_res = eng.verify_workflow(workspace_id="ws-inv", nodes=priv_nodes)
        assert priv_res["status"] == "VIOLATION_FOUND"
        assert {"no_privilege_escalation", "no_unguarded_destructive_tool"}.issubset({v["invariant_id"] for v in priv_res["violations"]})

        priv_healed = eng.verify_workflow(workspace_id="ws-inv", nodes=priv_nodes, inject_p10_guards=True)
        assert priv_healed["status"] == "VERIFIED_SAFE" and priv_healed["p10_guards_injected"] == ["rm_prod_dir"]

        cyc_res = eng.verify_workflow(
            workspace_id="ws-inv",
            nodes=[
                {"node_id": "draft", "role": "agent", "tool_kind": "write", "max_iterations": 25},
                {"node_id": "critique", "role": "agent", "tool_kind": "read_only", "max_iterations": 2},
            ],
            edges=[
                {"from_node": "draft", "to_node": "critique"},
                {"from_node": "critique", "to_node": "draft", "condition": "unbounded"},
            ],
        )
        bounded_viols = [v for v in cyc_res["violations"] if v["invariant_id"] == "bounded_termination"]
        assert cyc_res["status"] == "VIOLATION_FOUND" and len(bounded_viols) >= 1
        assert all(v["severity"] == "HIGH" for v in bounded_viols) and any(v["offending_node"] == "draft" for v in bounded_viols)

        egress_airgap = eng.verify_workflow(
            workspace_id="ws-inv",
            airgap_mode=True,
            nodes=[
                {"node_id": "local_prep", "tool_kind": "read_only", "data_classification": "public"},
                {"node_id": "call_cloud_llm", "tool_kind": "cloud_egress", "data_classification": "public"},
            ],
        )
        assert egress_airgap["status"] == "VIOLATION_FOUND" and egress_airgap["violations"][0]["invariant_id"] == "airgap_zero_egress"

        egress_pii = eng.verify_workflow(
            workspace_id="ws-inv",
            airgap_mode=False,
            nodes=[{"node_id": "pii_leak_step", "tool_kind": "cloud_egress", "data_classification": "restricted_pii"}],
        )
        assert egress_pii["status"] == "VIOLATION_FOUND" and egress_pii["violations"][0]["invariant_id"] == "airgap_zero_egress"

        with pytest.raises(SafetyMeshValidationError):
            eng.verify_workflow(workspace_id="../bad", nodes=[])
        with pytest.raises(SafetyVerificationNotFoundError):
            eng.get_verification("ws-inv", "sver-missing")
    finally:
        eng.close()


def test_federated_mesh_autoseed_custom_node_dispatch_pin_and_sovereignty_gate(tmp_path: Path) -> None:
    db_file = tmp_path / "mesh_engine.db"
    eng = SQLiteSafetyAndMeshEngine(db_path=db_file)
    gh_secret = "ghp_1234567890abcdef1234567890abcdef5678"
    try:
        seeded = eng.list_nodes(workspace_id="ws-mesh")
        assert seeded["count"] == 2
        assert {n["node_id"] for n in seeded["nodes"]} == {"edge-mac-m3-max", "cluster-h100-us-east"}
        assert all(n["attestation_sha256"].startswith("sha256:") for n in seeded["nodes"])

        custom = eng.register_node(
            workspace_id="ws-mesh",
            node_id="edge-linux-tpm2-01",
            name="Ubuntu Sovereign Workstation",
            tier="edge_local",
            hardware_hal="linux_tpm2",
            region="eu-frankfurt-lab",
            vram_gb=48,
        )
        assert custom["node_id"] == "edge-linux-tpm2-01" and eng.list_nodes(workspace_id="ws-mesh")["count"] == 3

        attested = eng.dispatch_handoff(
            workspace_id="ws-mesh",
            workflow_name="clinical-synthesis-pipeline",
            task_summary=f"Synthesize cohort intake using token {gh_secret}",
            data_classification="restricted_pii",
            allow_sanitized_burst=True,
        )
        assert attested["status"] == "ATTESTED_COMPLETE"
        assert attested["edge_node_id"] == "edge-mac-m3-max" and attested["burst_node_id"] == "cluster-h100-us-east"
        assert attested["total_cost_usd"] == pytest.approx(0.0042)
        assert [s["stage_name"] for s in attested["stages"]] == ["kbrain_pii_ingest_and_scrub", "attested_cluster_synthesis"]
        assert all(s["zero_raw_pii_egress"] is True for s in attested["stages"])
        assert attested["dlp_redactions"] >= 1 and gh_secret not in json.dumps(attested)

        pinned = eng.dispatch_handoff(workspace_id="ws-mesh", data_classification="restricted_pii", allow_sanitized_burst=False)
        assert pinned["status"] == "PINNED_EDGE_ONLY" and pinned["burst_node_id"] is None and pinned["total_cost_usd"] == 0.0
        assert pinned["stages"][1]["stage_name"] == "local_sovereign_synthesis" and pinned["stages"][1]["target_tier"] == "edge_local"

        with pytest.raises(MeshSovereigntyViolationError):
            eng.dispatch_handoff(workspace_id="ws-mesh", data_classification="restricted_pii", force_raw_cloud_burst=True)

        handoffs = eng.list_handoffs(workspace_id="ws-mesh", limit=10)
        assert handoffs["count"] == 2 and handoffs["handoffs"][0]["handoff_id"] == pinned["handoff_id"]

        with sqlite3.connect(db_file) as raw_conn:
            assert gh_secret not in "\n".join(raw_conn.iterdump())
    finally:
        eng.close()


@pytest.mark.asyncio
async def test_fastapi_safety_and_mesh_rbac_and_fail_closed_422(tmp_path: Path) -> None:
    db_file = tmp_path / "api_phase17.db"
    sm_eng = SQLiteSafetyAndMeshEngine(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_safety_mesh_router)
    test_app.dependency_overrides[get_safety_and_mesh_engine] = lambda: sm_eng
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac

    token = launch_token()
    headers = {
        r: {"Authorization": f"Bearer {token}", "X-Keelway-Role": r, "X-Keelway-Actor": f"{r}-user"}
        for r in ("owner", "admin", "developer", "operator", "auditor", "viewer")
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            for read_role in ("auditor", "viewer"):
                assert (await client.get("/v1/platform/safety/verifications?workspace_id=default", headers=headers[read_role])).status_code == 200
                assert (await client.get("/v1/platform/mesh/nodes?workspace_id=default", headers=headers[read_role])).status_code == 200
                assert (await client.get("/v1/platform/mesh/handoffs?workspace_id=default", headers=headers[read_role])).status_code == 200
                assert (await client.post("/v1/platform/safety/verify", headers=headers[read_role], json={"workspace_id": "default"})).status_code == 403
                assert (await client.post("/v1/platform/mesh/nodes", headers=headers[read_role], json={"workspace_id": "default", "name": "Denied", "tier": "edge_local", "hardware_hal": "linux_tpm2"})).status_code == 403
                assert (await client.post("/v1/platform/mesh/dispatch", headers=headers[read_role], json={"workspace_id": "default"})).status_code == 403

            ver_bad = await client.post("/v1/platform/safety/verify", headers=headers["developer"], json={"workspace_id": "default"})
            assert ver_bad.status_code == 200 and ver_bad.json()["status"] == "VIOLATION_FOUND"

            ver_ok = await client.post("/v1/platform/safety/verify", headers=headers["operator"], json={"workspace_id": "default", "inject_p10_guards": True})
            assert ver_ok.status_code == 200 and ver_ok.json()["status"] == "VERIFIED_SAFE"
            vid = ver_ok.json()["verification_id"]
            assert (await client.get(f"/v1/platform/safety/verifications/{vid}?workspace_id=default", headers=headers["auditor"])).status_code == 200
            assert (await client.get("/v1/platform/safety/verifications/sver-ghost?workspace_id=default", headers=headers["auditor"])).status_code == 404

            reg_res = await client.post("/v1/platform/mesh/nodes", headers=headers["admin"], json={"workspace_id": "default", "name": "H100 EU", "tier": "cluster_burst", "hardware_hal": "nvidia_h100_cc", "vram_gb": 80})
            assert reg_res.status_code == 200 and reg_res.json()["tier"] == "cluster_burst"

            disp_ok = await client.post("/v1/platform/mesh/dispatch", headers=headers["owner"], json={"workspace_id": "default", "data_classification": "restricted_pii", "allow_sanitized_burst": True})
            assert disp_ok.status_code == 200 and disp_ok.json()["status"] == "ATTESTED_COMPLETE"

            sov_422 = await client.post("/v1/platform/mesh/dispatch", headers=headers["owner"], json={"workspace_id": "default", "data_classification": "restricted_pii", "force_raw_cloud_burst": True})
            assert sov_422.status_code == 422 and sov_422.json()["code"] == "mesh_sovereignty_violation"
            assert "restricted_pii" in sov_422.json()["detail"]
    finally:
        sm_eng.close()
        rbac.close()


def test_live_openapi_has_298_paths_including_safety_and_mesh_routes() -> None:
    openapi_paths = live_app.openapi()["paths"]
    assert len(openapi_paths) == 298
    for route in (
        "/v1/platform/safety/verify",
        "/v1/platform/safety/verifications",
        "/v1/platform/safety/verifications/{verification_id}",
        "/v1/platform/mesh/nodes",
        "/v1/platform/mesh/dispatch",
        "/v1/platform/mesh/handoffs",
    ):
        assert route in openapi_paths


def test_sovereign_cli_safety_and_mesh_json_commands(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    db_file = str(tmp_path / "cli_phase17.db")

    assert cli_main(["safety", "verify", "--workspace", "ws-cli17", "--db-path", db_file, "--json"]) == 0
    v1 = json.loads(capsys.readouterr().out)
    assert v1["status"] == "VIOLATION_FOUND" and len(v1["violations"]) == 1

    assert cli_main(["safety", "verify", "--inject-p10-guards", "--workspace", "ws-cli17", "--db-path", db_file, "--json"]) == 0
    v2 = json.loads(capsys.readouterr().out)
    assert v2["status"] == "VERIFIED_SAFE" and v2["p10_guards_injected"] == ["execute_wire_transfer"]

    spec_str = json.dumps({"nodes": [{"node_id": "egress_step", "tool_kind": "cloud_egress"}]})
    assert cli_main(["safety", "verify", "--airgap", "--spec-json", spec_str, "--workspace", "ws-cli17", "--db-path", db_file, "--json"]) == 0
    v3 = json.loads(capsys.readouterr().out)
    assert v3["status"] == "VIOLATION_FOUND" and v3["violations"][0]["invariant_id"] == "airgap_zero_egress"

    assert cli_main(["safety", "list", "--workspace", "ws-cli17", "--limit", "10", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 3

    assert cli_main(["mesh", "nodes", "--workspace", "ws-cli17", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 2

    assert cli_main(["mesh", "register", "--name", "Linux Edge Node", "--tier", "edge_local", "--hal", "linux_tpm2", "--node-id", "edge-tpm2-cli", "--vram-gb", "32", "--workspace", "ws-cli17", "--db-path", db_file, "--json"]) == 0
    reg_out = json.loads(capsys.readouterr().out)
    assert reg_out["node_id"] == "edge-tpm2-cli" and reg_out["hardware_hal"] == "linux_tpm2"

    assert cli_main(["mesh", "dispatch", "--classification", "restricted_pii", "--workspace", "ws-cli17", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ATTESTED_COMPLETE"

    assert cli_main(["mesh", "dispatch", "--pin-edge-only", "--workspace", "ws-cli17", "--db-path", db_file, "--json"]) == 0
    d2 = json.loads(capsys.readouterr().out)
    assert d2["status"] == "PINNED_EDGE_ONLY" and d2["total_cost_usd"] == 0.0

    assert cli_main(["mesh", "dispatch", "--classification", "restricted_pii", "--force-raw-cloud-burst", "--workspace", "ws-cli17", "--db-path", db_file, "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "mesh_sovereignty_violation"

    assert cli_main(["mesh", "handoffs", "--workspace", "ws-cli17", "--limit", "10", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 2
