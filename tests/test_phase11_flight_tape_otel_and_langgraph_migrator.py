"""
Phase 11A Verification Suite (`KEEL-DEVX-018`) — OTel GenAI Trace Wedge, Pre-Storage DLP Scrubbing,
Deterministic Flight-Tape Time-Travel Replay, 1-Click Trace-to-Eval Dataset Promotion,
100% Static LangGraph AST/Regex Migrator, 5-Role RBAC, and Sovereign CLI Parity.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from cli import main as cli_main
from core.api.platform_devx_routes import (
    get_flight_tape_engine,
    get_langgraph_migrator,
    platform_devx_routes_router,
)
from core.api.platform_kflow_routes import (
    get_kflow_engine,
    router as platform_kflow_router,
)
from core.api.platform_runtime_routes import (
    get_rbac_controller,
    router as platform_runtime_router,
)
from core.main import app as live_app
from core.platform.flight_tape import SQLiteFlightTapeEngine
from core.platform.kflow_crdt import KFlowDagEngine
from core.platform.langgraph_migrator import LangGraphMigrator, MAX_MIGRATION_SOURCE_BYTES
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.security.auth import launch_token


def _sample_otlp_resource_spans(leaked_openai: str, leaked_gh: str, leaked_aws: str) -> list[dict]:
    return [
        {
            "resource": {
                "attributes": [
                    {"key": "service.name", "value": {"stringValue": "langgraph-support-triage"}},
                ]
            },
            "scopeSpans": [
                {
                    "scope": {"name": "opentelemetry.instrumentation.langchain"},
                    "spans": [
                        {
                            "traceId": "otel-trace-00112233",
                            "name": "planner_step",
                            "kind": "SPAN_KIND_CLIENT",
                            "attributes": [
                                {"key": "langgraph.node", "value": {"stringValue": "planner"}},
                                {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                                {
                                    "key": "gen_ai.prompt",
                                    "value": {
                                        "stringValue": f"Triage incident with key {leaked_openai} and Bearer SuperSecretJwtTokenValue999"
                                    },
                                },
                                {
                                    "key": "gen_ai.completion",
                                    "value": {"stringValue": f"Querying repo via {leaked_gh}"},
                                },
                                {"key": "gen_ai.usage.input_tokens", "value": {"intValue": 1200}},
                                {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 400}},
                                {
                                    "key": "langgraph.state",
                                    "value": {
                                        "stringValue": json.dumps(
                                            {
                                                "aws_id": leaked_aws,
                                                "db_url": "postgres://dbadmin:UltraSecretPass!@prod.internal:5432/core",
                                                "password": "PlaintextPassword123!",
                                                "ticket": "INC-402",
                                            }
                                        )
                                    },
                                },
                            ],
                        },
                        {
                            "traceId": "otel-trace-00112233",
                            "name": "tool_lookup_kb",
                            "attributes": [
                                {"key": "tool.name", "value": {"stringValue": "search_runbooks"}},
                                {"key": "tool.arguments", "value": {"stringValue": '{"query": "sqlite wal lock"}'}},
                                {
                                    "key": "tool.output",
                                    "value": {"stringValue": "Runbook RB-19: enable PRAGMA journal_mode=WAL."},
                                },
                            ],
                        },
                        {
                            "traceId": "otel-trace-00112233",
                            "name": "synthesizer_step",
                            "attributes": [
                                {"key": "langgraph.node", "value": {"stringValue": "synthesizer"}},
                                {"key": "gen_ai.request.model", "value": {"stringValue": "gpt-4o"}},
                                {"key": "gen_ai.prompt", "value": {"stringValue": "Draft final remediation summary"}},
                                {
                                    "key": "gen_ai.completion",
                                    "value": {
                                        "stringValue": "Remediation verified: configure SQLite WAL mode with busy timeout."
                                    },
                                },
                                {"key": "gen_ai.usage.input_tokens", "value": {"intValue": 1600}},
                                {"key": "gen_ai.usage.output_tokens", "value": {"intValue": 500}},
                            ],
                        },
                    ],
                }
            ],
        }
    ]


def test_flight_tape_otlp_and_flat_ingest_dlp_scrubbing_replay_and_eval_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dyn_db = tmp_path / "runtime_state" / "platform_runtime.db"
    monkeypatch.setenv("KEELWAY_RUNTIME_DB_PATH", str(dyn_db))

    raw_openai = "sk-proj-LiveSecretKeyMaterial9876543210"
    raw_gh = "ghp_SecretGitHubPatTokenValue1234567890"
    raw_aws = "AKIAIOSFODNN7EXAMPLE"
    raw_pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA7586...\n-----END RSA PRIVATE KEY-----"

    engine = SQLiteFlightTapeEngine()
    try:
        assert Path(engine.db_path) == dyn_db

        with pytest.raises(ValueError, match="at least 1 span"):
            engine.ingest_traces(workspace_id="ws-otel", spans=[])

        # 1. OTLP resourceSpans ingestion + pre-storage DLP scrubbing
        otlp_tape = engine.ingest_traces(
            workspace_id="ws-otel",
            resource_spans=_sample_otlp_resource_spans(raw_openai, raw_gh, raw_aws),
        )
        assert otlp_tape["trace_id"] == "otel-trace-00112233"
        assert otlp_tape["workflow_name"] == "langgraph-support-triage"
        assert otlp_tape["total_steps"] == 3
        assert otlp_tape["dlp_redactions"] >= 5
        assert otlp_tape["total_cost_usd"] > 0.0
        assert otlp_tape["tape_sha256"].startswith("sha256:")
        assert otlp_tape["steps"][1]["span_kind"] == "tool"
        assert otlp_tape["steps"][1]["node_name"] == "search_runbooks"
        assert "[REDACTED_SECRET]" in otlp_tape["steps"][0]["prompt_text"]
        assert "[REDACTED_SECRET]" in otlp_tape["steps"][0]["output_text"]
        assert otlp_tape["steps"][0]["state"]["password"] == "[REDACTED_SECRET]"

        # Flat spans ingestion with PEM & api_key=... secret scrubbing + local model $0 cost
        flat_tape = engine.ingest_traces(
            workspace_id="ws-otel",
            workflow_name="flat-hybrid-agent",
            source_framework="langgraph",
            spans=[
                {
                    "node_name": "draft",
                    "span_kind": "llm",
                    "model_id": "gpt-4o",
                    "prompt_text": f"Summarize key={raw_pem} and api_key=MyRawApiSecret998877",
                    "output_text": "Initial draft complete.",
                    "state": {"iteration": 1},
                    "input_tokens": 2000,
                    "output_tokens": 600,
                },
                {
                    "node_name": "refine",
                    "span_kind": "llm",
                    "model_id": "gpt-4o",
                    "prompt_text": "Refine architecture checklist",
                    "output_text": "Checklist finalized.",
                    "state": {"iteration": 2},
                    "input_tokens": 2400,
                    "output_tokens": 800,
                },
            ],
        )
        assert flat_tape["dlp_redactions"] >= 2
        assert flat_tape["total_cost_usd"] == round((2000 * 0.0025 + 600 * 0.01 + 2400 * 0.0025 + 800 * 0.01) / 1000.0, 6)

        # Verify raw secret bytes NEVER hit SQLite disk (including main DB and WAL file)
        for db_candidate in dyn_db.parent.glob("platform_runtime.db*"):
            raw_bytes = db_candidate.read_bytes()
            for forbidden_secret in (
                raw_openai.encode(),
                raw_gh.encode(),
                raw_aws.encode(),
                b"SuperSecretJwtTokenValue999",
                b"UltraSecretPass!",
                b"PlaintextPassword123!",
                b"MIIEpAIBAAKCAQEA7586",
                b"MyRawApiSecret998877",
            ):
                assert forbidden_secret not in raw_bytes

        # 2. Deterministic counterfactual time-travel replay from step 1 onto local OpenCore model
        replayed = engine.replay_tape(
            workspace_id="ws-otel",
            trace_id=otlp_tape["trace_id"],
            from_step_index=1,
            override_model="keelway-core:7b",
            override_prompt=f"Run offline check without leaking {raw_openai}",
            override_state={"mode": "sovereign_local"},
        )
        assert replayed["trace_id"].startswith("fork-")
        assert replayed["parent_trace_id"] == otlp_tape["trace_id"]
        assert replayed["forked_from_step"] == 1
        assert replayed["cached_steps_reused"] == 1
        assert replayed["cost_delta_usd"] < 0.0
        assert replayed["total_cost_usd"] == 0.0
        assert replayed["tokens_delta"] < 0
        assert replayed["tape_sha256"].startswith("sha256:")
        assert replayed["tape_sha256"] != otlp_tape["tape_sha256"]

        # Step 0 reused verbatim with identical SHA-256; steps >= 1 recomputed deterministically
        assert replayed["steps"][0]["cached_reuse"] is True
        assert replayed["steps"][0]["cost_usd"] == 0.0
        assert replayed["steps"][0]["step_sha256"] == otlp_tape["steps"][0]["step_sha256"]
        assert replayed["steps"][1]["cached_reuse"] is False
        assert replayed["steps"][1]["model_id"] == "keelway-core:7b"
        assert "[REDACTED_SECRET]" in replayed["steps"][1]["prompt_text"]
        assert replayed["steps"][2]["model_id"] == "keelway-core:7b"
        assert replayed["steps"][2]["step_sha256"] != otlp_tape["steps"][2]["step_sha256"]

        # 3. 1-Click Trace-to-Eval promotion & persistence across fresh engine instances
        eval_case = engine.promote_trace_to_eval(
            workspace_id="ws-otel",
            trace_id=otlp_tape["trace_id"],
            title="Support Triage Golden Case",
            created_by="builder-dana",
        )
        assert eval_case["case_id"].startswith("evalcase-")
        assert eval_case["source_trace_id"] == otlp_tape["trace_id"]
        assert len(eval_case["pinned_tool_mocks"]) == 1
        assert eval_case["pinned_tool_mocks"][0]["tool_name"] == "search_runbooks"
        assert len(eval_case["expected_substrings"]) >= 1
        assert "[REDACTED_SECRET]" in eval_case["forbidden_substrings"]
        assert eval_case["case_sha256"].startswith("sha256:")
    finally:
        engine.close()

    # Re-open a brand new engine instance to prove SQLite persistence
    reopened = SQLiteFlightTapeEngine()
    try:
        listed = reopened.list_tapes(workspace_id="ws-otel")
        assert listed["total_tapes"] == 3
        cases = reopened.list_eval_cases(workspace_id="ws-otel")
        assert cases["total_cases"] == 1
        assert cases["cases"][0]["case_id"] == eval_case["case_id"]
        assert cases["cases"][0]["pinned_tool_mocks"][0]["tool_name"] == "search_runbooks"
    finally:
        reopened.close()


def test_langgraph_static_migrator_cycles_p10_gates_legacy_warnings_ts_and_rce_safety(tmp_path: Path) -> None:
    pwn_marker = tmp_path / "rce_must_never_exist.txt"
    py_langgraph_code = f"""
