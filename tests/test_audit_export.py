"""Tests for Keelway Audit Export Bundle and Verification (FR-09).
Validates bundle creation, root hash signing, prompt redaction, and seal verification.
"""
from starlette.testclient import TestClient

from keelway.api.app import app
from keelway.audit.export import AuditExporter
from keelway.audit.recorder import AuditRecorder
from keelway.core.models import RunManifest, RunStatus


def test_audit_exporter_bundle_and_signature():
    exporter = AuditExporter()
    run_id = "run_export_test_01"

    manifest = RunManifest(
        run_id=run_id,
        org_id="org_sorvex",
        project_id="proj_governance",
        actor_id="eng_lead",
        source_commit_sha="4b8c03bea9d1c7b51257f6267a4831ee0da8aa20",
        policy_id="default_governed_v1",
        model_route_id="local-deepseek-coder",
        dataset_digest="sha256:abcd",
        toolchain_digest="sha256:toolchain",
        status=RunStatus.DEPLOYED,
        created_at="2026-11-03T18:00:00Z",
    )

    recorder = AuditRecorder(run_id=run_id)
    recorder.record_event("RUN_CREATED", {"actor": "eng_lead", "prompt": "Write secret code"})
    recorder.record_event("POLICY_DECISION", {"decision": "ALLOW"})
    recorder.record_event("APPROVAL_GRANTED", {"approver": "human_reviewer"})

    bundle = exporter.export(manifest, recorder.events, redact_prompts=True)
    assert bundle.run_id == run_id
    assert bundle.total_events == 3
    assert bundle.chain_verified is True
    assert bundle.chain_root_hash == recorder.events[-1].hash

    # Verify prompt redaction
    assert bundle.events[0]["payload"]["prompt"] == "[REDACTED_BY_KEELWAY_POLICY]"

    # Verify cryptographic signature verification
    assert exporter.verify_bundle_signature(bundle) is True

    # Tampered root hash fails verification
    bundle.chain_root_hash = "0" * 64
    assert exporter.verify_bundle_signature(bundle) is False


def test_audit_export_api_endpoint():
    client = TestClient(app)

    # 1. Start a run via API
    run_res = client.post("/v1/runs", json={"task_prompt": "Export test run", "repo_path": "."})
    assert run_res.status_code == 200
    run_id = run_res.json()["run_id"]

    # 2. Export audit bundle via API
    export_res = client.get(f"/v1/runs/{run_id}/export")
    assert export_res.status_code == 200
    bundle = export_res.json()
    assert bundle["run_id"] == run_id
    assert bundle["chain_verified"] is True
    assert len(bundle["events"]) >= 4
    assert len(bundle["verification_signature"]) == 64

    # Cleanup
    from keelway.api.routes import ACTIVE_RUNS
    if run_id in ACTIVE_RUNS:
        ACTIVE_RUNS[run_id].teardown()
