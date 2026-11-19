"""
Phase 12B Tri-SDK Golden-Thread Bidirectional KFlow Studio, Sandbox Blast-Radius Radar,
Prompt Regression Gate & Website Copy/Docs Sync Verification Suite.
"""

from __future__ import annotations

import inspect
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx
import pytest
from httpx import ASGITransport

from core.main import app
from core.sdk import (
    AsyncKeelwayClient,
    AsyncPlatformClient,
    KeelwayClient,
    PermissionDeniedError,
    PolicyViolationError,
    SyncPlatformClient,
)
from core.security.auth import launch_token

REPO_ROOT = Path(__file__).resolve().parent.parent

PHASE12_PYTHON_METHODS = (
    "sync_kflow_studio",
    "record_blast_radius",
    "list_blast_radius_audits",
    "evaluate_prompt_gate",
    "list_prompt_gate_runs",
)

FORBIDDEN_PRIVATE_TOKENS = (
    "creova-gif",
    "creovas-projects",
    "keelway.git",
    "KEEL-",
    "verify_engineering_gates.sh",
    "Antigravity",
    "gstack",
    "Signup intake is not configured yet",
)


def _make_phase12_mock_transport() -> Tuple[httpx.MockTransport, List[Dict[str, Any]]]:
    recorded: List[Dict[str, Any]] = []
    audits: List[Dict[str, Any]] = []
    gate_runs: List[Dict[str, Any]] = []

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

        is_viewer = request.headers.get("authorization") == "Bearer kw_live_viewer"

        if request.method == "POST" and path == "/v1/platform/studio/kflow/sync":
            if is_viewer and (body.get("direction") == "graph_to_code" or body.get("persist")):
                return httpx.Response(403, json={"detail": "Forbidden for viewer role"})
            src = str(body.get("source_code") or "")
            if len(src.encode("utf-8")) > 262_144:
                return httpx.Response(413, json={"detail": "source_code exceeds 262144 bytes"})
            if "def broken(:" in src:
                return httpx.Response(422, json={"detail": "Malformed syntax rejected without eval/exec"})
            raw_nodes = body.get("nodes") or [
                {
                    "id": "plan",
                    "label": "Plan Sprint",
                    "agent_id": "architect",
                    "depends_on": [],
                    "requires_p10": False,
                    "line_start": 1,
                    "line_end": 6,
                    "wave": 0,
                    "x": 80,
                    "y": 120,
                },
                {
                    "id": "ship",
                    "label": "Ship Release",
                    "agent_id": "release-engineer",
                    "depends_on": ["plan"],
                    "requires_p10": True,
                    "line_start": 8,
                    "line_end": 15,
                    "wave": 1,
                    "x": 320,
                    "y": 120,
                },
            ]
            nodes = [
                {
                    "id": n["id"],
                    "label": n.get("label", n["id"]),
                    "agent_id": n.get("agent_id", "feature-coder"),
                    "depends_on": list(n.get("depends_on") or []),
                    "requires_p10": bool(n.get("requires_p10", False)),
                    "line_start": int(n.get("line_start", idx * 8 + 1)),
                    "line_end": int(n.get("line_end", idx * 8 + 6)),
                    "wave": int(n.get("wave", idx)),
                    "x": int(n.get("x", idx * 220 + 80)),
                    "y": int(n.get("y", 120)),
                }
                for idx, n in enumerate(raw_nodes)
            ]
            return httpx.Response(
                200,
                json={
                    "workspace_id": body["workspace_id"],
                    "workflow_id": body["workflow_id"],
                    "direction": body["direction"],
                    "language": body["language"],
                    "nodes": nodes,
                    "edges": [{"from": nodes[0]["id"], "to": nodes[1]["id"], "is_cycle": False}] if len(nodes) > 1 else [],
                    "cycle_back_edges": [],
                    "p10_locked_nodes": [n["id"] for n in nodes if n["requires_p10"]],
                    "source_code": src or "# generated kflow studio python\n",
                    "persisted": bool(body.get("persist", False)),
                    "sync_sha256": "a" * 64,
                },
            )

        if request.method == "POST" and path == "/v1/platform/studio/blast-radius/record":
            if is_viewer:
                return httpx.Response(403, json={"detail": "Forbidden for viewer role"})
            fs_reads = list(body.get("fs_reads") or [])
            fs_writes = list(body.get("fs_writes") or [])
            blocked_paths = list(body.get("blocked_paths") or [])
            blocked_hosts = list(body.get("blocked_egress_hosts") or [])
            egress = int(body.get("egress_attempts") or 0)
            rec = {
                "audit_id": f"blast-py-{len(audits) + 1}",
                "workspace_id": body["workspace_id"],
                "trace_id": body.get("trace_id"),
                "workflow_id": body.get("workflow_id"),
                "fs_reads": fs_reads,
                "fs_writes": fs_writes,
                "blocked_paths": blocked_paths,
                "egress_attempts": egress,
                "blocked_egress_hosts": blocked_hosts,
                "p10_gates_triggered": int(body.get("p10_gates_triggered") or 0),
                "seatbelted": bool(body.get("seatbelted", True)),
                "zero_unapproved_egress": egress == len(blocked_hosts),
                "syscalls_audited": len(fs_reads) + len(fs_writes) + len(blocked_paths) + egress + 4,
                "risk_tier": "elevated" if (blocked_paths or egress) else "contained",
                "audit_sha256": "b" * 64,
                "recorded_at": "2026-11-15T19:00:00Z",
            }
            audits.append(rec)
            return httpx.Response(200, json=rec)

        if request.method == "GET" and path == "/v1/platform/studio/blast-radius":
            ws_id = params.get("workspace_id", "default")
            tid = params.get("trace_id")
            limit = int(params.get("limit", "25"))
            matched = [
                a for a in audits if a["workspace_id"] == ws_id and (not tid or a.get("trace_id") == tid)
            ][:limit]
            return httpx.Response(
                200,
                json={"workspace_id": ws_id, "count": len(matched), "audits": matched},
            )

        if request.method == "POST" and path == "/v1/platform/studio/prompt-gate/evaluate":
            if is_viewer:
                return httpx.Response(403, json={"detail": "Forbidden for viewer role"})
            txt = str(body.get("candidate_prompt_text") or "")
            dlp = 1 if "sk-live-" in txt else 0
            min_rate = float(body.get("min_pass_rate", 0.9))
            pass_rate = 0.5 if dlp else 1.0
            verdict = "PASS" if (dlp == 0 and pass_rate >= min_rate) else "BLOCK"
            run = {
                "gate_run_id": f"pgate-py-{len(gate_runs) + 1}",
                "workspace_id": body["workspace_id"],
                "candidate_prompt_version": body["candidate_prompt_version"],
                "candidate_model_id": body["candidate_model_id"],
                "verdict": verdict,
                "cases_evaluated": 4,
                "passed_cases": 2 if dlp else 4,
                "pass_rate": pass_rate,
                "min_pass_rate": min_rate,
                "schema_valid_count": 4,
                "dlp_violations": dlp,
                "cost_delta_usd": -0.0014,
                "dataset_source": "golden_eval_suite",
                "gate_sha256": "c" * 64,
                "evaluated_at": "2026-11-15T19:05:00Z",
            }
            gate_runs.append(run)
            return httpx.Response(200, json=run)

        if request.method == "GET" and path == "/v1/platform/studio/prompt-gate/runs":
            ws_id = params.get("workspace_id", "default")
            limit = int(params.get("limit", "20"))
            matched = [r for r in gate_runs if r["workspace_id"] == ws_id][:limit]
            return httpx.Response(
                200,
                json={"workspace_id": ws_id, "count": len(matched), "runs": matched},
            )

        return httpx.Response(404, json={"detail": f"Unhandled {request.method} {path}"})

    return httpx.MockTransport(handler), recorded


