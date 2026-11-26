"""
Tests for Keelway Sovereign Air-Gap & Zero-Egress Suite (WP15 / Section 15).
Verifies 5-point pre-flight compliance audit, cryptographic attestation generation,
self-contained bundle packaging, SHA256SUMS root digests, and tamper detection.
"""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from core.security.airgap import AirGapEnforcer, AirGapViolationError
from core.security.airgap_auditor import AirGapAuditor
from core.security.bundle_exporter import AirGapBundleExporter
from core.api.schemas import Provider
from core.main import app


def test_airgap_enforcer_provider_validation():
    enforcer = AirGapEnforcer(enabled=True)
    # Local is strictly permitted
    enforcer.validate_provider(Provider.LOCAL)

    # Cloud providers must be blocked
    with pytest.raises(AirGapViolationError) as exc_info:
        enforcer.validate_provider(Provider.OPENAI)
    assert "AIR-GAP VIOLATION" in str(exc_info.value)

    with pytest.raises(AirGapViolationError):
        enforcer.validate_provider(Provider.ANTHROPIC)

    # Attestation generation
    att = enforcer.generate_attestation(
        task_id="task_test_01",
        model_name="llama3.2:3b",
        tokens_processed=450,
    )
    assert att["air_gapped"] is True
    assert att["egress_allowed"] is False
    assert len(att["attestation_sha256"]) == 64


def test_airgap_auditor_environment(monkeypatch):
    # Isolate from host credentials — the auditor must flag real env keys,
    # so this test clears them to assert the clean-environment baseline.
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "AZURE_OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    report = AirGapAuditor.audit_environment()
    assert report.overall_compliant is True
    assert len(report.checks) == 5
    check_ids = {c.check_id for c in report.checks}
    assert "AIRGAP-01-CREDS" in check_ids
    assert "AIRGAP-02-ENFORCER" in check_ids
    assert "AIRGAP-03-TELEMETRY" in check_ids
    assert "AIRGAP-04-STORAGE" in check_ids
    assert "AIRGAP-05-ENDPOINT" in check_ids
    assert len(report.attestation_sha256) == 64
    assert report.attestation_sha256 == report.calculate_attestation()


def test_airgap_auditor_detects_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-test123456789")
    report = AirGapAuditor.audit_environment()
    assert report.overall_compliant is False
    cred_check = next(c for c in report.checks if c.check_id == "AIRGAP-01-CREDS")
    assert cred_check.passed is False
    assert "OPENAI_API_KEY" in cred_check.details


def test_airgap_bundle_export_and_verify(tmp_path):
    output_dir = tmp_path / "sovereign_out"
    receipt = AirGapBundleExporter.export_bundle(
        output_dir=output_dir,
        bundle_name="test-airgap-pkg",
        include_tar=True,
    )
    assert receipt.bundle_id == "test-airgap-pkg"
    assert receipt.total_files > 10
    assert Path(receipt.bundle_path).exists()
    assert len(receipt.root_digest_sha256) == 64

    # Verify the tar.gz archive
    verify_res = AirGapBundleExporter.verify_bundle(Path(receipt.bundle_path))
    assert verify_res.is_valid is True
    assert verify_res.matched_files == receipt.total_files
    assert len(verify_res.mismatched_files) == 0
    assert len(verify_res.missing_files) == 0
    assert verify_res.root_digest_sha256 == receipt.root_digest_sha256


def test_airgap_bundle_tamper_detection(tmp_path):
    output_dir = tmp_path / "sovereign_tamper"
    receipt = AirGapBundleExporter.export_bundle(
        output_dir=output_dir,
        bundle_name="tamper-test",
        include_tar=False,  # Directory verification
    )
    bundle_dir = Path(receipt.bundle_path)

    # Initial verification passes
    v1 = AirGapBundleExporter.verify_bundle(bundle_dir)
    assert v1.is_valid is True

    # Tamper with a file inside the bundle
    target_cli = bundle_dir / "cli.py"
    if target_cli.exists():
        with open(target_cli, "a") as f:
            f.write("\n# TAMPERED LINE\n")

    # Second verification must fail
    v2 = AirGapBundleExporter.verify_bundle(bundle_dir)
    assert v2.is_valid is False
    assert "cli.py" in v2.mismatched_files


def test_airgap_api_routes(tmp_path):
    client = TestClient(app)

    # 1. Audit endpoint
    res_audit = client.get("/v1/airgap/audit")
    assert res_audit.status_code == 200
    data_audit = res_audit.json()
    assert "overall_compliant" in data_audit
    assert "attestation_sha256" in data_audit
    assert len(data_audit["checks"]) >= 5

    # 2. Export bundle endpoint
    res_exp = client.post(
        "/v1/airgap/bundle/export",
        json={"bundle_name": "api-bundle-test", "output_dir": str(tmp_path / "api_out"), "include_tar": True},
    )
    assert res_exp.status_code == 200
    data_exp = res_exp.json()
    assert data_exp["bundle_id"] == "api-bundle-test"
    assert Path(data_exp["bundle_path"]).exists()

    # 3. Verify bundle endpoint
    res_ver = client.post(
        "/v1/airgap/bundle/verify",
        json={"bundle_path": data_exp["bundle_path"]},
    )
    assert res_ver.status_code == 200
    data_ver = res_ver.json()
    assert data_ver["is_valid"] is True
    assert data_ver["matched_files"] == data_exp["total_files"]