import os
from langchain.chains import LLMChain
from langchain.agents import AgentExecutor
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

# Malicious top-level side effect MUST NEVER execute during static AST migration:
__import__("os").system("touch {pwn_marker}")
open("{pwn_marker}", "w").write("pwned")

def draft_node(state):
    chain = LLMChain(prompt="legacy")
    return {{"draft": "v1"}}

def critic_node(state):
    return {{"score": 0.9}}

def human_publish_gate(state):
    decision = interrupt({{"question": "Approve production release?"}})
    return {{"approved": decision}}

def route_critic(state):
    return "revise" if state.get("score", 0) < 0.8 else "publish"

workflow = StateGraph(ReleaseState)
workflow.add_node("draft", draft_node)
workflow.add_node("critic", critic_node)
workflow.add_node("publish_gate", human_publish_gate)
workflow.add_edge(START, "draft")
workflow.add_edge("draft", "critic")
workflow.add_conditional_edges("critic", route_critic, {{"revise": "draft", "publish": "publish_gate"}})
workflow.add_edge("publish_gate", END)
app = workflow.compile()
"""
    migrator = LangGraphMigrator()
    res = migrator.migrate_source(
        source_code=py_langgraph_code,
        source_language="python",
        workflow_name="release-reflection-loop",
        workspace_id="ws-mig",
    )

    assert not pwn_marker.exists(), "Static migrator MUST NEVER execute untrusted source code!"
    assert res["workspace_id"] == "ws-mig"
    assert res["workflow_name"] == "release-reflection-loop"
    assert res["source_language"] == "python"
    assert [n["id"] for n in res["nodes"]] == ["draft", "critic", "publish_gate"]
    assert res["cycles_detected"] == 1
    assert res["bounded_loop_policies"][0]["cycle_path"] == ["draft", "critic", "draft"]
    assert res["bounded_loop_policies"][0]["max_iterations"] == 5
    assert res["bounded_loop_policies"][0]["timeout_seconds"] == 60
    assert res["p10_gates_injected"] == ["publish_gate"]
    gate_node = [n for n in res["nodes"] if n["id"] == "publish_gate"][0]
    assert gate_node["kind"] == "p10_human_gate"
    assert len(res["legacy_warnings"]) >= 3
    assert any("LLMChain" in w for w in res["legacy_warnings"])
    assert any("AgentExecutor" in w for w in res["legacy_warnings"])
    assert "KeelwayClient" in res["generated_sdk_code"]
    assert res["migration_sha256"].startswith("sha256:")

    # Prove 100% compatibility of `kflow_blueprint` with `KFlowDagEngine` (pauses at P-10, completes on approval!)
    dag_engine = KFlowDagEngine(db_path=tmp_path / "kflow_compat.db")
    try:
        held_run = dag_engine.execute_dag("ws-mig", res["workflow_name"], res["kflow_blueprint"])
        assert held_run["status"] == "awaiting_p10"
        assert held_run["held_node_id"] == "publish_gate"

        approved_run = dag_engine.execute_dag(
            "ws-mig",
            res["workflow_name"],
            res["kflow_blueprint"],
            approved_node_ids=["publish_gate"],
        )
        assert approved_run["status"] == "completed"
    finally:
        dag_engine.close()

    # TypeScript StateGraph migration
    ts_code = """