def test_python_sync_and_async_signature_parity_and_sync_contracts() -> None:
    for method_name in PHASE12_PYTHON_METHODS:
        sync_sig = inspect.signature(getattr(SyncPlatformClient, method_name))
        async_sig = inspect.signature(getattr(AsyncPlatformClient, method_name))
        assert sync_sig == async_sig, f"Signature drift on {method_name}: {sync_sig} != {async_sig}"

    transport, recorded = _make_phase12_mock_transport()
    with KeelwayClient(token="kw_live_py12_sync", transport=transport) as client:
        with pytest.raises(ValueError, match="direction"):
            client.platform.sync_kflow_studio("sideways")
        with pytest.raises(ValueError, match="language"):
            client.platform.sync_kflow_studio(language="cobol")
        with pytest.raises(ValueError, match="workflow_id"):
            client.platform.sync_kflow_studio(workflow_id="   ")
        with pytest.raises(ValueError, match="egress_attempts"):
            client.platform.record_blast_radius(egress_attempts=-1)
        with pytest.raises(ValueError, match="candidate_prompt_version"):
            client.platform.evaluate_prompt_gate("", "keelway-coder:7b")
        with pytest.raises(ValueError, match="candidate_model_id"):
            client.platform.evaluate_prompt_gate("p-15", "   ")
        with pytest.raises(ValueError, match="min_pass_rate"):
            client.platform.evaluate_prompt_gate("p-15", "keelway-coder:7b", min_pass_rate=1.5)

        sync_res = client.platform.sync_kflow_studio(
            "code_to_graph",
            workspace_id="ws-p12",
            language="python",
            workflow_id="WF-STUDIO-12",
            source_code="# @kflow_node id=plan\n# @kflow_node id=ship depends_on=plan requires_p10=true\n",
            persist=False,
        )
        assert sync_res["workflow_id"] == "WF-STUDIO-12"
        assert sync_res["p10_locked_nodes"] == ["ship"]
        assert len(sync_res["sync_sha256"]) == 64

        with pytest.raises(PolicyViolationError, match="Malformed syntax"):
            client.platform.sync_kflow_studio(workspace_id="ws-p12", source_code="def broken(:")

        audit = client.platform.record_blast_radius(
            workspace_id="ws-p12",
            trace_id="trace_sync_12",
            workflow_id="WF-STUDIO-12",
            fs_reads=["core/main.py"],
            fs_writes=["artifacts/out.json"],
            blocked_paths=["/etc/passwd"],
            egress_attempts=1,
            blocked_egress_hosts=["telemetry.invalid"],
            p10_gates_triggered=1,
            seatbelted=True,
        )
        assert audit["zero_unapproved_egress"] is True
        assert len(audit["audit_sha256"]) == 64

        listed_audits = client.platform.list_blast_radius_audits("ws-p12", "trace_sync_12", 10)
        assert listed_audits["count"] == 1
        assert recorded[-1]["params"] == {
            "workspace_id": "ws-p12",
            "trace_id": "trace_sync_12",
            "limit": "10",
        }

        gate_pass = client.platform.evaluate_prompt_gate(
            "p-15",
            "keelway-coder:7b",
            workspace_id="ws-p12",
            candidate_prompt_text="Return strict JSON with summary and risk_tier.",
            required_json_keys=["summary", "risk_tier"],
            min_pass_rate=0.9,
        )
        assert gate_pass["verdict"] == "PASS"
        assert len(gate_pass["gate_sha256"]) == 64

        gate_block = client.platform.evaluate_prompt_gate(
            candidate_prompt_version="p-16-leak",
            candidate_model_id="keelway-coder:7b",
            workspace_id="ws-p12",
            candidate_prompt_text="Hardcoded token sk-live-bad",
        )
        assert gate_block["verdict"] == "BLOCK"
        assert gate_block["dlp_violations"] == 1

        gate_list = client.platform.list_prompt_gate_runs("ws-p12", 5)
        assert gate_list["count"] == 2
        assert recorded[-1]["params"] == {"workspace_id": "ws-p12", "limit": "5"}

    viewer_transport, _ = _make_phase12_mock_transport()
    with KeelwayClient(token="kw_live_viewer", transport=viewer_transport) as viewer:
        preview = viewer.platform.sync_kflow_studio("code_to_graph", workspace_id="ws-p12")
        assert preview["persisted"] is False
        with pytest.raises(PermissionDeniedError):
            viewer.platform.record_blast_radius(workspace_id="ws-p12")


