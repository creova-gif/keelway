"""
Phase 11B Tri-SDK OpenTelemetry Flight-Tape Time-Travel, Trace-to-Eval Promotion,
LangGraph Static AST Migration & Website Docs Sync Verification Suite.
"""

from __future__ import annotations

import inspect
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

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

PHASE11_PYTHON_METHODS = (
    "ingest_otel_traces",
    "list_flight_tapes",
    "replay_flight_tape",
    "promote_trace_to_eval",
    "list_eval_dataset_cases",
    "migrate_langgraph_source",
)

FORBIDDEN_PRIVATE_TOKENS = (
    "creova-gif",
    "creovas-projects",
    "kora.git",
    "KEEL-",
    "verify_engineering_gates.sh",
    "Antigravity",
    "gstack",
    "Signup intake is not configured yet",
)


def _make_phase11_mock_transport() -> Tuple[httpx.MockTransport, List[Dict[str, Any]]]:
    recorded: List[Dict[str, Any]] = []
    tapes: Dict[str, Dict[str, Any]] = {}
    eval_cases: Dict[str, Dict[str, Any]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else None
        path, params = request.url.path, dict(request.url.params)
        recorded.append(
            {
                "method": request.method,
                "path": path,
                "params": params,
                "headers": dict(request.headers),
                "json": body,
            }
        )

        if request.headers.get("authorization") == "Bearer kw_live_viewer" and request.method == "POST":
            return httpx.Response(403, json={"detail": "Forbidden for viewer role"})

        if request.method == "POST" and path == "/v1/platform/traces/ingest":
            spans = body.get("spans") or []
            res_spans = body.get("resourceSpans") or body.get("resource_spans") or []
            if not spans and not res_spans:
                return httpx.Response(400, json={"detail": "spans or resourceSpans required"})
            trace_id = body.get("trace_id") or f"ft_py_{len(tapes) + 1}"
            steps = [
                {
                    "step_index": idx,
                    "span_id": sp.get("span_id", f"sp_{idx}"),
                    "name": sp.get("name", f"step_{idx}"),
                    "model": (sp.get("attributes") or {}).get("gen_ai.request.model", "keelway-core:7b"),
                    "prompt": (sp.get("attributes") or {}).get("gen_ai.prompt", ""),
                    "output": (sp.get("attributes") or {}).get("gen_ai.completion", ""),
                    "step_sha256": "a" * 64,
                }
                for idx, sp in enumerate(spans)
            ]
            rec = {
                "trace_id": trace_id,
                "workspace_id": body["workspace_id"],
                "workflow_name": body["workflow_name"],
                "source_framework": body["source_framework"],
                "span_count": len(spans) or len(res_spans),
                "step_count": len(steps) or 1,
                "steps": steps,
                "tape_sha256": "b" * 64,
                "status": "recorded",
            }
            tapes[trace_id] = rec
            return httpx.Response(200, json=rec)

        if request.method == "GET" and path == "/v1/platform/traces":
            ws_id = params.get("workspace_id", "default")
            limit = int(params.get("limit", "20"))
            matched = [t for t in tapes.values() if t["workspace_id"] == ws_id][:limit]
            return httpx.Response(
                200,
                json={
                    "workspace_id": ws_id,
                    "total": len(matched),
                    "tapes": matched,
                },
            )

        if request.method == "POST" and path.startswith("/v1/platform/traces/") and path.endswith("/replay"):
            trace_id = path[len("/v1/platform/traces/") : -len("/replay")]
            if trace_id not in tapes:
                return httpx.Response(404, json={"detail": "Trace not found"})
            orig = tapes[trace_id]
            from_idx = int(body.get("from_step_index", 0))
            fork_id = f"{trace_id}_fork_{len(tapes) + 1}"
            fork_steps = []
            for st in orig["steps"]:
                updated = dict(st)
                if updated["step_index"] == from_idx:
                    if body.get("override_prompt") is not None:
                        updated["prompt"] = body["override_prompt"]
                    if body.get("override_model") is not None:
                        updated["model"] = body["override_model"]
                    if body.get("override_state") is not None:
                        updated["state"] = body["override_state"]
                fork_steps.append(updated)
            forked = {
                **orig,
                "trace_id": fork_id,
                "forked_from_trace_id": trace_id,
                "forked_from_step_index": from_idx,
                "steps": fork_steps,
                "tape_sha256": "c" * 64,
                "status": "replayed_fork",
            }
            tapes[fork_id] = forked
            return httpx.Response(200, json=forked)

        if request.method == "POST" and path == "/v1/platform/eval/dataset/promote":
            tid = body["trace_id"]
            if tid not in tapes:
                return httpx.Response(404, json={"detail": "Trace not found"})
            cid = f"eval_py_{len(eval_cases) + 1}"
            case = {
                "case_id": cid,
                "id": cid,
                "workspace_id": body["workspace_id"],
                "source_trace_id": tid,
                "title": body.get("title") or f"Case from {tid}",
                "expected_substrings": list(body.get("expected_substrings") or []),
                "forbidden_substrings": list(body.get("forbidden_substrings") or []),
                "case_sha256": "d" * 64,
            }
            eval_cases[cid] = case
            return httpx.Response(200, json=case)

        if request.method == "GET" and path == "/v1/platform/eval/dataset":
            ws_id = params.get("workspace_id", "default")
            items = [c for c in eval_cases.values() if c["workspace_id"] == ws_id]
            return httpx.Response(
                200,
                json={"workspace_id": ws_id, "total": len(items), "cases": items},
            )

        if request.method == "POST" and path == "/v1/platform/migrate/langgraph":
            code = body.get("source_code", "")
            if "subprocess.Popen" in code:
                return httpx.Response(400, json={"detail": "Unsafe subprocess rejected by AST importer"})
            return httpx.Response(
                200,
                json={
                    "workspace_id": body["workspace_id"],
                    "workflow_id": "wf_py_migrated",
                    "workflow_name": body.get("workflow_name") or "migrated-langgraph",
                    "source_framework": "langgraph",
                    "source_language": body["source_language"],
                    "nodes": [
                        {"id": "analyze", "requires_p10": False},
                        {"id": "deploy", "requires_p10": True},
                    ],
                    "edges": [{"from": "analyze", "to": "deploy"}],
                    "p10_gates_injected": 1,
                    "ast_digest_sha256": "e" * 64,
                },
            )

        return httpx.Response(404, json={"detail": f"Unhandled {request.method} {path}"})

    return httpx.MockTransport(handler), recorded


def test_python_sync_and_async_signature_parity_and_sync_contracts() -> None:
    for method_name in PHASE11_PYTHON_METHODS:
        sync_sig = inspect.signature(getattr(SyncPlatformClient, method_name))
        async_sig = inspect.signature(getattr(AsyncPlatformClient, method_name))
        assert sync_sig == async_sig, f"Signature drift on {method_name}: {sync_sig} != {async_sig}"

    transport, recorded = _make_phase11_mock_transport()
    with KeelwayClient(token="kw_live_py11_sync", transport=transport) as client:
        with pytest.raises(ValueError, match="trace_id"):
            client.platform.replay_flight_tape("   ")
        with pytest.raises(ValueError, match="from_step_index"):
            client.platform.replay_flight_tape("trace_1", from_step_index=-1)
        with pytest.raises(ValueError, match="trace_id"):
            client.platform.promote_trace_to_eval("")
        with pytest.raises(ValueError, match="source_code"):
            client.platform.migrate_langgraph_source("   ")

        tape = client.platform.ingest_otel_traces(
            [
                {
                    "span_id": "sp_01",
                    "name": "gen_ai.chat",
                    "attributes": {
                        "gen_ai.request.model": "keelway-core:7b",
                        "gen_ai.prompt": "Audit firewall rules",
                        "gen_ai.completion": "Zero open ingress ports detected.",
                    },
                }
            ],
            workspace_id="ws-p11",
            workflow_name="firewall-audit",
            source_framework="opentelemetry_genai",
            trace_id="trace_sync_01",
        )
        assert tape["trace_id"] == "trace_sync_01"
        assert tape["span_count"] == 1
        assert recorded[-1]["json"] == {
            "workspace_id": "ws-p11",
            "workflow_name": "firewall-audit",
            "source_framework": "opentelemetry_genai",
            "spans": [
                {
                    "span_id": "sp_01",
                    "name": "gen_ai.chat",
                    "attributes": {
                        "gen_ai.request.model": "keelway-core:7b",
                        "gen_ai.prompt": "Audit firewall rules",
                        "gen_ai.completion": "Zero open ingress ports detected.",
                    },
                }
            ],
            "trace_id": "trace_sync_01",
        }

        otlp_tape = client.platform.ingest_otel_traces(
            workspace_id="ws-p11",
            resource_spans=[{"scopeSpans": [{"spans": [{"name": "gen_ai.tool"}]}]}],
        )
        assert otlp_tape["span_count"] == 1
        assert "resourceSpans" in recorded[-1]["json"]
        assert "resource_spans" in recorded[-1]["json"]

        listed = client.platform.list_flight_tapes(workspace_id="ws-p11", limit=5)
        assert listed["total"] == 2
        assert recorded[-1]["params"] == {"workspace_id": "ws-p11", "limit": "5"}

        forked = client.platform.replay_flight_tape(
            "trace_sync_01",
            workspace_id="ws-p11",
            from_step_index=0,
            override_prompt="Audit firewall rules with egress strictness",
            override_model="keelway-coder:7b",
            override_state={"egress": "air_gap"},
        )
        assert forked["forked_from_trace_id"] == "trace_sync_01"
        assert forked["steps"][0]["model"] == "keelway-coder:7b"
        assert recorded[-1]["json"] == {
            "workspace_id": "ws-p11",
            "from_step_index": 0,
            "override_prompt": "Audit firewall rules with egress strictness",
            "override_model": "keelway-coder:7b",
            "override_state": {"egress": "air_gap"},
        }

        case = client.platform.promote_trace_to_eval(
            "trace_sync_01",
            workspace_id="ws-p11",
            title="Firewall zero-ingress golden check",
            expected_substrings=["Zero open ingress"],
            forbidden_substrings=["0.0.0.0/0"],
        )
        assert case["source_trace_id"] == "trace_sync_01"
        assert recorded[-1]["json"] == {
            "workspace_id": "ws-p11",
            "trace_id": "trace_sync_01",
            "title": "Firewall zero-ingress golden check",
            "expected_substrings": ["Zero open ingress"],
            "forbidden_substrings": ["0.0.0.0/0"],
        }

        dataset = client.platform.list_eval_dataset_cases(workspace_id="ws-p11")
        assert dataset["total"] == 1
        assert recorded[-1]["params"] == {"workspace_id": "ws-p11"}

        migrated = client.platform.migrate_langgraph_source(
            "from langgraph.graph import StateGraph\ng = StateGraph(dict)\n",
            workspace_id="ws-p11",
            source_language="python",
            workflow_name="firewall-kflow",
        )
        assert migrated["workflow_name"] == "firewall-kflow"
        assert migrated["p10_gates_injected"] == 1

        with pytest.raises(KeelwayError, match="HTTP 400"):
            client.platform.migrate_langgraph_source(
                "import subprocess\nsubprocess.Popen(['sh'])\n",
                workspace_id="ws-p11",
            )

    viewer_transport, _ = _make_phase11_mock_transport()
    with KeelwayClient(token="kw_live_viewer", transport=viewer_transport) as viewer:
        with pytest.raises(PermissionDeniedError):
            viewer.platform.promote_trace_to_eval("trace_sync_01")


async def test_python_async_sdk_and_optional_live_asgi_plus_tri_sdk_symbols() -> None:
    mock_transport, _ = _make_phase11_mock_transport()
    async with AsyncKeelwayClient(token="kw_live_py11_async", transport=mock_transport) as aclient:
        tape = await aclient.platform.ingest_otel_traces(
            [{"span_id": "sp_async_1", "name": "gen_ai.chat"}],
            workspace_id="ws-async-11",
            trace_id="trace_async_01",
        )
        assert tape["trace_id"] == "trace_async_01"
        listed = await aclient.platform.list_flight_tapes(workspace_id="ws-async-11", limit=10)
        assert listed["total"] == 1
        replayed = await aclient.platform.replay_flight_tape(
            "trace_async_01",
            workspace_id="ws-async-11",
            from_step_index=0,
            override_model="keelway-coder:7b",
        )
        assert replayed["forked_from_trace_id"] == "trace_async_01"
        promoted = await aclient.platform.promote_trace_to_eval(
            "trace_async_01",
            workspace_id="ws-async-11",
            title="Async regression case",
        )
        assert promoted["source_trace_id"] == "trace_async_01"
        cases = await aclient.platform.list_eval_dataset_cases(workspace_id="ws-async-11")
        assert cases["total"] == 1
        migrated = await aclient.platform.migrate_langgraph_source(
            "from langgraph.graph import StateGraph\ng = StateGraph(dict)\n",
            workspace_id="ws-async-11",
            workflow_name="async-kflow",
        )
        assert migrated["workflow_name"] == "async-kflow"

    # Opportunistic live ASGI integration check if Phase 11A routes are already mounted
    from httpx import ASGITransport

    from core.main import app
    from core.security.auth import launch_token

    mounted_paths = {getattr(r, "path", "") for r in app.routes}
    if "/v1/platform/traces/ingest" in mounted_paths:
        live_ws = f"ws-live-11-{uuid.uuid4().hex[:8]}"
        async with AsyncKeelwayClient(
            base_url="http://localhost",
            token=launch_token(),
            transport=ASGITransport(app=app),
        ) as live_client:
            live_tape = await live_client.platform.ingest_otel_traces(
                [
                    {
                        "span_id": "sp_live_01",
                        "name": "gen_ai.chat",
                        "attributes": {
                            "gen_ai.request.model": "keelway-core:7b",
                            "gen_ai.prompt": "Verify deterministic sovereign trace replay",
                            "gen_ai.completion": "Flight tape verified.",
                        },
                    }
                ],
                workspace_id=live_ws,
                workflow_name="live-phase11-check",
            )
            live_tid = live_tape["trace_id"]
            live_list = await live_client.platform.list_flight_tapes(workspace_id=live_ws, limit=10)
            assert live_list["workspace_id"] == live_ws
            fork_res = await live_client.platform.replay_flight_tape(
                live_tid,
                workspace_id=live_ws,
                from_step_index=0,
                override_prompt="Counterfactual prompt fork",
            )
            assert fork_res["workspace_id"] == live_ws
            eval_case = await live_client.platform.promote_trace_to_eval(
                live_tid,
                workspace_id=live_ws,
                title="Live ASGI promoted golden eval",
                expected_substrings=["verified"],
            )
            assert eval_case["workspace_id"] == live_ws
            eval_list = await live_client.platform.list_eval_dataset_cases(workspace_id=live_ws)
            assert len(eval_list["cases"]) >= 1
            mig_res = await live_client.platform.migrate_langgraph_source(
                "from langgraph.graph import StateGraph\nworkflow = StateGraph(dict)\nworkflow.add_node('plan', plan_step)\n",
                workspace_id=live_ws,
                workflow_name="live-migrated-dag",
            )
            assert "nodes" in mig_res

    ts_src = (REPO_ROOT / "sdk" / "typescript" / "src" / "platform.ts").read_text(encoding="utf-8")
    ts_devx = (REPO_ROOT / "sdk" / "typescript" / "src" / "platformDevx.ts").read_text(encoding="utf-8")
    ts_dts = (REPO_ROOT / "sdk" / "typescript" / "dist" / "platform.d.ts").read_text(encoding="utf-8")
    for ts_method in (
        "ingestOtelTraces",
        "listFlightTapes",
        "replayFlightTape",
        "promoteTraceToEval",
        "listEvalDatasetCases",
        "migrateLanggraphSource",
    ):
        assert ts_method in ts_src and ts_method in ts_devx and ts_method in ts_dts

    go_src = (REPO_ROOT / "sdk" / "go" / "platform_phase11.go").read_text(encoding="utf-8")
    for go_method in (
        "IngestOtelTraces",
        "ListFlightTapes",
        "ReplayFlightTape",
        "PromoteTraceToEval",
        "ListEvalDatasetCases",
        "MigrateLanggraphSource",
    ):
        assert f"func (p *PlatformService) {go_method}(" in go_src
        assert f"func (c *Client) {go_method}(" in go_src


def test_docs_hub_phase11_line_caps_and_customer_privacy() -> None:
    docs_hub = REPO_ROOT / "website" / "src" / "components" / "docs" / "DocsHub.tsx"
    docs_src = docs_hub.read_text(encoding="utf-8")
    docs_lines = len(docs_src.splitlines())
    assert docs_lines < 500, f"DocsHub.tsx has {docs_lines} lines (must remain < 500)"

    for required_token in (
        "OpenTelemetry GenAI Flight-Tape Time-Travel Debugging",
        "Trace-to-Eval Promotion",
        "migrate-langgraph",
        "Static AST",
    ):
        assert required_token in docs_src, f"Missing '{required_token}' in DocsHub.tsx"

    for token in FORBIDDEN_PRIVATE_TOKENS:
        assert token not in docs_src, f"Forbidden private token '{token}' leaked in DocsHub.tsx"

    phase11b_files = (
        REPO_ROOT / "core" / "sdk" / "platform_devx_client.py",
        REPO_ROOT / "core" / "sdk" / "platform_runtime_client.py",
        REPO_ROOT / "sdk" / "typescript" / "src" / "platformDevx.ts",
        REPO_ROOT / "sdk" / "typescript" / "src" / "platform.ts",
        REPO_ROOT / "sdk" / "typescript" / "src" / "types.ts",
        REPO_ROOT / "sdk" / "typescript" / "src" / "index.ts",
        REPO_ROOT / "sdk" / "typescript" / "tests" / "platform_phase11.test.mjs",
        REPO_ROOT / "sdk" / "go" / "platform_phase11.go",
        REPO_ROOT / "sdk" / "go" / "platform_phase11_test.go",
        REPO_ROOT / "tests" / "test_phase11_sdk_parity.py",
    )
    for file_path in phase11b_files:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 750, f"{file_path.relative_to(REPO_ROOT)} has {line_count} lines (must be < 750)"
