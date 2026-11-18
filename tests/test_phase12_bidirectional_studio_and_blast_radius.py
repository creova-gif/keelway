"""
Phase 12A Verification Suite (`KEEL-STUDIO-019`) — Bidirectional Python/TypeScript KFlow AST Sync,
Deterministic Wave Layout & Cycle Back-Edges, OS Sandbox Blast-Radius Radar, Prompt/Schema
Regression Gate (SQLite WAL + Flight-Tape Golden Evals), 5-Role RBAC, and Sovereign CLI Parity.
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
from core.api.platform_studio_routes import (
    get_blast_radius_engine,
    get_kflow_sync_engine,
    platform_studio_router,
)
from core.main import app as live_app
from core.platform.flight_tape import SQLiteFlightTapeEngine
from core.platform.kflow_bidirectional_sync import (
    KFlowBidirectionalSyncEngine,
    MAX_SOURCE_CODE_BYTES,
    PayloadTooLargeError,
)
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.sandbox_blast_radius import SQLiteSandboxBlastRadiusEngine
from core.security.auth import launch_token


def test_python_code_to_graph_langgraph_interrupt_cycles_and_layout() -> None:
    py_langgraph_src = (
        "from langgraph.graph import StateGraph, START, END\n"
        "from langgraph.types import interrupt\n\n"
        "def intake_fn(state: dict) -> dict:\n"
        "    return {'ticket': state.get('id')}\n\n"
        "def research_fn(state: dict) -> dict:\n"
        "    return {'context': 'kb_hit'}\n\n"
        "def policy_check_fn(state: dict) -> dict:\n"
        "    return {'policy': 'ok'}\n\n"
        "def human_refund_fn(state: dict) -> dict:\n"
        "    decision = interrupt('Approve refund over $250?')\n"
        "    return {'approved': decision}\n\n"
        "workflow = StateGraph(dict)\n"
        "workflow.add_node('intake', intake_fn)\n"
        "workflow.add_node('research', research_fn)\n"
        "workflow.add_node('policy_check', policy_check_fn)\n"
        "workflow.add_node('human_refund', human_refund_fn)\n"
        "workflow.add_edge(START, 'intake')\n"
        "workflow.add_edge('intake', 'research')\n"
        "workflow.add_edge('intake', 'policy_check')\n"
        "workflow.add_edge('research', 'human_refund')\n"
        "workflow.add_edge('policy_check', 'human_refund')\n"
        "workflow.add_conditional_edges('human_refund', router_fn, {'retry': 'research', 'done': END})\n"
    )
    engine = KFlowBidirectionalSyncEngine(db_path=":memory:")
    try:
        res = engine.sync(
            workspace_id="default", direction="code_to_graph", language="python",
            workflow_id="WF-LG-PY", source_code=py_langgraph_src, persist=False,
        )
        assert res["direction"] == "code_to_graph" and res["language"] == "python"
        assert res["persisted"] is False and res["sync_sha256"].startswith("sha256:")
        assert res["p10_locked_nodes"] == ["human_refund"]
        assert res["cycle_back_edges"] == [{"from": "human_refund", "to": "research"}]

        by_id = {n["id"]: n for n in res["nodes"]}
        assert set(by_id.keys()) == {"intake", "research", "policy_check", "human_refund"}
        assert by_id["intake"]["wave"] == 0 and (by_id["intake"]["x"], by_id["intake"]["y"]) == (80, 76)
        assert (by_id["intake"]["line_start"], by_id["intake"]["line_end"]) == (4, 5)
        assert by_id["research"]["wave"] == 1 and (by_id["research"]["x"], by_id["research"]["y"]) == (300, 76)
        assert by_id["research"]["depends_on"] == ["intake"]
        assert by_id["policy_check"]["wave"] == 1 and (by_id["policy_check"]["x"], by_id["policy_check"]["y"]) == (300, 186)
        assert by_id["human_refund"]["wave"] == 2 and (by_id["human_refund"]["x"], by_id["human_refund"]["y"]) == (520, 76)
        assert by_id["human_refund"]["requires_p10"] is True
        assert (by_id["human_refund"]["line_start"], by_id["human_refund"]["line_end"]) == (13, 15)
        assert set(by_id["human_refund"]["depends_on"]) == {"research", "policy_check"}
        assert [e for e in res["edges"] if e["is_cycle"]] == [{"from": "human_refund", "to": "research", "is_cycle": True}]
    finally:
        engine.close()


def test_typescript_code_to_graph_comments_offsets_and_syntax_bounds() -> None:
    ts_src = (
        "// Leading comment with unmatched { and ( that must be ignored\n"
        "/* Block comment\n"
        "   with unbalanced {{{ ))) */\n"
        'import { StateGraph, START, END, interrupt } from "@langchain/langgraph";\n\n'
        "export async function gatherStep(state: Record<string, unknown>) {\n"
        "  return { gathered: true };\n"
        "}\n\n"
        "export async function escalationGate(state: Record<string, unknown>) {\n"
        '  const ok = interrupt("P-10 approval needed");\n'
        "  return { ok };\n"
        "}\n\n"
        "const graph = new StateGraph({});\n"
        'graph.addNode("gather", gatherStep);\n'
        'graph.addNode("escalate", escalationGate);\n'
        'graph.addEdge(START, "gather");\n'
        'graph.addEdge("gather", "escalate");\n'
        'graph.addConditionalEdges("escalate", routeFn, { loop: "gather", finish: END });\n'
    )
    engine = KFlowBidirectionalSyncEngine(db_path=":memory:")
    try:
        res = engine.sync(direction="code_to_graph", language="typescript", workflow_id="WF-LG-TS", source_code=ts_src)
        by_id = {n["id"]: n for n in res["nodes"]}
        assert (by_id["gather"]["line_start"], by_id["gather"]["line_end"]) == (6, 8)
        assert (by_id["escalate"]["line_start"], by_id["escalate"]["line_end"]) == (10, 13)
        assert by_id["escalate"]["requires_p10"] is True
        assert res["p10_locked_nodes"] == ["escalate"]
        assert res["cycle_back_edges"] == [{"from": "escalate", "to": "gather"}]

        with pytest.raises(SyntaxError):
            engine.sync(direction="code_to_graph", language="python", source_code="def broken_syntax(:\n    pass\n")
        with pytest.raises(SyntaxError):
            engine.sync(direction="code_to_graph", language="typescript", source_code="export function bad() {\n  const x = 1;\n")
        with pytest.raises(PayloadTooLargeError, match="source_code exceeds 262144 byte limit"):
            engine.sync(direction="code_to_graph", language="python", source_code="x = 1\n" * ((MAX_SOURCE_CODE_BYTES // 6) + 10))
    finally:
        engine.close()


def test_graph_to_code_roundtrip_python_and_typescript_with_sqlite_wal(tmp_path: Path) -> None:
    db_file = tmp_path / "studio_sync.db"
    sample_nodes = [
        {"id": "ingest_ticket", "label": "Ingest Ticket", "agent_id": "triage-classifier", "depends_on": [], "requires_p10": False},
        {"id": "draft_remediation", "label": "Draft Remediation", "agent_id": "remediation-planner", "depends_on": ["ingest_ticket"], "requires_p10": False},
        {"id": "execute_prod_patch", "label": "Execute Prod Patch", "agent_id": "release-operator", "depends_on": ["draft_remediation"], "requires_p10": True},
    ]
    eng1 = KFlowBidirectionalSyncEngine(db_path=db_file)
    try:
        py_gen = eng1.sync(workspace_id="ws-studio", direction="graph_to_code", language="python", workflow_id="WF-RT-PY", nodes=sample_nodes, persist=True)
        assert py_gen["persisted"] is True
        assert "from core.sdk.client import KeelwayClient" in py_gen["source_code"]
        assert "# P-10 human gate required" in py_gen["source_code"]
        py_back = eng1.sync(workspace_id="ws-studio", direction="code_to_graph", language="python", workflow_id="WF-RT-PY", source_code=py_gen["source_code"])
        assert py_back["nodes"] == py_gen["nodes"] and py_back["edges"] == py_gen["edges"]
        assert py_back["p10_locked_nodes"] == ["execute_prod_patch"]

        ts_gen = eng1.sync(workspace_id="ws-studio", direction="graph_to_code", language="typescript", workflow_id="WF-RT-TS", nodes=sample_nodes, persist=True)
        assert 'import { KeelwayClient } from "@keelway/sdk";' in ts_gen["source_code"]
        assert "export const KFLOW_BLUEPRINT = [" in ts_gen["source_code"]
        ts_back = eng1.sync(workspace_id="ws-studio", direction="code_to_graph", language="typescript", workflow_id="WF-RT-TS", source_code=ts_gen["source_code"])
        assert ts_back["nodes"] == ts_gen["nodes"] and ts_back["edges"] == ts_gen["edges"]
        assert ts_back["p10_locked_nodes"] == ["execute_prod_patch"]
    finally:
        eng1.close()

    eng2 = KFlowBidirectionalSyncEngine(db_path=db_file)
    try:
        saved = eng2.list_syncs(workspace_id="ws-studio")
        assert saved["count"] == 2 and {s["workflow_id"] for s in saved["syncs"]} == {"WF-RT-PY", "WF-RT-TS"}
    finally:
        eng2.close()


def test_sandbox_blast_radius_tiers_and_wal_persistence(tmp_path: Path) -> None:
    db_file = tmp_path / "blast_radius.db"
    eng1 = SQLiteSandboxBlastRadiusEngine(db_path=db_file)
    try:
        nominal = eng1.record_blast_radius(
            workspace_id="default", trace_id="trace-nom-01", workflow_id="WF-01",
            fs_reads=["workspace/src/app.py", "workspace/README.md"], fs_writes=["workspace/out/summary.json"],
            egress_attempts=0, p10_gates_triggered=1, seatbelted=True,
        )
        assert nominal["risk_tier"] == "nominal_confined" and nominal["zero_unapproved_egress"] is True
        assert nominal["syscalls_audited"] == 2 + 1 + 0 + 0 + 1 + 4
        assert nominal["audit_id"].startswith("blast-") and nominal["audit_sha256"].startswith("sha256:")

        contained = eng1.record_blast_radius(
            workspace_id="default", trace_id="trace-guard-02", workflow_id="WF-01",
            fs_reads=["workspace/config.yaml"], blocked_paths=["/etc/passwd", "~/.ssh/id_ed25519"],
            egress_attempts=1, blocked_egress_hosts=["exfil.attacker.example"], p10_gates_triggered=1,
        )
        assert contained["risk_tier"] == "contained_guarded" and contained["zero_unapproved_egress"] is True
        assert contained["syscalls_audited"] == 1 + 0 + 2 + 1 + 1 + 4

        elevated = eng1.record_blast_radius(
            workspace_id="default", trace_id="trace-leak-03", workflow_id="WF-02",
            egress_attempts=2, blocked_egress_hosts=["blocked.example"], seatbelted=False,
        )
        assert elevated["risk_tier"] == "elevated_unblocked_egress" and elevated["zero_unapproved_egress"] is False
    finally:
        eng1.close()

    eng2 = SQLiteSandboxBlastRadiusEngine(db_path=db_file)
    try:
        assert eng2.list_blast_radius_audits(workspace_id="default")["count"] == 3
        filtered = eng2.list_blast_radius_audits(workspace_id="default", trace_id="trace-guard-02")
        assert filtered["count"] == 1 and filtered["audits"][0]["risk_tier"] == "contained_guarded"
    finally:
        eng2.close()


def test_prompt_regression_gate_baseline_promoted_evals_and_dlp_block(tmp_path: Path) -> None:
    db_file = tmp_path / "shared_platform.db"
    gate_eng = SQLiteSandboxBlastRadiusEngine(db_path=db_file)
    tape_eng = SQLiteFlightTapeEngine(db_path=db_file)
    leaked_secret = "sk-live-SuperSensitivePromptSecret998877"
    try:
        base_pass = gate_eng.evaluate_prompt_gate(
            workspace_id="ws-fresh", candidate_prompt_version="p-15", candidate_model_id="keelway-core:7b",
            candidate_prompt_text="Triage incident safely and emit JSON with resolution and confidence.",
            required_json_keys=["resolution", "confidence"], min_pass_rate=0.9,
        )
        assert base_pass["dataset_source"] == "builtin_baseline"
        assert base_pass["cases_evaluated"] == 3 and base_pass["passed_cases"] == 3
        assert base_pass["pass_rate"] == 1.0 and base_pass["verdict"] == "PASS" and base_pass["cost_delta_usd"] < 0.0

        frontier_pass = gate_eng.evaluate_prompt_gate(
            workspace_id="ws-fresh", candidate_prompt_version="p-15-frontier",
            candidate_model_id="gpt-4o", candidate_prompt_text="Triage incident safely and emit JSON.",
        )
        assert frontier_pass["verdict"] == "PASS" and frontier_pass["cost_delta_usd"] > 0.0

        dlp_block = gate_eng.evaluate_prompt_gate(
            workspace_id="ws-fresh", candidate_prompt_version="p-16-leaked", candidate_model_id="keelway-core:7b",
            candidate_prompt_text=f"System key {leaked_secret} and AKIAIOSFODNN7EXAMPLE",
        )
        assert dlp_block["verdict"] == "BLOCK" and dlp_block["dlp_violations"] >= 2 and dlp_block["passed_cases"] == 0

        for idx, forb_tok in enumerate(("FORBID_A", "FORBID_B", "LEGACY_UNSAFE_FLAG"), start=1):
            tape = tape_eng.ingest_traces(
                workspace_id="ws-promoted", workflow_name=f"golden-flow-{idx}",
                spans=[{"node_name": "solver", "span_kind": "llm", "model_id": "gpt-4o", "prompt_text": f"Solve {idx}", "output_text": f"Verified golden_token_{idx}"}],
            )
            tape_eng.promote_trace_to_eval(
                workspace_id="ws-promoted", trace_id=tape["trace_id"], title=f"Promoted Case {idx}",
                expected_substrings=[f"golden_token_{idx}"], forbidden_substrings=[forb_tok],
            )

        prom_pass = gate_eng.evaluate_prompt_gate(
            workspace_id="ws-promoted", candidate_prompt_version="p-17", candidate_model_id="qwen2.5:14b",
            candidate_prompt_text="Structured JSON responder with audit_tag.",
            required_json_keys=["resolution", "confidence", "audit_tag"], min_pass_rate=0.9,
        )
        assert prom_pass["dataset_source"] == "sqlite_eval_cases" and prom_pass["verdict"] == "PASS"
        assert prom_pass["schema_valid_count"] == 3 and prom_pass["cost_delta_usd"] < 0.0

        low_rate_block = gate_eng.evaluate_prompt_gate(
            workspace_id="ws-promoted", candidate_prompt_version="p-18-regress", candidate_model_id="keelway-core:7b",
            candidate_prompt_text="Include LEGACY_UNSAFE_FLAG in output.", min_pass_rate=0.9,
        )
        assert low_rate_block["dlp_violations"] == 0 and low_rate_block["passed_cases"] == 2
        assert low_rate_block["pass_rate"] == pytest.approx(0.6667, abs=1e-4) and low_rate_block["verdict"] == "BLOCK"
        assert gate_eng.list_prompt_gate_runs(workspace_id="ws-promoted")["count"] == 2

        with sqlite3.connect(str(db_file)) as raw_conn:
            assert leaked_secret not in "\n".join(raw_conn.iterdump())
    finally:
        gate_eng.close()
        tape_eng.close()


@pytest.mark.asyncio
async def test_fastapi_studio_routes_5_role_rbac_and_status_codes(tmp_path: Path) -> None:
    db_file = tmp_path / "api_phase12.db"
    sync_eng = KFlowBidirectionalSyncEngine(db_path=db_file)
    blast_eng = SQLiteSandboxBlastRadiusEngine(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_studio_router)
    test_app.dependency_overrides[get_kflow_sync_engine] = lambda: sync_eng
    test_app.dependency_overrides[get_blast_radius_engine] = lambda: blast_eng
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac

    token = launch_token()
    role_headers = {
        r: {"Authorization": f"Bearer {token}", "X-Keelway-Role": r, "X-Keelway-Actor": f"{r}-user"}
        for r in ("owner", "admin", "builder", "operator", "viewer")
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            preview = await client.post(
                "/v1/platform/studio/kflow/sync", headers=role_headers["viewer"],
                json={"workspace_id": "default", "direction": "code_to_graph", "language": "python", "source_code": "def triage_step(state):\n    return state\n", "persist": False},
            )
            assert preview.status_code == 200 and preview.json()["nodes"][0]["id"] == "triage_step"

            assert (await client.post("/v1/platform/studio/kflow/sync", headers=role_headers["viewer"], json={"workspace_id": "default", "direction": "code_to_graph", "language": "python", "source_code": "def f(s):\n    return s\n", "persist": True})).status_code == 403
            assert (await client.post("/v1/platform/studio/kflow/sync", headers=role_headers["viewer"], json={"workspace_id": "default", "direction": "graph_to_code", "language": "python", "nodes": [{"id": "n1"}]})).status_code == 403
            assert (await client.post("/v1/platform/studio/blast-radius/record", headers=role_headers["viewer"], json={"workspace_id": "default", "fs_reads": ["a.py"]})).status_code == 403
            assert (await client.post("/v1/platform/studio/prompt-gate/evaluate", headers=role_headers["viewer"], json={"workspace_id": "default", "candidate_prompt_version": "p-15"})).status_code == 403

            assert (await client.post("/v1/platform/studio/kflow/sync", headers=role_headers["builder"], json={"workspace_id": "default", "direction": "code_to_graph", "language": "python", "source_code": "a = 1\n" * ((MAX_SOURCE_CODE_BYTES // 6) + 8)})).status_code == 413
            assert (await client.post("/v1/platform/studio/kflow/sync", headers=role_headers["builder"], json={"workspace_id": "default", "direction": "code_to_graph", "language": "python", "source_code": "def broken(:\n"})).status_code == 422
            assert (await client.post("/v1/platform/studio/kflow/sync", headers=role_headers["builder"], json={"workspace_id": "default", "direction": "graph_to_code", "language": "python", "nodes": []})).status_code == 400

            g2c = await client.post("/v1/platform/studio/kflow/sync", headers=role_headers["builder"], json={"workspace_id": "default", "direction": "graph_to_code", "language": "python", "nodes": [{"id": "approve_wire", "requires_p10": True}], "persist": True})
            assert g2c.status_code == 200 and g2c.json()["persisted"] is True

            br_post = await client.post("/v1/platform/studio/blast-radius/record", headers=role_headers["builder"], json={"workspace_id": "default", "trace_id": "trace-api-1", "blocked_paths": ["/etc/shadow"], "egress_attempts": 1, "blocked_egress_hosts": ["evil.io"]})
            assert br_post.status_code == 200 and br_post.json()["risk_tier"] == "contained_guarded"

            br_get = await client.get("/v1/platform/studio/blast-radius?workspace_id=default&trace_id=trace-api-1", headers=role_headers["viewer"])
            assert br_get.status_code == 200 and br_get.json()["count"] == 1

            pg_post = await client.post("/v1/platform/studio/prompt-gate/evaluate", headers=role_headers["builder"], json={"workspace_id": "default", "candidate_prompt_version": "p-20", "candidate_model_id": "keelway-core:7b", "candidate_prompt_text": "Safe triage responder."})
            assert pg_post.status_code == 200 and pg_post.json()["verdict"] == "PASS"

            pg_get = await client.get("/v1/platform/studio/prompt-gate/runs?workspace_id=default", headers=role_headers["viewer"])
            assert pg_get.status_code == 200 and pg_get.json()["count"] == 1

        live_paths = live_app.openapi()["paths"]
        for expected_route in (
            "/v1/platform/studio/kflow/sync",
            "/v1/platform/studio/blast-radius/record",
            "/v1/platform/studio/blast-radius",
            "/v1/platform/studio/prompt-gate/evaluate",
            "/v1/platform/studio/prompt-gate/runs",
        ):
            assert expected_route in live_paths
    finally:
        sync_eng.close()
        blast_eng.close()
        rbac.close()


def test_sovereign_cli_kflow_sync_blast_radius_and_prompt_gate(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    db_file = str(tmp_path / "cli_phase12.db")
    nodes_payload = json.dumps([
        {"id": "collect", "label": "Collect", "agent_id": "collector", "depends_on": [], "requires_p10": False},
        {"id": "signoff", "label": "Signoff", "agent_id": "governor", "depends_on": ["collect"], "requires_p10": True},
    ])

    assert cli_main(["kflow-sync", "--direction", "graph_to_code", "--language", "typescript", "--workflow-id", "WF-CLI-01", "--nodes-json", nodes_payload, "--persist", "--workspace-id", "default", "--db-path", db_file, "--json"]) == 0
    ts_synced = json.loads(capsys.readouterr().out)
    assert ts_synced["p10_locked_nodes"] == ["signoff"]
    ts_file = tmp_path / "generated_kflow.ts"
    ts_file.write_text(ts_synced["source_code"], encoding="utf-8")

    assert cli_main(["kflow-sync", "--direction", "code_to_graph", "--file", str(ts_file), "--workspace-id", "default", "--db-path", db_file, "--json"]) == 0
    roundtripped = json.loads(capsys.readouterr().out)
    assert roundtripped["language"] == "typescript" and len(roundtripped["nodes"]) == 2

    assert cli_main(["blast-radius", "record", "--trace-id", "trace-cli-99", "--workflow-id", "WF-CLI-01", "--fs-read", "workspace/main.py", "--blocked-path", "~/.aws/credentials", "--egress-attempts", "1", "--blocked-host", "telemetry.external.io", "--p10-gates", "1", "--workspace-id", "default", "--db-path", db_file, "--json"]) == 0
    br_rec = json.loads(capsys.readouterr().out)
    assert br_rec["risk_tier"] == "contained_guarded" and br_rec["zero_unapproved_egress"] is True

    assert cli_main(["blast-radius", "list", "--workspace-id", "default", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1

    assert cli_main(["prompt-gate", "evaluate", "--prompt-version", "p-cli-1", "--model-id", "keelway-core:7b", "--prompt-text", "Emit structured resolution and confidence JSON.", "--required-key", "resolution", "--required-key", "confidence", "--min-pass-rate", "0.9", "--workspace-id", "default", "--db-path", db_file, "--json"]) == 0
    pg_eval = json.loads(capsys.readouterr().out)
    assert pg_eval["verdict"] == "PASS" and pg_eval["cost_delta_usd"] < 0.0

    assert cli_main(["prompt-gate", "list", "--workspace-id", "default", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1
