"""
Phase 16B & Integration Verification Suite — Tri-Language SDK Parity (`Python`, `TypeScript`, `Go`)
for Typed Structured-Output & Content-Block Normalizer + Autonomous Self-Healing Failure Root-Causer,
Module-Size & Public-Hygiene Ratchets, and Website `292`-Route OpenAPI + `24`-Feature Facts Sync.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any, Dict, List
import uuid

import httpx
from httpx import ASGITransport
import pytest

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
WEBSITE_DIR = REPO_ROOT / "website"

PHASE16_PYTHON_METHODS = (
    "normalize_content_blocks",
    "enforce_structured_output",
    "list_structured_output_runs",
    "diagnose_failure_root_cause",
    "apply_self_healing_patch",
    "list_self_healing_diagnoses",
)

PHASE16_TS_METHODS = (
    "normalizeContentBlocks",
    "enforceStructuredOutput",
    "listStructuredOutputRuns",
    "diagnoseFailureRootCause",
    "applySelfHealingPatch",
    "listSelfHealingDiagnoses",
)

PHASE16_GO_METHODS = (
    "NormalizeContentBlocks",
    "EnforceStructuredOutput",
    "ListStructuredOutputRuns",
    "DiagnoseFailureRootCause",
    "ApplySelfHealingPatch",
    "ListSelfHealingDiagnoses",
)

FORBIDDEN_PRIVATE_TOKENS = (
    "creova-gif",
    "creovas-projects",
    "keelway.git",
    "KEEL-",
    "verify_engineering_gates.sh",
    "Antigravity",
    "gstack",
)

DECISION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["action", "confidence"],
    "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": ["approve", "escalate", "reject"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
}


def _make_sync_mock_transport() -> httpx.MockTransport:
    runs_store: List[Dict[str, Any]] = []
    diag_store: Dict[str, Dict[str, Any]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode("utf-8") if request.content else ""
        body = json.loads(raw) if raw else {}
        path, params = request.url.path, dict(request.url.params)

        if path == "/v1/platform/healing/content-blocks/normalize" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "workspace_id": body.get("workspace_id", "default"),
                    "provider_format": body.get("provider_format", "deepseek_opencore"),
                    "model_id": body.get("model_id", "keelway-core:7b"),
                    "block_count": 2,
                    "content_blocks": [
                        {"index": 0, "kind": "reasoning", "content": "Checking invoice policy"},
                        {"index": 1, "kind": "structured_json", "content": "{\"action\":\"approve\"}", "structured_data": {"action": "approve"}},
                    ],
                    "dlp_redactions": 1,
                    "envelope_sha256": "sha256:" + ("a" * 64),
                },
            )

        if path == "/v1/platform/healing/structured/enforce" and request.method == "POST":
            if body.get("strict_mode") and isinstance(body.get("raw_output"), str):
                return httpx.Response(422, json={"detail": "Strict schema rejected", "code": "structured_schema_rejected"})
            rec = {
                "run_id": f"srun-{len(runs_store) + 1}",
                "workspace_id": body.get("workspace_id", "default"),
                "schema_name": body.get("schema_name", "AgentDecisionContract"),
                "provider_format": body.get("provider_format", "deepseek_opencore"),
                "model_id": body.get("model_id", "keelway-core:7b"),
                "status": "REPAIRED_VALID",
                "repair_applied": True,
                "repair_actions": ["strip_think_tags", "coerce_scalar_types"],
                "validated_data": {"action": "approve", "confidence": 0.92},
                "validation_errors": [],
                "dlp_redactions": 0,
                "run_sha256": "sha256:" + ("b" * 64),
                "created_at": "2026-11-15T00:00:00+00:00",
            }
            runs_store.append(rec)
            return httpx.Response(200, json=rec)

        if path == "/v1/platform/healing/structured/runs" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            matched = [r for r in runs_store if r["workspace_id"] == ws]
            return httpx.Response(200, json={"workspace_id": ws, "count": len(matched), "runs": matched})

        if path == "/v1/platform/healing/root-cause/diagnose" and request.method == "POST":
            did = f"diag-{len(diag_store) + 1}"
            rec = {
                "diagnosis_id": did,
                "workspace_id": body.get("workspace_id", "default"),
                "trace_id": body.get("trace_id") or "trace-sample-1",
                "workflow_name": body.get("workflow_name", "invoice-triage-agent"),
                "failure_class": "schema_mismatch",
                "status": "DIAGNOSED",
                "confidence": 0.94,
                "failed_node": "extract_decision",
                "diagnostic_model": "keelway-core:7b",
                "summary": "Detected schema mismatch on required field confidence.",
                "root_cause_evidence": ["Missing required field confidence"],
                "proposed_patch": {
                    "target_surface": "json_schema",
                    "recommended_model": "keelway-core:7b",
                    "unified_diff": "--- a/schema.json\n+++ b/schema.json",
                    "patched_prompt": "Return strict JSON matching AgentDecisionContract.",
                },
                "verification_replay_trace_id": None,
                "promoted_eval_case_id": None,
                "dlp_redactions": 0,
                "diagnosis_sha256": "sha256:" + ("c" * 64),
                "created_at": "2026-11-15T00:00:00+00:00",
            }
            diag_store[did] = rec
            return httpx.Response(200, json=rec)

        if path.startswith("/v1/platform/healing/root-cause/") and path.endswith("/apply") and request.method == "POST":
            did = path.split("/")[-2]
            if did not in diag_store:
                return httpx.Response(404, json={"detail": "Diagnosis not found"})
            rec = dict(diag_store[did])
            rec["status"] = "VERIFIED_HEALED"
            rec["verification_replay_trace_id"] = "trace-replay-1"
            rec["promoted_eval_case_id"] = "eval-case-1"
            diag_store[did] = rec
            return httpx.Response(
                200,
                json={
                    "diagnosis": rec,
                    "verified_healed": True,
                    "cached_steps_reused": 2,
                    "replay_cost_usd": 0.0,
                    "promoted_eval_case": {"case_id": "eval-case-1", "title": "Regression Eval", "case_sha256": "sha256:" + ("d" * 64)},
                },
            )

        if path == "/v1/platform/healing/root-cause/diagnoses" and request.method == "GET":
            ws = params.get("workspace_id", "default")
            matched = [d for d in diag_store.values() if d["workspace_id"] == ws]
            return httpx.Response(200, json={"workspace_id": ws, "count": len(matched), "diagnoses": matched})

        return httpx.Response(404, json={"detail": f"Unhandled mock route {request.method} {path}"})

    return httpx.MockTransport(handler)


def test_python_sdk_phase16_sync_async_signature_and_mock_parity() -> None:
    for method_name in PHASE16_PYTHON_METHODS:
        sync_fn = getattr(SyncPlatformClient, method_name, None)
        async_fn = getattr(AsyncPlatformClient, method_name, None)
        assert callable(sync_fn), f"Missing SyncPlatformClient.{method_name}"
        assert callable(async_fn), f"Missing AsyncPlatformClient.{method_name}"
        assert inspect.iscoroutinefunction(async_fn)
        assert list(inspect.signature(sync_fn).parameters.keys()) == list(inspect.signature(async_fn).parameters.keys())

    with KeelwayClient(base_url="http://127.0.0.1:7420", token="test-token", transport=_make_sync_mock_transport()) as client:
        norm = client.platform.normalize_content_blocks(
            "<think>check</think>{\"action\":\"approve\"}",
            provider_format="deepseek_opencore",
            workspace_id="ws-p16",
        )
        assert norm["block_count"] == 2 and norm["envelope_sha256"].startswith("sha256:")

        enforced = client.platform.enforce_structured_output(
            DECISION_SCHEMA,
            "<think>check</think>```json\n{\"action\":\"approve\",\"confidence\":\"0.92\",}\n```",
            workspace_id="ws-p16",
        )
        assert enforced["status"] == "REPAIRED_VALID" and enforced["repair_applied"] is True

        runs = client.platform.list_structured_output_runs(workspace_id="ws-p16")
        assert runs["count"] == 1

        diag = client.platform.diagnose_failure_root_cause(
            workspace_id="ws-p16",
            workflow_name="invoice-triage-agent",
            failed_step={"node_name": "extract_decision", "error_message": "JSON schema validation failed: missing confidence"},
        )
        assert diag["failure_class"] == "schema_mismatch" and diag["status"] == "DIAGNOSED"

        applied = client.platform.apply_self_healing_patch(diag["diagnosis_id"], workspace_id="ws-p16")
        assert applied["verified_healed"] is True and applied["replay_cost_usd"] == 0.0

        diags = client.platform.list_self_healing_diagnoses(workspace_id="ws-p16")
        assert diags["count"] == 1

        with pytest.raises(KeelwayError):
            client.platform.enforce_structured_output(DECISION_SCHEMA, "not json", workspace_id="ws-p16", strict_mode=True)


@pytest.mark.asyncio
async def test_python_async_sdk_live_asgi_structured_and_self_healing() -> None:
    ws_id = f"ws-p16-asgi-{uuid.uuid4().hex[:8]}"
    token = launch_token()

    async with AsyncKeelwayClient(base_url="http://127.0.0.1:7420", token=token, transport=ASGITransport(app=app)) as client:
        norm = await client.platform.normalize_content_blocks(
            "<think>Inspecting key sk-live-1234567890abcdef</think>\n```json\n{\"action\":\"approve\",\"confidence\":0.95}\n```",
            provider_format="deepseek_opencore",
            workspace_id=ws_id,
        )
        assert norm["dlp_redactions"] >= 1
        assert any(b["kind"] == "reasoning" for b in norm["content_blocks"])
        assert any(b["kind"] == "structured_json" for b in norm["content_blocks"])

        repaired = await client.platform.enforce_structured_output(
            DECISION_SCHEMA,
            "<think>repairing</think>\n```json\n{\"action\": \"approve\", \"confidence\": \"0.91\",}\n```",
            workspace_id=ws_id,
            strict_mode=False,
        )
        assert repaired["status"] == "REPAIRED_VALID"
        assert repaired["validated_data"] == {"action": "approve", "confidence": 0.91}

        runs = await client.platform.list_structured_output_runs(workspace_id=ws_id)
        assert runs["count"] >= 1

        diag = await client.platform.diagnose_failure_root_cause(
            workspace_id=ws_id,
            workflow_name="invoice-triage-agent",
            failed_step={
                "node_name": "extract_decision",
                "model_id": "keelway-core:7b",
                "output_text": "{\"action\": \"unknown_enum\"}",
                "error_message": "JSON Schema validation error: enum mismatch on action",
                "expected_schema": DECISION_SCHEMA,
            },
        )
        assert diag["failure_class"] == "schema_mismatch"
        assert diag["status"] == "DIAGNOSED"

        healed = await client.platform.apply_self_healing_patch(
            diag["diagnosis_id"],
            workspace_id=ws_id,
            promote_to_eval=True,
            eval_title="Invoice Triage Schema Regression",
        )
        assert healed["verified_healed"] is True
        assert healed["diagnosis"]["status"] == "VERIFIED_HEALED"
        assert healed["promoted_eval_case"] is not None

        listed = await client.platform.list_self_healing_diagnoses(workspace_id=ws_id)
        assert listed["count"] >= 1

    async with AsyncKeelwayClient(base_url="http://127.0.0.1:7420", token=token, transport=ASGITransport(app=app)) as auditor_client:
        http_attr = getattr(auditor_client, "_http", None) or getattr(auditor_client, "_client")
        http_attr.headers["X-Keelway-Role"] = "auditor"
        http_attr.headers["X-Keelway-Actor"] = "auditor-actor"
        read_ok = await auditor_client.platform.normalize_content_blocks(
            "{\"action\":\"approve\"}",
            provider_format="deepseek_opencore",
            workspace_id=ws_id,
        )
        assert read_ok["block_count"] >= 1
        with pytest.raises(PermissionDeniedError):
            await auditor_client.platform.enforce_structured_output(DECISION_SCHEMA, "{\"action\":\"approve\",\"confidence\":0.9}", workspace_id=ws_id)
        with pytest.raises(PermissionDeniedError):
            await auditor_client.platform.diagnose_failure_root_cause(workspace_id=ws_id)


def test_tri_sdk_module_caps_and_website_292_route_24_feature_parity() -> None:
    new_phase16_files = (
        REPO_ROOT / "core" / "platform" / "structured_self_healing.py",
        REPO_ROOT / "core" / "api" / "platform_healing_routes.py",
        REPO_ROOT / "core" / "cli_healing.py",
        REPO_ROOT / "core" / "sdk" / "platform_healing_client.py",
        REPO_ROOT / "sdk" / "typescript" / "src" / "platformHealing.ts",
        REPO_ROOT / "sdk" / "go" / "platform_phase16.go",
        REPO_ROOT / "dev-app" / "src" / "lib" / "platformHealingApi.ts",
        REPO_ROOT / "dev-app" / "src" / "components" / "platform" / "StructuredOutputAndSelfHealingPanel.tsx",
    )
    for fpath in new_phase16_files:
        assert fpath.exists(), f"Expected Phase 16 module {fpath}"
        lines = fpath.read_text(encoding="utf-8").splitlines()
        assert len(lines) < 480, f"{fpath} exceeds 480-line cap ({len(lines)} lines)"

    # KEEL-WEB-038: DocsHub.tsx was retired with the v3 route prune; the
    # no-private-token scan now covers the live v3 docs + marketing surface.
    v3_surface = "\n".join(
        (WEBSITE_DIR / p).read_text(encoding="utf-8")
        for p in (
            "src/app/docs/page.tsx",
            "src/app/page.tsx",
            "src/app/product/page.tsx",
            "src/app/pricing/page.tsx",
            "src/data/releases.ts",
        )
    )
    for tok in FORBIDDEN_PRIVATE_TOKENS:
        assert tok not in v3_surface, f"Private token '{tok}' leaked in v3 public surface"

    ts_src = (REPO_ROOT / "sdk" / "typescript" / "src" / "platformHealing.ts").read_text(encoding="utf-8")
    go_src = (REPO_ROOT / "sdk" / "go" / "platform_phase16.go").read_text(encoding="utf-8")
    for ts_m in PHASE16_TS_METHODS:
        assert ts_m in ts_src, f"Missing TypeScript SDK method {ts_m}"
    for go_m in PHASE16_GO_METHODS:
        assert f"func (p *PlatformService) {go_m}(" in go_src, f"Missing Go SDK method {go_m}"

    openapi_raw = (WEBSITE_DIR / "openapi.json").read_text(encoding="utf-8")
    pub_openapi_raw = (WEBSITE_DIR / "public" / "openapi.json").read_text(encoding="utf-8")
    assert openapi_raw == pub_openapi_raw
    openapi_doc = json.loads(openapi_raw)
    assert len(openapi_doc["paths"]) >= 292
    assert len(app.openapi()["paths"]) >= 292
    for route in (
        "/v1/platform/healing/content-blocks/normalize",
        "/v1/platform/healing/structured/enforce",
        "/v1/platform/healing/structured/runs",
        "/v1/platform/healing/root-cause/diagnose",
        "/v1/platform/healing/root-cause/{diagnosis_id}/apply",
        "/v1/platform/healing/root-cause/diagnoses",
    ):
        assert route in openapi_doc["paths"], f"Missing OpenAPI route {route}"

    facts_raw = (WEBSITE_DIR / "product-facts.json").read_text(encoding="utf-8")
    pub_facts_raw = (WEBSITE_DIR / "public" / "product-facts.json").read_text(encoding="utf-8")
    assert facts_raw == pub_facts_raw
    for tok in FORBIDDEN_PRIVATE_TOKENS:
        assert tok not in facts_raw, f"Private token '{tok}' leaked in product-facts.json"
    facts = json.loads(facts_raw)
    assert len(facts["features"]) >= 24
    feat = facts["features"]["structured_output_normalizer_and_self_healing_root_causer"]
    assert feat["status"] == "AVAILABLE"
    assert "core/platform/structured_self_healing.py" in feat["code_path"]