async def test_python_async_sdk_and_optional_live_asgi_plus_tri_sdk_symbols() -> None:
    mock_transport, _ = _make_phase12_mock_transport()
    async with AsyncKeelwayClient(token="kw_live_py12_async", transport=mock_transport) as aclient:
        synced = await aclient.platform.sync_kflow_studio(
            "graph_to_code",
            workspace_id="ws-async-12",
            language="typescript",
            workflow_id="WF-ASYNC-12",
            nodes=[
                {"id": "triage", "label": "Triage", "agent_id": "architect", "requires_p10": False},
                {"id": "deploy", "label": "Deploy", "agent_id": "deployer", "depends_on": ["triage"], "requires_p10": True},
            ],
            persist=True,
        )
        assert synced["persisted"] is True
        audit = await aclient.platform.record_blast_radius(
            workspace_id="ws-async-12",
            trace_id="trace_async_12",
            fs_reads=["sdk/typescript/src/index.ts"],
            seatbelted=True,
        )
        assert audit["seatbelted"] is True
        audits = await aclient.platform.list_blast_radius_audits("ws-async-12", "trace_async_12", 15)
        assert audits["count"] == 1
        gate = await aclient.platform.evaluate_prompt_gate(
            "p-20",
            "keelway-core:7b",
            workspace_id="ws-async-12",
            required_json_keys=["status"],
            min_pass_rate=0.85,
        )
        assert gate["verdict"] == "PASS"
        runs = await aclient.platform.list_prompt_gate_runs("ws-async-12", 10)
        assert runs["count"] == 1

    mounted_paths = {getattr(r, "path", "") for r in app.routes}
    if "/v1/platform/studio/kflow/sync" in mounted_paths:
        live_ws = f"ws-live-12-{uuid.uuid4().hex[:8]}"
        async with AsyncKeelwayClient(
            base_url="http://localhost",
            token=launch_token(),
            transport=ASGITransport(app=app),
        ) as live_client:
            live_sync = await live_client.platform.sync_kflow_studio(
                "graph_to_code",
                workspace_id=live_ws,
                language="python",
                workflow_id="WF-LIVE-12",
                nodes=[
                    {"id": "plan", "label": "Plan", "agent_id": "architect", "depends_on": [], "requires_p10": False},
                    {"id": "ship", "label": "Ship", "agent_id": "release-engineer", "depends_on": ["plan"], "requires_p10": True},
                ],
                persist=True,
            )
            assert live_sync["workspace_id"] == live_ws
            assert len(live_sync["sync_sha256"]) == 64
            live_audit = await live_client.platform.record_blast_radius(
                workspace_id=live_ws,
                workflow_id="WF-LIVE-12",
                fs_reads=["core/main.py"],
                seatbelted=True,
            )
            assert live_audit["workspace_id"] == live_ws
            live_audits = await live_client.platform.list_blast_radius_audits(live_ws)
            assert live_audits["count"] >= 1
            live_gate = await live_client.platform.evaluate_prompt_gate(
                "p-live-12",
                "keelway-core:7b",
                workspace_id=live_ws,
                min_pass_rate=0.5,
            )
            assert live_gate["verdict"] in ("PASS", "BLOCK")
            live_runs = await live_client.platform.list_prompt_gate_runs(live_ws)
            assert live_runs["count"] >= 1

    ts_src = (REPO_ROOT / "sdk" / "typescript" / "src" / "platform.ts").read_text(encoding="utf-8")
    ts_studio = (REPO_ROOT / "sdk" / "typescript" / "src" / "platformStudio.ts").read_text(encoding="utf-8")
    ts_dts = (REPO_ROOT / "sdk" / "typescript" / "dist" / "platform.d.ts").read_text(encoding="utf-8")
    for ts_method in (
        "syncKflowStudio",
        "recordBlastRadius",
        "listBlastRadiusAudits",
        "evaluatePromptGate",
        "listPromptGateRuns",
    ):
        assert ts_method in ts_src and ts_method in ts_studio and ts_method in ts_dts

    go_src = (REPO_ROOT / "sdk" / "go" / "platform_phase12.go").read_text(encoding="utf-8")
    for go_method in (
        "SyncKflowStudio",
        "RecordBlastRadius",
        "ListBlastRadiusAudits",
        "EvaluatePromptGate",
        "ListPromptGateRuns",
    ):
        assert f"func (p *PlatformService) {go_method}(" in go_src
        assert f"func (c *Client) {go_method}(" in go_src


