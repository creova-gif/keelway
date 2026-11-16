"""
Phase 16A Verification Suite — Cross-Provider `.content_blocks` Normalizer, JSON-Schema
Structured-Output Enforcer & Single-Pass Repair, Autonomous Self-Healing Root-Causer,
Golden Eval Promotion, 5-Role RBAC FastAPI Routes (`292` OpenAPI paths), and Sovereign CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any, Dict

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from cli import main as cli_main
from core.api.platform_healing_routes import get_structured_healing_engine, platform_healing_router
from core.api.platform_runtime_routes import get_rbac_controller, router as platform_runtime_router
from core.main import app as live_app
from core.platform.rbac_webhooks import WorkspaceRbacController
from core.platform.structured_self_healing import (
    FlightTapeStore,
    SelfHealingNotFoundError,
    SQLiteStructuredHealingEngine,
    StructuredHealingValidationError,
    StructuredSchemaRejectedError,
)
from core.security.auth import launch_token

_CONTRACT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["decision", "invoice_count", "confidence", "escalate", "tags"],
    "additionalProperties": False,
    "properties": {
        "decision": {"type": "string", "enum": ["approve", "reject", "review"]},
        "invoice_count": {"type": "integer", "minimum": 1, "maximum": 100},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "escalate": {"type": "boolean"},
        "tags": {"type": "array", "minItems": 1, "maxItems": 3, "items": {"type": "string"}},
        "audit_note": {"type": "string"},
    },
}


def test_normalize_deepseek_and_openai_with_dlp(tmp_path: Path) -> None:
    eng = SQLiteStructuredHealingEngine(db_path=tmp_path / "norm_ds_oa.db")
    secret_sk, secret_ghp = "sk-live-secret1234567890abcdef", "ghp_1234567890abcdef1234567890abcdef1234"
    try:
        ds = eng.normalize_content_blocks(
            workspace_id="ws-norm",
            provider_format="deepseek_opencore",
            raw_payload={
                "choices": [{
                    "message": {
                        "content": f"<think>Verify key {secret_sk} before triage.</think>\nTriage summary ready.\n```json\n{{\"decision\": \"approve\", \"amount\": 42}}\n```",
                        "tool_calls": [{"id": "call_1", "function": {"name": "lookup_vendor", "arguments": '{"vendor":"acme"}'}}],
                    }
                }]
            },
        )
        assert ds["block_count"] == 4 and [b["kind"] for b in ds["content_blocks"]] == ["reasoning", "text", "structured_json", "tool_call"]
        assert ds["dlp_redactions"] >= 1 and "[REDACTED_SECRET]" in ds["content_blocks"][0]["content"]
        assert secret_sk not in json.dumps(ds)
        assert ds["content_blocks"][2]["structured_data"] == {"decision": "approve", "amount": 42}
        assert ds["content_blocks"][3]["tool_name"] == "lookup_vendor" and ds["envelope_sha256"].startswith("sha256:")

        oa = eng.normalize_content_blocks(
            workspace_id="ws-norm",
            provider_format="openai",
            model_id="gpt-4.1",
            raw_payload={
                "choices": [{
                    "message": {
                        "reasoning_content": "Audited PO line items.",
                        "content": '{"decision": "review"}',
                        "tool_calls": [{"id": "call_oa", "function": {"name": "fetch_po", "arguments": f'{{"tok":"{secret_ghp}"}}'}}],
                        "annotations": [{"url_citation": {"title": "SOC2 Policy", "url": "https://docs.internal/soc2"}}],
                    }
                }]
            },
        )
        assert [b["kind"] for b in oa["content_blocks"]] == ["reasoning", "structured_json", "tool_call", "citation"]
        assert oa["content_blocks"][2]["tool_args"]["tok"] == "[REDACTED_SECRET]" and oa["dlp_redactions"] >= 1
        assert oa["content_blocks"][3]["source_uri"] == "https://docs.internal/soc2"
    finally:
        eng.close()


def test_normalize_anthropic_gemini_and_validation_errors(tmp_path: Path) -> None:
    eng = SQLiteStructuredHealingEngine(db_path=tmp_path / "norm_an_gm.db")
    try:
        an = eng.normalize_content_blocks(
            workspace_id="ws-norm",
            provider_format="anthropic",
            model_id="claude-sonnet-4-5",
            raw_payload={
                "content": [
                    {"type": "thinking", "thinking": "Cross-checking tax ID."},
                    {"type": "tool_use", "id": "toolu_01", "name": "query_ledger", "input": {"ledger_id": "L-9"}},
                    {"type": "text", "text": '{"status": "verified"}', "citations": [{"cited_text": "Clause 4.2", "url": "https://kb.internal/clause-4-2"}]},
                ]
            },
        )
        assert [b["kind"] for b in an["content_blocks"]] == ["reasoning", "tool_call", "structured_json", "citation"]
        assert an["content_blocks"][1]["tool_call_id"] == "toolu_01" and an["content_blocks"][2]["structured_data"] == {"status": "verified"}

        gm = eng.normalize_content_blocks(
            workspace_id="ws-norm",
            provider_format="gemini",
            model_id="gemini-2.5-pro",
            raw_payload={
                "candidates": [{
                    "content": {"parts": [
                        {"thought": True, "text": "Evaluating grounding chunks."},
                        {"functionCall": {"name": "check_budget", "args": {"dept": "eng"}}},
                        {"text": '{"approved": true}'},
                    ]},
                    "groundingMetadata": {"groundingChunks": [{"web": {"title": "Treasury Spec", "uri": "https://spec.internal/treasury"}}]},
                }]
            },
        )
        assert [b["kind"] for b in gm["content_blocks"]] == ["reasoning", "tool_call", "structured_json", "citation"]
        assert gm["content_blocks"][1]["tool_args"] == {"dept": "eng"} and gm["content_blocks"][3]["source_uri"] == "https://spec.internal/treasury"

        with pytest.raises(StructuredHealingValidationError):
            eng.normalize_content_blocks(workspace_id="ws-norm", provider_format="cohere_unknown", raw_payload="{}")
        with pytest.raises(StructuredHealingValidationError):
            eng.normalize_content_blocks(workspace_id="../bad/ws", provider_format="openai", raw_payload={})
    finally:
        eng.close()


def test_enforce_structured_output_valid_repair_strict_and_dlp_wal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_file = tmp_path / "enforce_wal.db"
    monkeypatch.setenv("KEELWAY_RUNTIME_DB_PATH", str(db_file))
    eng = SQLiteStructuredHealingEngine()
    raw_aws = "AKIAIOSFODNN7EXAMPLE"
    try:
        clean_run = eng.enforce_structured_output(
            workspace_id="ws-struct",
            json_schema=_CONTRACT_SCHEMA,
            raw_output={"decision": "approve", "invoice_count": 3, "confidence": 0.96, "escalate": False, "tags": ["po-match"]},
        )
        assert clean_run["status"] == "VALID" and clean_run["repair_applied"] is False and clean_run["repair_actions"] == []
        assert clean_run["run_sha256"].startswith("sha256:")

        messy = (
            f"<think>Using credential {raw_aws} during extraction.</think>\n```json\n"
            '{"decision": "review", "invoice_count": "42", "confidence": "0.91", '
            '"escalate": "true", "tags": ["urgent",], "audit_note": "Key ' + raw_aws + '",}\n```'
        )
        repaired = eng.enforce_structured_output(workspace_id="ws-struct", json_schema=_CONTRACT_SCHEMA, raw_output=messy, strict_mode=False, fail_closed=True)
        assert repaired["status"] == "REPAIRED_VALID" and repaired["repair_applied"] is True
        assert set(repaired["repair_actions"]) == {"strip_think_tags", "strip_markdown_fences", "remove_trailing_commas", "coerce_scalar_types"}
        assert repaired["validated_data"]["invoice_count"] == 42 and repaired["validated_data"]["confidence"] == 0.91
        assert repaired["validated_data"]["escalate"] is True and "[REDACTED_SECRET]" in repaired["validated_data"]["audit_note"]
        assert repaired["dlp_redactions"] >= 2

        with pytest.raises(StructuredSchemaRejectedError) as exc_strict:
            eng.enforce_structured_output(workspace_id="ws-struct", json_schema=_CONTRACT_SCHEMA, raw_output=messy, strict_mode=True, fail_closed=True)
        assert exc_strict.value.run_record["status"] == "SCHEMA_REJECTED"

        soft_reject = eng.enforce_structured_output(
            workspace_id="ws-struct",
            json_schema=_CONTRACT_SCHEMA,
            raw_output={"decision": "bad_enum", "invoice_count": 500, "confidence": -0.5, "escalate": False, "tags": [], "rogue": 1},
            fail_closed=False,
        )
        assert soft_reject["status"] == "SCHEMA_REJECTED" and soft_reject["validated_data"] is None and len(soft_reject["validation_errors"]) >= 4
        assert eng.list_structured_runs(workspace_id="ws-struct", limit=10)["count"] == 4

        with sqlite3.connect(db_file) as raw_conn:
            assert raw_conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
            assert raw_aws not in "\n".join(raw_conn.iterdump())
    finally:
        eng.close()


def test_diagnose_all_five_root_cause_classes(tmp_path: Path) -> None:
    eng = SQLiteStructuredHealingEngine(db_path=tmp_path / "diag5.db")
    try:
        cases = [
            ("schema_mismatch", {"node_name": "parse_json", "error_message": "JSON schema validation failed: missing required key"}),
            ("context_truncation", {"node_name": "summarize_doc", "error_message": "Unterminated string due to max_tokens context window cutoff"}),
            ("prompt_ambiguity", {"node_name": "classify_intent", "error_message": "Output diverged due to ambiguous underspecified prompt"}),
            ("kbrain_conflict", {"node_name": "fetch_policy", "error_message": "Conflicting fact and stale fact in KBrain memory scope"}),
            ("airgap_egress_blocked", {"node_name": "call_remote", "error_message": "Outbound external endpoint blocked by zero-egress airgap policy"}),
        ]
        for expected_cls, step_payload in cases:
            diag = eng.diagnose_failure(workspace_id="ws-heal", workflow_name="wf-check", failed_step=step_payload)
            assert diag["failure_class"] == expected_cls and diag["status"] == "DIAGNOSED"
            assert 0.86 <= diag["confidence"] <= 0.97 and diag["diagnostic_model"] == "keelway-core:7b"
            assert diag["diagnosis_sha256"].startswith("sha256:")
        assert eng.list_diagnoses(workspace_id="ws-heal", limit=20)["count"] == 5
    finally:
        eng.close()


def test_flight_tape_trace_diagnosis_and_golden_eval_promotion(tmp_path: Path) -> None:
    db_file = tmp_path / "heal_tape.db"
    eng = SQLiteStructuredHealingEngine(db_path=db_file)
    tape_store = FlightTapeStore(db_file)
    try:
        ingested = tape_store.ingest_traces(
            workspace_id="ws-heal",
            workflow_name="treasury-settlement",
            trace_id="trace-heal-001",
            spans=[
                {"node_name": "load_invoice", "prompt_text": "Load INV-9", "output_text": "Loaded INV-9"},
                {"node_name": "route_cloud", "prompt_text": "Send Bearer secret-xyz987654321", "output_text": "Error: air-gap zero-egress blocked outbound call"},
            ],
        )
        assert ingested["trace_id"] == "trace-heal-001"

        tape_diag = eng.diagnose_failure(workspace_id="ws-heal", trace_id="trace-heal-001")
        assert tape_diag["failure_class"] == "airgap_egress_blocked" and tape_diag["failed_node"] == "route_cloud"
        assert tape_diag["workflow_name"] == "treasury-settlement"

        applied = eng.apply_healing_patch(workspace_id="ws-heal", diagnosis_id=tape_diag["diagnosis_id"], promote_to_eval=True, eval_title="Treasury Air-Gap Regression")
        assert applied["verified_healed"] is True and applied["replay_cost_usd"] == 0.0 and applied["cached_steps_reused"] >= 1
        assert applied["diagnosis"]["status"] == "VERIFIED_HEALED" and applied["diagnosis"]["verification_replay_trace_id"].startswith("replay-heal-")
        promoted = applied["promoted_eval_case"]
        assert promoted is not None and promoted["title"] == "Treasury Air-Gap Regression"
        assert any(c["case_id"] == promoted["case_id"] for c in tape_store.list_eval_cases(workspace_id="ws-heal")["cases"])

        with pytest.raises(SelfHealingNotFoundError):
            eng.diagnose_failure(workspace_id="ws-heal", trace_id="trace-does-not-exist")
        with pytest.raises(SelfHealingNotFoundError):
            eng.apply_healing_patch(workspace_id="ws-heal", diagnosis_id="diag-missing")
    finally:
        tape_store.close()
        eng.close()


@pytest.mark.asyncio
async def test_fastapi_routes_five_role_rbac_and_fail_closed_modes(tmp_path: Path) -> None:
    db_file = tmp_path / "api_phase16.db"
    heal_eng = SQLiteStructuredHealingEngine(db_path=db_file)
    rbac = WorkspaceRbacController(db_path=db_file)

    test_app = FastAPI()
    test_app.include_router(platform_runtime_router)
    test_app.include_router(platform_healing_router)
    test_app.dependency_overrides[get_structured_healing_engine] = lambda: heal_eng
    test_app.dependency_overrides[get_rbac_controller] = lambda: rbac

    token = launch_token()
    headers = {
        r: {"Authorization": f"Bearer {token}", "X-Keelway-Role": r, "X-Keelway-Actor": f"{r}-user"}
        for r in ("owner", "admin", "developer", "operator", "auditor")
    }
    try:
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            norm_res = await client.post("/v1/platform/healing/content-blocks/normalize", headers=headers["auditor"], json={"workspace_id": "default", "provider_format": "deepseek_opencore", "raw_payload": "<think>ok</think>{\"a\":1}"})
            assert norm_res.status_code == 200 and norm_res.json()["block_count"] == 2
            assert (await client.get("/v1/platform/healing/structured/runs?workspace_id=default", headers=headers["auditor"])).status_code == 200
            assert (await client.get("/v1/platform/healing/root-cause/diagnoses?workspace_id=default", headers=headers["auditor"])).status_code == 200

            assert (await client.post("/v1/platform/healing/structured/enforce", headers=headers["auditor"], json={"workspace_id": "default", "json_schema": _CONTRACT_SCHEMA, "raw_output": "{}"})).status_code == 403
            assert (await client.post("/v1/platform/healing/root-cause/diagnose", headers=headers["auditor"], json={"workspace_id": "default"})).status_code == 403
            assert (await client.post("/v1/platform/healing/root-cause/diag-any/apply", headers=headers["auditor"], json={"workspace_id": "default"})).status_code == 403

            repaired_raw = "<think>fix</think>```json\n{\"decision\":\"approve\",\"invoice_count\":\"2\",\"confidence\":\"0.9\",\"escalate\":\"false\",\"tags\":[\"ok\",]}\n```"
            for write_role in ("owner", "admin", "developer", "operator"):
                enf_ok = await client.post("/v1/platform/healing/structured/enforce", headers=headers[write_role], json={"workspace_id": "default", "json_schema": _CONTRACT_SCHEMA, "raw_output": repaired_raw})
                assert enf_ok.status_code == 200 and enf_ok.json()["status"] == "REPAIRED_VALID"

            rej_422 = await client.post("/v1/platform/healing/structured/enforce", headers=headers["developer"], json={"workspace_id": "default", "json_schema": _CONTRACT_SCHEMA, "raw_output": '{"decision":"invalid"}', "fail_closed": True})
            assert rej_422.status_code == 422 and rej_422.json()["code"] == "structured_schema_rejected"

            rej_200 = await client.post("/v1/platform/healing/structured/enforce", headers=headers["developer"], json={"workspace_id": "default", "json_schema": _CONTRACT_SCHEMA, "raw_output": '{"decision":"invalid"}', "fail_closed": False})
            assert rej_200.status_code == 200 and rej_200.json()["status"] == "SCHEMA_REJECTED"

            diag_res = await client.post("/v1/platform/healing/root-cause/diagnose", headers=headers["operator"], json={"workspace_id": "default", "failed_step": {"node_name": "step_x", "error_message": "kbrain memory conflict detected"}})
            assert diag_res.status_code == 200 and diag_res.json()["failure_class"] == "kbrain_conflict"
            diag_id = diag_res.json()["diagnosis_id"]

            app_res = await client.post(f"/v1/platform/healing/root-cause/{diag_id}/apply", headers=headers["admin"], json={"workspace_id": "default", "promote_to_eval": True})
            assert app_res.status_code == 200 and app_res.json()["verified_healed"] is True
            assert (await client.post("/v1/platform/healing/root-cause/diagnose", headers=headers["owner"], json={"workspace_id": "default", "trace_id": "ghost-trace"})).status_code == 404
            assert (await client.post("/v1/platform/healing/root-cause/diag-ghost/apply", headers=headers["owner"], json={"workspace_id": "default"})).status_code == 404
    finally:
        heal_eng.close()
        rbac.close()


def test_live_openapi_has_292_paths_including_six_healing_routes() -> None:
    openapi_paths = live_app.openapi()["paths"]
    assert len(openapi_paths) == 292
    for route in (
        "/v1/platform/healing/content-blocks/normalize",
        "/v1/platform/healing/structured/enforce",
        "/v1/platform/healing/structured/runs",
        "/v1/platform/healing/root-cause/diagnose",
        "/v1/platform/healing/root-cause/{diagnosis_id}/apply",
        "/v1/platform/healing/root-cause/diagnoses",
    ):
        assert route in openapi_paths


def test_sovereign_cli_structured_and_heal_json_commands(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    db_file = str(tmp_path / "cli_phase16.db")

    assert cli_main(["structured", "normalize", "--provider-format", "deepseek_opencore", "--payload", "<think>plan</think>```json\n{\"decision\":\"approve\"}\n```", "--workspace-id", "ws-cli16", "--db-path", db_file, "--json"]) == 0
    norm_out = json.loads(capsys.readouterr().out)
    assert norm_out["block_count"] == 2 and norm_out["content_blocks"][0]["kind"] == "reasoning"

    assert cli_main(["structured", "enforce", "--output", "<think>r</think>```json\n{\"decision\":\"approve\",\"confidence\":\"0.88\",}\n```", "--workspace-id", "ws-cli16", "--db-path", db_file, "--json"]) == 0
    enf_out = json.loads(capsys.readouterr().out)
    assert enf_out["status"] == "REPAIRED_VALID" and enf_out["validated_data"]["confidence"] == 0.88

    assert cli_main(["structured", "enforce", "--strict", "--output", "<think>r</think>{\"decision\":\"approve\"}", "--workspace-id", "ws-cli16", "--db-path", db_file, "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["code"] == "structured_schema_rejected"

    assert cli_main(["structured", "runs", "--workspace-id", "ws-cli16", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 2

    assert cli_main(["heal", "diagnose", "--failure-hint", "Outbound external endpoint blocked by zero-egress airgap", "--workspace-id", "ws-cli16", "--db-path", db_file, "--json"]) == 0
    diag_out = json.loads(capsys.readouterr().out)
    assert diag_out["failure_class"] == "airgap_egress_blocked"

    assert cli_main(["heal", "apply", "--diagnosis-id", diag_out["diagnosis_id"], "--workspace-id", "ws-cli16", "--db-path", db_file, "--json"]) == 0
    apply_out = json.loads(capsys.readouterr().out)
    assert apply_out["verified_healed"] is True and apply_out["promoted_eval_case"] is not None

    assert cli_main(["heal", "list", "--workspace-id", "ws-cli16", "--db-path", db_file, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["count"] == 1
