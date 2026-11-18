"""
Tests for Keelway Hybrid AI Developer CLI (`opencore`, `route`, `swarm`, `governance`).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


KEELWAY_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*cli_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "cli.py", *cli_args],
        cwd=str(KEELWAY_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_cli_opencore_status_and_weights_json():
    res_status = _run_cli("opencore", "status", "--json")
    assert res_status.returncode == 0, res_status.stderr
    status_data = json.loads(res_status.stdout)
    assert "hardware" in status_data
    assert len(status_data["models"]) >= 4
    model_ids = {m["id"] for m in status_data["models"]}
    assert "keelway-core:7b" in model_ids

    res_weights = _run_cli("opencore", "weights", "--model", "keelway-core:7b", "--json")
    assert res_weights.returncode == 0, res_weights.stderr
    weights_data = json.loads(res_weights.stdout)
    assert len(weights_data["manifests"]) >= 1
    assert weights_data["manifests"][0]["model_id"] == "keelway-core:7b"


def test_cli_opencore_modelfile_and_adapt_output(tmp_path: Path):
    mf_out = tmp_path / "Modelfile"
    res_mf = _run_cli(
        "opencore",
        "modelfile",
        "--model",
        "keelway-coder:7b",
        "--quantization",
        "q4_k_m",
        "--out",
        str(mf_out),
        "--json",
    )
    assert res_mf.returncode == 0, res_mf.stderr
    mf_data = json.loads(res_mf.stdout)
    assert "FROM" in mf_data["modelfile"]
    assert mf_out.exists() and "FROM" in mf_out.read_text(encoding="utf-8")

    recipe_out = tmp_path / "train_qlora.py"
    res_adapt = _run_cli(
        "opencore",
        "adapt",
        "--model",
        "keelway-core:7b",
        "--languages",
        "swahili",
        "yoruba",
        "hausa",
        "--out",
        str(recipe_out),
        "--json",
    )
    assert res_adapt.returncode == 0, res_adapt.stderr
    adapt_data = json.loads(res_adapt.stdout)
    assert adapt_data["peft_config"]["r"] == 16
    assert adapt_data["sample_count"] >= 6
    assert recipe_out.exists() and "FastLanguageModel" in recipe_out.read_text(encoding="utf-8")


def test_cli_route_explain_privacy_and_provenance():
    # 1. Default local-first route
    res_std = _run_cli("route", "explain", "--prompt", "Summarize architecture", "--json")
    assert res_std.returncode == 0, res_std.stderr
    std_data = json.loads(res_std.stdout)
    assert std_data["selected_provider"] == "local"
    assert std_data["provenance"]["data_processing_boundary"] == "zero_external_egress"

    # 2. Private request explicitly requesting a closed model must fail-closed (blocked)
    res_priv = _run_cli(
        "route",
        "explain",
        "--prompt",
        "Confidential payroll record",
        "--model",
        "gemini-3.5-flash-lite",
        "--privacy",
        "private",
        "--json",
    )
    assert res_priv.returncode == 0, res_priv.stderr
    priv_data = json.loads(res_priv.stdout)
    assert priv_data["selected_provider"] is None
    assert priv_data["candidate_chain"] == []
    assert priv_data["provenance"]["data_processing_boundary"] == "rejected_by_policy"


def test_cli_swarm_offline_benchmark_json():
    res = _run_cli("swarm", "run", "--rounds", "1", "--json")
    assert res.returncode == 0, res.stderr
    data = json.loads(res.stdout)
    assert data["total_calls"] >= 5
    assert data["open_weight_calls"] >= 2
    assert data["security_checks"]["prompt_injection_blocked"] is True
    assert data["security_checks"]["episode_secret_redacted"] is True
    assert data["security_checks"]["airgap_cloud_egress_blocked"] is True


def test_cli_governance_tenants_issue_key_and_audit():
    res_tenants = _run_cli("governance", "tenants", "--json")
    assert res_tenants.returncode == 0, res_tenants.stderr
    t_data = json.loads(res_tenants.stdout)
    assert any(t["tenant_id"] == "default" for t in t_data["tenants"])

    res_key = _run_cli("governance", "issue-key", "--tenant", "default", "--name", "ci-runner", "--json")
    assert res_key.returncode == 0, res_key.stderr
    k_data = json.loads(res_key.stdout)
    assert k_data["tenant_id"] == "default"
    assert k_data["key_prefix"].startswith("kw_live_")

    res_audit = _run_cli("governance", "audit", "--limit", "10", "--json")
    assert res_audit.returncode == 0, res_audit.stderr
    a_data = json.loads(res_audit.stdout)
    assert a_data["chain_valid"] is True
    assert a_data["broken_at_seq"] is None