def test_website_phase12_docs_hub_pricing_calibration_and_line_caps() -> None:
    # KEEL-WEB-038: DocsHub.tsx and CustomerJourneyGrid.tsx were retired with
    # the v3 route prune; the same disclosure + privacy contract now binds to
    # product-facts.json, and the pricing contract binds to src/data/pricing.ts.
    facts_src = (REPO_ROOT / "website" / "product-facts.json").read_text(encoding="utf-8")

    for required_token in (
        "Golden-Thread Bidirectional KFlow Studio",
        "kflow-sync",
        "Blast-Radius Radar",
        "blast-radius",
        "Prompt Regression Gate",
        "prompt-gate",
    ):
        assert required_token in facts_src, f"Missing '{required_token}' in product-facts.json"

    for token in FORBIDDEN_PRIVATE_TOKENS:
        assert token not in facts_src, f"Forbidden private token '{token}' leaked in product-facts.json"

    pricing_src = (REPO_ROOT / "website" / "src" / "data" / "pricing.ts").read_text(
        encoding="utf-8"
    ) + (REPO_ROOT / "website" / "src" / "app" / "pricing" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "$29/seat" in pricing_src, "Pro $29/seat pricing must be disclosed on /pricing"
    assert "spend cap" in pricing_src.lower(), "spend caps must be disclosed on /pricing"
    assert "$39/seat" not in pricing_src, "$39/seat pricing must not appear on /pricing"

    phase12b_files = (
        REPO_ROOT / "core" / "sdk" / "platform_studio_client.py",
        REPO_ROOT / "core" / "sdk" / "platform_runtime_client.py",
        REPO_ROOT / "sdk" / "typescript" / "src" / "platformStudio.ts",
        REPO_ROOT / "sdk" / "typescript" / "src" / "platform.ts",
        REPO_ROOT / "sdk" / "typescript" / "src" / "types.ts",
        REPO_ROOT / "sdk" / "typescript" / "src" / "index.ts",
        REPO_ROOT / "sdk" / "typescript" / "tests" / "platform_phase12.test.mjs",
        REPO_ROOT / "sdk" / "go" / "platform_phase12.go",
        REPO_ROOT / "sdk" / "go" / "platform_phase12_test.go",
        REPO_ROOT / "tests" / "test_phase12_sdk_parity.py",
    )
    for file_path in phase12b_files:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 700, f"{file_path.relative_to(REPO_ROOT)} has {line_count} lines (must be < 700)"
