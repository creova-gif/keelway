"""Tests for Keelway Customer Runner Daemon (Milestone 3).
Validates outbound runner authentication, cross-org job blocking, repo allowlists, and job execution.
"""
import pytest

from keelway.runner.daemon import (
    CrossOrgConsumptionError,
    CustomerRunnerDaemon,
    RunnerAuthenticationError,
)


def test_runner_token_generation_and_verification():
    secret = b"customer_secret_token_key_123"
    runner = CustomerRunnerDaemon(
        runner_id="runner_vpc_us_east_1",
        org_id="org_acme_corp",
        secret_key=secret,
    )

    token = runner.generate_auth_token()
    assert runner.verify_auth_token(token) is True

    # Tampered token rejected
    tampered_token = token[:-4] + "ffff"
    assert runner.verify_auth_token(tampered_token) is False

    # Forged org token rejected
    forged_token = token.replace("org_acme_corp", "org_evil_attacker")
    assert runner.verify_auth_token(forged_token) is False


def test_runner_blocks_cross_org_job_consumption():
    runner = CustomerRunnerDaemon(
        runner_id="runner_vpc_01",
        org_id="org_legit_corp",
        secret_key=b"secret",
    )

    job_spec = {
        "org_id": "org_different_tenant",
        "task_prompt": "Attempt cross-org execution",
    }

    with pytest.raises(CrossOrgConsumptionError) as exc_info:
        runner.validate_job_scope(job_spec)
    assert "refused cross-org job" in str(exc_info.value)


def test_runner_enforces_repo_allowlist():
    runner = CustomerRunnerDaemon(
        runner_id="runner_vpc_02",
        org_id="org_acme",
        secret_key=b"secret",
        allowed_repos=["/approved/repo/only"],
    )

    unapproved_job = {
        "org_id": "org_acme",
        "repo_path": "/malicious/or/unapproved/repo",
    }

    with pytest.raises(RunnerAuthenticationError) as exc_info:
        runner.validate_job_scope(unapproved_job)
    assert "not in runner allowlist" in str(exc_info.value)


def test_runner_executes_governed_job_locally():
    runner = CustomerRunnerDaemon(
        runner_id="runner_vpc_03",
        org_id="org_sorvex_test",
        secret_key=b"secret",
        allowed_repos=["."],
    )

    job_spec = {
        "org_id": "org_sorvex_test",
        "project_id": "proj_runner_test",
        "task_prompt": "Add healthcheck via customer runner",
        "repo_path": ".",
    }

    ok, status, summary = runner.execute_job(job_spec)
    assert ok is True
    assert status == "JOB_AWAITING_APPROVAL"
    assert summary["events_count"] >= 4
    assert len(summary["patch_hash"]) == 64
    assert runner.status == "IDLE"
    assert len(runner._local_spool) >= 4


def test_runner_api_poll_and_ack_lifecycle():
    from starlette.testclient import TestClient
    from keelway.api.app import app
    from keelway.api.routes import PENDING_RUNNER_JOBS

    client = TestClient(app)
    secret = b"runner_shared_secret_key"
    runner = CustomerRunnerDaemon(
        runner_id="runner_node_alpha",
        org_id="org_runner_corp",
        secret_key=secret,
        allowed_repos=["."],
    )

    # 1. Enqueue job
    job_payload = {
        "org_id": "org_runner_corp",
        "project_id": "proj_runner_api",
        "task_prompt": "Distributed runner job test",
        "repo_path": ".",
    }
    enqueue_res = client.post("/v1/runner/jobs/enqueue", json=job_payload)
    assert enqueue_res.status_code == 200
    job_id = enqueue_res.json()["job_id"]

    # 2. Poll for job with valid auth token
    auth_token = runner.generate_auth_token()
    poll_res = client.post(
        "/v1/runner/jobs/poll",
        json={
            "runner_id": runner.runner_id,
            "org_id": runner.org_id,
            "auth_token": auth_token,
        },
    )
    assert poll_res.status_code == 200
    poll_data = poll_res.json()
    assert poll_data["job_available"] is True
    assert poll_data["job"]["job_id"] == job_id

    # 3. Runner executes job locally
    ok, status, summary = runner.execute_job(poll_data["job"])
    assert ok is True

    # 4. Acknowledge completion to control plane
    ack_res = client.post(
        "/v1/runner/jobs/ack",
        json={
            "runner_id": runner.runner_id,
            "org_id": runner.org_id,
            "run_id": summary["run_id"],
            "status": summary["status"],
            "patch_hash": summary["patch_hash"],
            "approval_id": summary["approval_id"],
        },
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "RECORDED"

