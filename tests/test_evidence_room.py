"""
Unit and Integration Tests for Keelway Investor & Audit Evidence Room (WP21).
"""
import copy
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from core.main import app
from core.eval.evidence_room import (
    EvidenceMetric,
    EvidenceRoomPackage,
    EvidenceRoomPipeline,
)


def test_evidence_room_package_sealing():
    """Verify package hashing and tamper detection."""
    pkg = EvidenceRoomPackage(
        package_id="test_pkg_001",
        commit_sha="abcdef1234567890",
        git_branch="main",
        timestamp_utc="2026-11-04T12:00:00Z",
        summary={"total_verified_metrics": 1, "all_verified": True},
        metrics=[{
            "name": "Test Metric",
            "category": "tests",
            "claim": "100% test pass",
            "observed_value": {"passed": 10},
            "is_verified": True,
            "evidence_path_or_receipt": "tests/",
            "reproduce_command": "pytest",
        }],
        reproducibility_guide={"full_tests": "pytest"},
    )
    pkg.seal()
    assert pkg.package_sha256 != ""
    assert len(pkg.package_sha256) == 64

    # Verify unmutated
    valid, status_str, details = EvidenceRoomPipeline.verify_package(pkg.to_dict())
    assert valid is True
    assert status_str == "VERIFIED"
    assert details["package_id"] == "test_pkg_001"

    # Verify tampering detection
    tampered_data = copy.deepcopy(pkg.to_dict())
    tampered_data["summary"]["all_verified"] = False
    valid_t, status_t, details_t = EvidenceRoomPipeline.verify_package(tampered_data)
    assert valid_t is False
    assert status_t == "EVIDENCE_PACKAGE_TAMPERED"


def test_assemble_evidence_package():
    """Not-run checks stay unverified and do not carry a pass count."""
    pkg = EvidenceRoomPipeline.assemble_package()
    assert pkg.package_id.startswith("evd_")
    assert pkg.commit_sha != ""
    assert pkg.package_sha256 != ""
    assert len(pkg.metrics) == 10
    verified = [m for m in pkg.metrics if m["is_verified"] is True]
    not_run = [m for m in pkg.metrics if m["observed_value"].get("status") == "not_run"]
    assert pkg.summary["total_metrics"] == 10
    assert pkg.summary["total_verified_metrics"] == len(verified)
    assert pkg.summary["not_run_metrics"] == len(not_run)
    assert pkg.summary["all_verified"] is False
    assert pkg.summary["simulated_metrics"] is False
    assert not_run, "checks this call does not execute must stay explicitly not-run"
    for metric in not_run:
        assert metric["is_verified"] is False
        assert metric["observed_value"]["passed"] is None
        assert metric["observed_value"]["failed"] is None
        assert metric["observed_value"]["count"] is None
        assert metric["claim"].startswith("Not run.")

    serialized = json.dumps(pkg.to_dict())
    for banned in ("745", "40/40", "10/10 stages", "7/7", "worm_verified", "100% Pass@1", "HEALTHY"):
        assert banned not in serialized

    pytest_metric = next(m for m in pkg.metrics if m["name"] == "Automated Pytest Suite")
    assert pytest_metric["observed_value"]["status"] == "not_run"
    assert pytest_metric["is_verified"] is False

    benchmark = next(m for m in pkg.metrics if m["category"] == "benchmark")
    bench_status = benchmark["observed_value"]["status"]
    assert bench_status in {"executed", "error"}
    if bench_status == "executed":
        passed_tasks = benchmark["observed_value"]["passed_tasks"]
        total_tasks = benchmark["observed_value"]["total_tasks"]
        assert isinstance(passed_tasks, int) and isinstance(total_tasks, int)
        assert benchmark["is_verified"] is (passed_tasks == total_tasks)
        assert benchmark["claim"].startswith("In-process golden panel finished")
    else:
        assert benchmark["is_verified"] is False
        assert benchmark["observed_value"]["passed"] is None

    categories = {m["category"] for m in pkg.metrics}
    assert "tests" in categories
    assert "benchmark" in categories
    assert "architecture" in categories
    assert "compliance" in categories
    assert "security" in categories


def test_evidence_api_endpoints():
    """Verify FastAPI evidence and governance endpoints."""
    client = TestClient(app)

    # 1. Summary
    resp_sum = client.get("/v1/evidence/summary")
    assert resp_sum.status_code == 200
    sum_data = resp_sum.json()
    assert "package_id" in sum_data
    assert "metrics" in sum_data
    assert len(sum_data["metrics"]) == 10

    # 2. Generate
    resp_gen = client.post("/v1/evidence/generate")
    assert resp_gen.status_code == 200
    gen_data = resp_gen.json()
    assert gen_data["status"] == "SEALED"
    assert "package_sha256" in gen_data

    # 3. Verify valid
    resp_ver = client.post("/v1/evidence/verify", json={"package": gen_data["evidence_package"]})
    assert resp_ver.status_code == 200
    ver_data = resp_ver.json()
    assert ver_data["is_valid"] is True
    assert ver_data["status"] == "VERIFIED"

    # 4. Verify tampered
    tampered = copy.deepcopy(gen_data["evidence_package"])
    tampered["metrics"][0]["claim"] = "Tampered Claim"
    resp_bad = client.post("/v1/evidence/verify", json={"package": tampered})
    assert resp_bad.status_code == 200
    bad_data = resp_bad.json()
    assert bad_data["is_valid"] is False
    assert bad_data["status"] == "EVIDENCE_PACKAGE_TAMPERED"

    # 5. Entitlements status
    resp_ent = client.get("/v1/entitlements/status")
    assert resp_ent.status_code == 200
    ent_data = resp_ent.json()
    assert ent_data["tier"] == "community"
    assert ent_data["is_valid"] is False
    assert ent_data["status"] == "SOURCE_DEFAULT_REFUSED"
    assert not any(ent_data["features"].values())

    # 6. CycloneDX SBOM
    resp_sbom = client.get("/v1/sbom")
    assert resp_sbom.status_code == 200
    sbom_data = resp_sbom.json()
    assert sbom_data["bom_format"] == "CycloneDX"
    assert "provenance_signature" in sbom_data
