"""
Phase 8A Verification Suite — KFlow Topological DAG Engine, KSpaces LWW-Element-Set CRDT Sync,
Live CycloneDX 1.5 SBOM Provenance, Sovereign CLI (`kflow`, `kspaces-sync`, `sbom`), and
`AgentBuilder.unpack_bundle` Sibling-Prefix Zip-Slip & Python 3.14 `tarfile` Hardening.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import sqlite3
import tarfile
import time
import warnings

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from cli import cmd_sbom, main as cli_main
from core.agents.builder import AgentBuilder, AgentBundlePacker
from core.api.platform_kflow_routes import (
    get_kflow_engine,
    get_kspaces_crdt_engine,
    router as platform_kflow_router,
)
from core.api.platform_runtime_routes import (
    get_rbac_controller,
    router as platform_runtime_router,
)
from core.main import app as live_app
from core.platform.kflow_crdt import KFlowCycleError, KFlowDagEngine, KSpacesCrdtEngine
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import launch_token


DIAMOND_DAG_NODES = [
    {"id": "ingest", "label": "Ingest Repo AST", "agent_id": "code-architect", "depends_on": []},
    {"id": "lint", "label": "Static Lint Gate", "agentId": "qa-verifier", "dependsOn": ["ingest"]},
    {"id": "sec-scan", "label": "DLP & SAST Audit", "agent": "security-auditor", "depends_on": ["ingest"]},
    {
        "id": "release-gate", "label": "Production Release Gate",
        "agent_id": "release-captain", "depends_on": ["lint", "sec-scan"], "requiresP10": True,
    },
    {"id": "notify", "label": "Emit Signed Receipt", "agent_id": "ops-notifier", "depends_on": ["release-gate"]},
]


def test_kflow_dag_engine_waves_digests_cycles_budget_p10_and_wal_durability(tmp_path: Path) -> None:
    db_file = tmp_path / "phase8_kflow.db"
    engine = KFlowDagEngine(db_path=db_file)
    assert engine.journal_mode == "wal"

    # 1. P-10 hold stops at release-gate and marks downstream 'pending'
    held_run = engine.execute_dag("ws-alpha", "WF-DIAMOND", DIAMOND_DAG_NODES, trigger="ci_push", token_budget=5000)
    assert held_run["status"] == "awaiting_p10" and held_run["held_node_id"] == "release-gate"
    assert held_run["waves"] == [["ingest"], ["lint", "sec-scan"], ["release-gate"], ["notify"]]
    assert held_run["topological_order"] == ["ingest", "lint", "sec-scan", "release-gate", "notify"]
    assert held_run["receipt_sha256"].startswith("sha256:")

    held_by_id = {n["id"]: n for n in held_run["nodes"]}
    assert held_by_id["ingest"]["status"] == "passed"
    assert held_by_id["lint"]["status"] == "passed" and held_by_id["sec-scan"]["status"] == "passed"
    assert held_by_id["release-gate"]["status"] == "awaiting_p10"
    assert held_by_id["notify"]["status"] == "pending"
    assert held_by_id["lint"]["upstream_digests"] == [held_by_id["ingest"]["output_digest"]]

    # 2. Approved P-10 executes full diamond DAG and chains upstream digests
    completed = engine.execute_dag(
        "ws-alpha", "WF-DIAMOND", DIAMOND_DAG_NODES,
        trigger="p10_resume", token_budget=5000, approved_node_ids=["release-gate"],
    )
    assert completed["status"] == "completed" and completed["held_node_id"] is None
    comp_by_id = {n["id"]: n for n in completed["nodes"]}
    assert all(n["status"] == "passed" and str(n["output_digest"]).startswith("sha256:") for n in completed["nodes"])
    assert comp_by_id["release-gate"]["upstream_digests"] == [
        comp_by_id["lint"]["output_digest"], comp_by_id["sec-scan"]["output_digest"],
    ]
    assert comp_by_id["notify"]["upstream_digests"] == [comp_by_id["release-gate"]["output_digest"]]

    # 3. Token-budget exhaustion marks failing node 'failed' and downstream 'blocked'
    budget_fail = engine.execute_dag(
        "ws-alpha", "WF-BUDGET", DIAMOND_DAG_NODES, token_budget=300, approved_node_ids=["release-gate"]
    )
    assert budget_fail["status"] == "failed"
    bf_by_id = {n["id"]: n for n in budget_fail["nodes"]}
    assert bf_by_id["ingest"]["status"] == "passed"
    assert bf_by_id["lint"]["status"] == "failed" and bf_by_id["lint"]["error_detail"] == "Token budget exceeded"
    assert bf_by_id["release-gate"]["status"] == "blocked" and bf_by_id["notify"]["status"] == "blocked"

    # 4. Cycle detection & unknown upstream dependency rejection
    with pytest.raises(KFlowCycleError, match="Cycle detected"):
        engine.execute_dag(
            "ws-alpha", "WF-CYCLE",
            [{"id": "node-a", "depends_on": ["node-b"]}, {"id": "node-b", "depends_on": ["node-a"]}],
        )
    with pytest.raises(KFlowCycleError, match="Unknown upstream node dependency 'ghost-step'"):
        engine.execute_dag("ws-alpha", "WF-MISSING", [{"id": "node-a", "depends_on": ["ghost-step"]}])

    # 5. SQLite WAL restart durability & newest-first ordering
    engine.close()
    reopened = KFlowDagEngine(db_path=db_file)
    try:
        all_runs = reopened.list_runs(workspace_id="ws-alpha")
        assert all_runs["count"] == 3
        assert [r["run_id"] for r in all_runs["runs"]] == [
            budget_fail["run_id"], completed["run_id"], held_run["run_id"],
        ]
        assert reopened.list_runs(workspace_id="ws-alpha", workflow_id="WF-DIAMOND")["count"] == 2
    finally:
        reopened.close()


def test_kspaces_crdt_three_peer_commutativity_idempotence_tombstone_and_dlp(tmp_path: Path) -> None:
    ops_a = [
        {"namespace": "issues", "key": "ISS-1", "op": "set", "value": {"state": "todo", "pts": 3}, "lamport_ts": 2},
        {"namespace": "issues", "key": "ISS-TIE", "op": "set", "value": "from-peer-a", "lamport_ts": 5},
        {"namespace": "docs", "key": "DOC-1", "op": "set", "value": "Draft v1", "lamport_ts": 1},
    ]
    ops_b = [
        {"namespace": "issues", "key": "ISS-1", "op": "set", "value": {"state": "in_progress", "pts": 5}, "lamport_ts": 4},
        {"namespace": "issues", "key": "ISS-TIE", "op": "set", "value": "from-peer-b", "lamport_ts": 5},
        {"namespace": "issues", "key": "ISS-2", "op": "set", "value": "Ship CRDT", "lamport_ts": 6},
    ]
    ops_c = [
        {"namespace": "issues", "key": "ISS-TIE", "op": "set", "value": "from-peer-c", "lamport_ts": 5},
        {"namespace": "docs", "key": "DOC-1", "op": "remove", "lamport_ts": 3},
        {"namespace": "config", "key": "region", "op": "set", "value": "airgap_local", "lamport_ts": 7},
    ]

    schedules = [
        ("peer-a", ops_a, "peer-b", ops_b, "peer-c", ops_c),
        ("peer-c", ops_c, "peer-a", ops_a, "peer-b", ops_b),
        ("peer-b", ops_b, "peer-c", ops_c, "peer-a", ops_a),
    ]
    states = []
    for idx, (p1, o1, p2, o2, p3, o3) in enumerate(schedules):
        eng = KSpacesCrdtEngine(db_path=tmp_path / f"crdt_order_{idx}.db")
        assert eng.journal_mode == "wal"
        eng.apply_ops("ws-sync", p1, o1)
        eng.apply_ops("ws-sync", p2, o2)
        eng.apply_ops("ws-sync", p3, o3)
        states.append(eng.get_state("ws-sync"))
        eng.close()

    assert states[0]["state_digest_sha256"] == states[1]["state_digest_sha256"] == states[2]["state_digest_sha256"]
    assert states[0]["vector_clock"] == states[1]["vector_clock"] == states[2]["vector_clock"]
    assert states[0]["entries"] == states[1]["entries"] == states[2]["entries"]
    assert states[0]["active_keys_count"] == 4

    by_ns_key = {(e["namespace"], e["key"]): e for e in states[0]["entries"]}
    assert by_ns_key[("issues", "ISS-TIE")]["value"] == "from-peer-c"
    assert by_ns_key[("issues", "ISS-TIE")]["peer_id"] == "peer-c"
    assert by_ns_key[("docs", "DOC-1")]["tombstone"] is True and by_ns_key[("docs", "DOC-1")]["value"] is None

    durable_db = tmp_path / "crdt_order_0.db"
    reopened = KSpacesCrdtEngine(db_path=durable_db)
    try:
        dup = reopened.apply_ops("ws-sync", "peer-a", ops_a)
        assert dup["applied_count"] == 0 and dup["state_digest_sha256"] == states[0]["state_digest_sha256"]

        stale = reopened.apply_ops(
            "ws-sync", "peer-z",
            [{"namespace": "docs", "key": "DOC-1", "op": "set", "value": "Stale", "lamport_ts": 2}],
        )
        assert stale["applied_count"] == 0

        resurrected = reopened.apply_ops(
            "ws-sync", "peer-a",
            [{"namespace": "docs", "key": "DOC-1", "op": "set", "value": "Resurrected v2", "lamport_ts": 9}],
        )
        assert resurrected["applied_count"] == 1 and resurrected["active_keys_count"] == 5

        raw_openai = "sk-proj-SecretCredentialLeak0123456789ABCDEF"
        raw_kw = "kw_live_SovereignSecretToken987654"
        raw_aws = "AKIAIOSFODNN7EXAMPLE"
        reopened.apply_ops(
            "ws-sync", "peer-b",
            [{
                "namespace": "secrets_test", "key": "env_note", "op": "set",
                "value": {"note": f"keys: {raw_openai} {raw_kw} {raw_aws}", "api_key": "raw-unmasked-credential"},
            }],
        )
        ns_state = reopened.get_state("ws-sync", namespace="secrets_test")
        serialized = json.dumps(ns_state["entries"][0]["value"])
        raw_sql = sqlite3.connect(str(durable_db)).execute(
            "SELECT value_json FROM platform_crdt_entries WHERE namespace='secrets_test'"
        ).fetchone()[0]
        for forbidden in (raw_openai, raw_kw, raw_aws, "raw-unmasked-credential"):
            assert forbidden not in serialized and forbidden not in raw_sql
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_fastapi_kflow_crdt_p10_rbac_sbom_and_live_openapi(tmp_path: Path) -> None:
    rbac = WorkspaceRbacController(db_path=tmp_path / "api_p8_rbac.db")
    kflow = KFlowDagEngine(db_path=tmp_path / "api_p8_kflow.db")
    crdt = KSpacesCrdtEngine(db_path=tmp_path / "api_p8_crdt.db")

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_kflow_router)
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac
    test_app.dependency_overrides[get_kflow_engine] = lambda: kflow
    test_app.dependency_overrides[get_kspaces_crdt_engine] = lambda: crdt

    owner_headers = {"Authorization": f"Bearer {launch_token()}"}
    operator_headers = {**owner_headers, "X-Keelway-Role": "operator"}
    builder_headers = {**owner_headers, "X-Keelway-Role": "builder"}
    viewer_headers = {**owner_headers, "X-Keelway-Role": "viewer"}

    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
            assert (
                await client.post(
                    "/v1/platform/automation/workflows/execute",
                    headers=viewer_headers,
                    json={"workflow_id": "WF-API", "nodes": DIAMOND_DAG_NODES},
                )
            ).status_code == 403

            b_hold = await client.post(
                "/v1/platform/automation/workflows/execute",
                headers=builder_headers,
                json={"workflow_id": "WF-API", "nodes": DIAMOND_DAG_NODES},
            )
            assert b_hold.status_code == 200 and b_hold.json()["status"] == "awaiting_p10"

            # CRITICAL P-10 RBAC INVARIANT: builder & viewer get 403 when passing approved_node_ids
            for denied_hdrs in (builder_headers, viewer_headers):
                denied = await client.post(
                    "/v1/platform/automation/workflows/execute",
                    headers=denied_hdrs,
                    json={"workflow_id": "WF-API", "nodes": DIAMOND_DAG_NODES, "approved_node_ids": ["release-gate"]},
                )
                assert denied.status_code == 403

            for allowed_hdrs in (operator_headers, owner_headers):
                ok_res = await client.post(
                    "/v1/platform/automation/workflows/execute",
                    headers=allowed_hdrs,
                    json={"workflow_id": "WF-API", "nodes": DIAMOND_DAG_NODES, "approved_node_ids": ["release-gate"]},
                )
                assert ok_res.status_code == 200 and ok_res.json()["status"] == "completed"

            cyc_res = await client.post(
                "/v1/platform/automation/workflows/execute",
                headers=owner_headers,
                json={"workflow_id": "WF-BAD", "nodes": [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]},
            )
            assert cyc_res.status_code == 400

            runs_res = await client.get("/v1/platform/automation/runs", headers=viewer_headers)
            assert runs_res.status_code == 200 and runs_res.json()["count"] == 3

            assert (
                await client.post(
                    "/v1/platform/kspaces/sync",
                    headers=viewer_headers,
                    json={"peer_id": "peer-v", "operations": [{"key": "k1", "op": "set", "value": 1}]},
                )
            ).status_code == 403

            sync_ok = await client.post(
                "/v1/platform/kspaces/sync",
                headers=builder_headers,
                json={"peer_id": "peer-b", "operations": [{"key": "sprint_goal", "op": "set", "value": "GA"}]},
            )
            assert sync_ok.status_code == 200 and sync_ok.json()["applied_count"] == 1

            st_ok = await client.get("/v1/platform/kspaces/state", headers=viewer_headers)
            assert st_ok.status_code == 200 and st_ok.json()["active_keys_count"] == 1

            sbom_res = await client.get("/v1/platform/security/sbom", headers=viewer_headers)
            assert sbom_res.status_code == 200
            sbom_body = sbom_res.json()
            assert sbom_body["verified"] is True and sbom_body["verification_status"] == "VERIFIED"
            assert sbom_body["bom_format"] == "CycloneDX" and sbom_body["spec_version"] == "1.5"
            assert sbom_body["component_count"] > 0 and len(sbom_body["root_digest_sha256"]) == 64

        live_paths = live_app.openapi()["paths"]
        for expected in (
            "/v1/platform/automation/workflows/execute",
            "/v1/platform/automation/runs",
            "/v1/platform/kspaces/sync",
            "/v1/platform/kspaces/state",
            "/v1/platform/security/sbom",
        ):
            assert expected in live_paths
    finally:
        kflow.close()
        crdt.close()
        rbac.close()


def test_cli_kflow_kspaces_sync_and_sbom_commands(capsys, tmp_path: Path) -> None:
    db_file = str(tmp_path / "cli_phase8.db")
    nodes_str = json.dumps([
        {"id": "step-1", "label": "Compile Spec", "depends_on": []},
        {"id": "step-2", "label": "Deploy Prod", "depends_on": ["step-1"], "requires_p10": True},
    ])

    assert cli_main([
        "kflow", "execute", "--workflow-id", "WF-CLI", "--nodes-json", nodes_str,
        "--approve-node", "step-2", "--workspace-id", "ws-cli", "--db-path", db_file, "--json",
    ]) == 0
    exec_out = json.loads(capsys.readouterr().out)
    assert exec_out["status"] == "completed" and exec_out["workflow_id"] == "WF-CLI"

    assert cli_main(["kflow", "runs", "--workflow-id", "WF-CLI", "--workspace-id", "ws-cli", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1

    ops_str = json.dumps([{"namespace": "issues", "key": "KEEL-801", "op": "set", "value": {"done": True}, "lamport_ts": 4}])
    assert cli_main([
        "kspaces-sync", "push", "--peer-id", "peer-cli", "--ops-json", ops_str,
        "--workspace-id", "ws-cli", "--db-path", db_file, "--json",
    ]) == 0
    push_out = json.loads(capsys.readouterr().out)
    assert push_out["applied_count"] == 1 and push_out["vector_clock"] == {"peer-cli": 4}

    assert cli_main(["kspaces-sync", "state", "--namespace", "issues", "--workspace-id", "ws-cli", "--db-path", db_file, "--json"]) == 0
    state_out = json.loads(capsys.readouterr().out)
    assert state_out["active_keys_count"] == 1 and state_out["entries"][0]["key"] == "KEEL-801"

    assert cli_main(["sbom", "--verify", "--json"]) == 0
    sbom_out = json.loads(capsys.readouterr().out)
    assert sbom_out["verified"] is True and sbom_out["bom_format"] == "CycloneDX"

    legacy_out = tmp_path / "legacy_sbom.json"
    assert cmd_sbom("generate", out=legacy_out) == 0
    assert cmd_sbom("verify", target=str(legacy_out)) == 0
    capsys.readouterr()


def test_agent_builder_unpack_sibling_prefix_zip_slip_and_zero_tarfile_warnings(tmp_path: Path) -> None:
    dest_dir = tmp_path / "dest"
    sibling_evil_dir = tmp_path / "dest_evil"
    sibling_archive = tmp_path / "sibling_slip.tar.gz"

    with tarfile.open(sibling_archive, "w:gz") as tar:
        bm = json.dumps({"bundle_name": "evil", "files": {}}).encode("utf-8")
        ti_bm = tarfile.TarInfo(name="bundle_manifest.json")
        ti_bm.size, ti_bm.mtime = len(bm), int(time.time())
        tar.addfile(ti_bm, io.BytesIO(bm))

        payload = b"raise SystemExit('pwned')\n"
        ti_evil = tarfile.TarInfo(name="../dest_evil/pwn.py")
        ti_evil.size, ti_evil.mtime = len(payload), int(time.time())
        tar.addfile(ti_evil, io.BytesIO(payload))

    with pytest.raises(PermissionError, match="Directory traversal"):
        AgentBuilder.unpack_bundle(sibling_archive, dest_dir, verify=True)
    assert not (sibling_evil_dir / "pwn.py").exists()

    clean_src = tmp_path / "clean_agent"
    clean_src.mkdir()
    (clean_src / "clean.agent.json").write_text(json.dumps({"name": "clean", "version": "1.0.0"}), encoding="utf-8")
    (clean_src / "runner.py").write_text("x = 42\n", encoding="utf-8")
    clean_archive = tmp_path / "clean_agent.tar.gz"
    AgentBundlePacker.pack(clean_src, clean_archive)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        unpacked = AgentBuilder.unpack_bundle(clean_archive, tmp_path / "clean_dest", verify=True)

    tar_deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning) and "tar" in str(w.message).lower()]
    assert tar_deprecations == [] and unpacked["bundle_name"] == "clean_agent"