import { StateGraph, START, END, NodeInterrupt } from "@langchain/langgraph";
import { ConversationChain } from "langchain/chains";

const reviewNode = async (state: any) => {
  throw new NodeInterrupt("Requires operator sign-off");
};

const graph = new StateGraph(TriageAnnotation)
  .addNode("ingest", ingestFn)
  .addNode("verify", verifyFn)
  .addNode("review", reviewNode)
  .addEdge(START, "ingest")
  .addEdge("ingest", "verify")
  .addConditionalEdges("verify", checkQuality, { retry: "ingest", escalate: "review" })
  .addEdge("review", END);
"""
    ts_res = migrator.migrate_source(ts_code, source_language="typescript", workspace_id="ws-mig")
    assert ts_res["source_language"] == "typescript"
    assert ts_res["cycles_detected"] == 1
    assert ts_res["p10_gates_injected"] == ["review"]
    assert any("ConversationChain" in w for w in ts_res["legacy_warnings"])

    with pytest.raises(ValueError, match="Invalid Python syntax"):
        migrator.migrate_source("def broken_graph(:\n    pass", source_language="python")

    with pytest.raises(ValueError, match="exceeds maximum"):
        migrator.migrate_source("x = 1\n" * (MAX_MIGRATION_SOURCE_BYTES // 4), source_language="python")


@pytest.mark.asyncio
async def test_fastapi_devx_routes_and_5_role_rbac(tmp_path: Path) -> None:
    db_file = tmp_path / "api_phase11.db"
    engine = SQLiteFlightTapeEngine(db_path=db_file)
    migrator = LangGraphMigrator()
    rbac = WorkspaceRbacController(db_path=db_file)

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_devx_routes_router)
    test_app.dependency_overrides[get_flight_tape_engine] = lambda: engine
    test_app.dependency_overrides[get_langgraph_migrator] = lambda: migrator
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac

    token = launch_token()
    role_headers = {
        r: {"Authorization": f"Bearer {token}", "X-Keelway-Role": r, "X-Keelway-Actor": f"{r}-user"}
        for r in ("owner", "admin", "builder", "operator", "viewer")
    }

    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Viewer denied (403) on all mutating/compute routes
            assert (
                await client.post(
                    "/v1/platform/traces/ingest",
                    headers=role_headers["viewer"],
                    json={"workspace_id": "default", "spans": [{"name": "s0", "prompt": "hi", "output": "ok"}]},
                )
            ).status_code == 403

            assert (
                await client.post(
                    "/v1/platform/traces/trace-1/replay",
                    headers=role_headers["viewer"],
                    json={"workspace_id": "default", "from_step_index": 0},
                )
            ).status_code == 403

            assert (
                await client.post(
                    "/v1/platform/eval/dataset/promote",
                    headers=role_headers["viewer"],
                    json={"workspace_id": "default", "trace_id": "trace-1"},
                )
            ).status_code == 403

            assert (
                await client.post(
                    "/v1/platform/migrate/langgraph",
                    headers=role_headers["viewer"],
                    json={"workspace_id": "default", "source_code": "x = 1"},
                )
            ).status_code == 403

            # Builder allowed (200) on ingest, replay, promote, and migrate; 400/404 error contracts enforced
            assert (
                await client.post(
                    "/v1/platform/traces/ingest",
                    headers=role_headers["builder"],
                    json={"workspace_id": "default", "spans": []},
                )
            ).status_code == 400

            ing_resp = await client.post(
                "/v1/platform/traces/ingest",
                headers=role_headers["builder"],
                json={
                    "workspace_id": "default",
                    "resourceSpans": _sample_otlp_resource_spans(
                        "sk-live-ApiRouteSecret12345678",
                        "ghp_ApiRouteGitHubSecret12345678",
                        "AKIAIOSFODNN7EXAMPLE",
                    ),
                },
            )
            assert ing_resp.status_code == 200
            tid = ing_resp.json()["trace_id"]

            # Viewer allowed (200) on GET /traces and GET /eval/dataset
            list_resp = await client.get("/v1/platform/traces?workspace_id=default", headers=role_headers["viewer"])
            assert list_resp.status_code == 200 and list_resp.json()["total_tapes"] == 1

            assert (
                await client.post(
                    "/v1/platform/traces/nonexistent-trace/replay",
                    headers=role_headers["builder"],
                    json={"workspace_id": "default", "from_step_index": 0},
                )
            ).status_code == 404

            assert (
                await client.post(
                    f"/v1/platform/traces/{tid}/replay",
                    headers=role_headers["builder"],
                    json={"workspace_id": "default", "from_step_index": 99},
                )
            ).status_code == 400

            rep_resp = await client.post(
                f"/v1/platform/traces/{tid}/replay",
                headers=role_headers["builder"],
                json={"workspace_id": "default", "from_step_index": 1, "override_model": "keelway-core:7b"},
            )
            assert rep_resp.status_code == 200 and rep_resp.json()["cost_delta_usd"] < 0.0

            prom_resp = await client.post(
                "/v1/platform/eval/dataset/promote",
                headers=role_headers["builder"],
                json={"workspace_id": "default", "trace_id": tid, "title": "API Promoted Eval"},
            )
            assert prom_resp.status_code == 200 and prom_resp.json()["created_by"] == "builder-user"

            ds_resp = await client.get("/v1/platform/eval/dataset?workspace_id=default", headers=role_headers["viewer"])
            assert ds_resp.status_code == 200 and ds_resp.json()["total_cases"] == 1

            bad_mig = await client.post(
                "/v1/platform/migrate/langgraph",
                headers=role_headers["builder"],
                json={"workspace_id": "default", "source_code": "def broken(:\n", "source_language": "python"},
            )
            assert bad_mig.status_code == 400

            ok_mig = await client.post(
                "/v1/platform/migrate/langgraph",
                headers=role_headers["builder"],
                json={
                    "workspace_id": "default",
                    "source_language": "python",
                    "workflow_name": "api-mig",
                    "source_code": (
                        "from langgraph.graph import StateGraph, START, END\n"
                        "g = StateGraph(dict)\n"
                        "g.add_node('step_a', fn_a)\n"
                        "g.add_edge(START, 'step_a')\n"
                        "g.add_edge('step_a', END)\n"
                    ),
                },
            )
            assert ok_mig.status_code == 200 and len(ok_mig.json()["kflow_blueprint"]) == 1

        live_paths = live_app.openapi()["paths"]
        for expected_path in (
            "/v1/platform/traces/ingest",
            "/v1/platform/traces",
            "/v1/platform/traces/{trace_id}/replay",
            "/v1/platform/eval/dataset/promote",
            "/v1/platform/eval/dataset",
            "/v1/platform/migrate/langgraph",
        ):
            assert expected_path in live_paths
    finally:
        engine.close()
        rbac.close()


def test_cli_traces_trace_eval_and_migrate_langgraph_json(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    db_file = str(tmp_path / "cli_phase11.db")
    spans_file = tmp_path / "spans.json"
    spans_file.write_text(
        json.dumps(
            {
                "workflow_name": "cli-agent-flow",
                "spans": [
                    {
                        "node_name": "planner",
                        "span_kind": "llm",
                        "model_id": "gpt-4o",
                        "prompt_text": "Plan task with sk-live-CliSecretToken1234567890",
                        "output_text": "Calling lookup tool",
                        "input_tokens": 1000,
                        "output_tokens": 300,
                    },
                    {
                        "node_name": "lookup_docs",
                        "span_kind": "tool",
                        "prompt_text": '{"topic": "kflow"}',
                        "output_text": "KFlow executes acyclic topological waves.",
                    },
                    {
                        "node_name": "writer",
                        "span_kind": "llm",
                        "model_id": "gpt-4o",
                        "prompt_text": "Synthesize answer",
                        "output_text": "Final answer synthesized cleanly.",
                        "input_tokens": 1200,
                        "output_tokens": 400,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    assert (
        cli_main(
            ["traces", "ingest", "--workspace", "default", "--file", str(spans_file), "--db-path", db_file, "--json"]
        )
        == 0
    )
    ingested = json.loads(capsys.readouterr().out)
    assert ingested["dlp_redactions"] == 1 and ingested["total_steps"] == 3
    trace_id = ingested["trace_id"]

    assert (
        cli_main(
            [
                "traces",
                "replay",
                "--workspace",
                "default",
                "--trace-id",
                trace_id,
                "--from-step",
                "1",
                "--override-model",
                "keelway-core:7b",
                "--override-prompt",
                "Offline replay prompt",
                "--db-path",
                db_file,
                "--json",
            ]
        )
        == 0
    )
    replayed = json.loads(capsys.readouterr().out)
    assert replayed["cached_steps_reused"] == 1 and replayed["cost_delta_usd"] < 0.0

    assert cli_main(["traces", "list", "--workspace", "default", "--db-path", db_file, "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["total_tapes"] == 2

    assert (
        cli_main(
            [
                "trace-eval",
                "promote",
                "--workspace",
                "default",
                "--trace-id",
                trace_id,
                "--title",
                "CLI Eval Case",
                "--db-path",
                db_file,
                "--json",
            ]
        )
        == 0
    )
    promoted = json.loads(capsys.readouterr().out)
    assert promoted["title"] == "CLI Eval Case" and len(promoted["pinned_tool_mocks"]) == 1

    assert cli_main(["trace-eval", "list", "--workspace", "default", "--db-path", db_file, "--json"]) == 0
    eval_list = json.loads(capsys.readouterr().out)
    assert eval_list["total_cases"] == 1

    graph_py = tmp_path / "agent_graph.py"
    graph_py.write_text(
        "from langgraph.graph import StateGraph, START, END\n"
        "from langgraph.types import interrupt\n"
        "def gate(s):\n"
        "    return interrupt('confirm')\n"
        "g = StateGraph(dict)\n"
        "g.add_node('draft', draft_fn)\n"
        "g.add_node('gate', gate)\n"
        "g.add_edge(START, 'draft')\n"
        "g.add_conditional_edges('draft', router, {'loop': 'draft', 'done': 'gate'})\n"
        "g.add_edge('gate', END)\n",
        encoding="utf-8",
    )
    assert (
        cli_main(
            [
                "migrate-langgraph",
                "--workspace",
                "default",
                "--file",
                str(graph_py),
                "--lang",
                "python",
                "--name",
                "cli-migrated-flow",
                "--json",
            ]
        )
        == 0
    )
    mig_out = json.loads(capsys.readouterr().out)
    assert mig_out["workflow_name"] == "cli-migrated-flow"
    assert mig_out["cycles_detected"] == 1
    assert mig_out["p10_gates_injected"] == ["gate"]

    # CLI end-to-end: feed the migrated blueprint straight into the KFlow executor.
    blueprint_json = json.dumps(mig_out["kflow_blueprint"])
    assert (
        cli_main(
            [
                "kflow",
                "execute",
                "--workspace-id",
                "default",
                "--workflow-id",
                mig_out["workflow_name"],
                "--nodes-json",
                blueprint_json,
                "--db-path",
                db_file,
                "--json",
            ]
        )
        == 0
    )
    held = json.loads(capsys.readouterr().out)
    assert held["status"] == "awaiting_p10" and held["held_node_id"] == "gate"

    assert (
        cli_main(
            [
                "kflow",
                "execute",
                "--workspace-id",
                "default",
                "--workflow-id",
                mig_out["workflow_name"],
                "--nodes-json",
                blueprint_json,
                "--approve-node",
                "gate",
                "--db-path",
                db_file,
                "--json",
            ]
        )
        == 0
    )
    approved = json.loads(capsys.readouterr().out)
    assert approved["status"] == "completed"

    assert cli_main(["kflow", "runs", "--workspace-id", "default", "--db-path", db_file, "--json"]) == 0
    kflow_runs = json.loads(capsys.readouterr().out)
    assert kflow_runs["count"] >= 2


@pytest.mark.asyncio
async def test_langgraph_import_to_governed_run_e2e(tmp_path: Path) -> None:
    """Public-surface E2E: migrate real LangGraph source via the API, feed the returned
    kflow_blueprint into the governed KFlow execute route, and verify P-10 pause,
    RBAC-gated approval, completion, and durable run receipts."""
    rbac = WorkspaceRbacController(db_path=tmp_path / "e2e_rbac.db")
    kflow = KFlowDagEngine(db_path=tmp_path / "e2e_kflow.db")

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_devx_routes_router)
    test_app.include_router(platform_kflow_router)
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac
    test_app.dependency_overrides[get_langgraph_migrator] = lambda: LangGraphMigrator()
    test_app.dependency_overrides[get_kflow_engine] = lambda: kflow

    token = launch_token()
    base = {"Authorization": f"Bearer {token}"}
    builder_headers = {**base, "X-Keelway-Role": "builder", "X-Keelway-Actor": "builder-e2e"}
    operator_headers = {**base, "X-Keelway-Role": "operator", "X-Keelway-Actor": "operator-e2e"}
    viewer_headers = {**base, "X-Keelway-Role": "viewer", "X-Keelway-Actor": "viewer-e2e"}

    graph_source = (
        "from langgraph.graph import StateGraph, START, END\n"
        "from langgraph.types import interrupt\n"
        "def fetch(state):\n"
        "    return {'rows': 1}\n"
        "def human_review(state):\n"
        "    return interrupt({'question': 'approve?'})\n"
        "g = StateGraph(dict)\n"
        "g.add_node('fetch', fetch)\n"
        "g.add_node('gate', human_review)\n"
        "g.add_edge(START, 'fetch')\n"
        "g.add_edge('fetch', 'gate')\n"
        "g.add_edge('gate', END)\n"
        "app = g.compile()\n"
    )

    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # 1. Static migration through the public route.
            mig = await client.post(
                "/v1/platform/migrate/langgraph",
                headers=builder_headers,
                json={
                    "workspace_id": "default",
                    "source_language": "python",
                    "workflow_name": "e2e-imported-flow",
                    "source_code": graph_source,
                },
            )
            assert mig.status_code == 200
            migration = mig.json()
            assert migration["p10_gates_injected"] == ["gate"]
            blueprint = migration["kflow_blueprint"]
            assert [n["id"] for n in blueprint] == ["fetch", "gate"]

            # 2. Execute the imported blueprint through the governed KFlow route.
            execute_payload = {
                "workspace_id": "default",
                "workflow_id": migration["workflow_name"],
                "nodes": blueprint,
                "trigger": "langgraph-import",
            }
            held = await client.post(
                "/v1/platform/automation/workflows/execute",
                headers=builder_headers,
                json=execute_payload,
            )
            assert held.status_code == 200
            held_body = held.json()
            assert held_body["status"] == "awaiting_p10"
            assert held_body["held_node_id"] == "gate"
            assert held_body["receipt_sha256"].startswith("sha256:")
            gate_node = [n for n in held_body["nodes"] if n["id"] == "gate"][0]
            assert gate_node["status"] == "awaiting_p10"
            fetch_node = [n for n in held_body["nodes"] if n["id"] == "fetch"][0]
            assert fetch_node["status"] == "passed"

            # 3. P-10 approval is RBAC-gated: builder lacks p10:approve.
            denied = await client.post(
                "/v1/platform/automation/workflows/execute",
                headers=builder_headers,
                json={**execute_payload, "approved_node_ids": ["gate"]},
            )
            assert denied.status_code == 403

            # 4. Operator holds p10:approve — run completes end-to-end.
            done = await client.post(
                "/v1/platform/automation/workflows/execute",
                headers=operator_headers,
                json={**execute_payload, "approved_node_ids": ["gate"]},
            )
            assert done.status_code == 200
            done_body = done.json()
            assert done_body["status"] == "completed"
            assert all(n["status"] == "passed" for n in done_body["nodes"])
            assert all(n["output_digest"].startswith("sha256:") for n in done_body["nodes"])

            # 5. Both runs are durably persisted with receipts.
            runs = await client.get(
                "/v1/platform/automation/runs?workspace_id=default",
                headers=viewer_headers,
            )
            assert runs.status_code == 200
            runs_body = runs.json()
            assert runs_body["count"] == 2
            statuses = {r["status"] for r in runs_body["runs"]}
            assert statuses == {"awaiting_p10", "completed"}
            assert all(r["receipt_sha256"].startswith("sha256:") for r in runs_body["runs"])

            # 6. Negative path: graphless source refuses honestly.
            bad = await client.post(
                "/v1/platform/migrate/langgraph",
                headers=builder_headers,
                json={
                    "workspace_id": "default",
                    "source_language": "python",
                    "source_code": "x = 1\nprint(x)\n",
                },
            )
            assert bad.status_code == 400
            assert "No LangGraph" in bad.json()["detail"]
    finally:
        kflow.close()
        rbac.close()
