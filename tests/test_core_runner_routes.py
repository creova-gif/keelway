"""
Tests for Core API Outbound Runner Endpoints and CLI Runner Daemon Integration.
"""
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from core.main import app
from keelway.runner.daemon import CustomerRunnerDaemon, OutboundRunnerDaemon
from core.storage.workspace_fs import WorkspaceFilesystem
from core.api import routes


@pytest.fixture
def test_client(tmp_path, monkeypatch):
    prev_fs = routes._workspace_fs
    monkeypatch.chdir(tmp_path)
    routes.set_workspace_fs(WorkspaceFilesystem(root_dir=str(tmp_path)))
    try:
        with TestClient(app) as client:
            yield client
    finally:
        routes.set_workspace_fs(prev_fs)


def test_core_runner_endpoints_lifecycle(test_client):
    runner = CustomerRunnerDaemon(
        runner_id="vpc_node_01",
        org_id="org_enterprise",
        allowed_repos=["."],
    )

    # 1. Enqueue job via Core API
    res = test_client.post(
        "/v1/runner/jobs/enqueue",
        json={
            "org_id": "org_enterprise",
            "project_id": "proj_enterprise_01",
            "task_prompt": "Run security check via customer runner",
            "repo_path": ".",
        },
    )
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    assert res.json()["status"] == "ENQUEUED"

    # 2. Check pending queue
    pending_res = test_client.get("/v1/runner/jobs/pending")
    assert pending_res.status_code == 200
    assert pending_res.json()["count"] >= 1

    # 3. Poll job using runner token
    auth_token = runner.generate_auth_token()
    poll_res = test_client.post(
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

    # 4. Acknowledge job
    ack_res = test_client.post(
        "/v1/runner/jobs/ack",
        json={
            "runner_id": runner.runner_id,
            "org_id": runner.org_id,
            "run_id": "run_12345",
            "status": "COMPLETED",
        },
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "RECORDED"


def test_outbound_runner_daemon_start_single_iteration():
    daemon = OutboundRunnerDaemon(
        runner_id="runner_iter_test",
        org_id="org_test",
        control_plane_url="http://127.0.0.1:9999",  # unreachable host should gracefully handle
    )
    # Run 1 iteration; should not raise unhandled exception
    daemon.start(poll_interval=0.01, max_iterations=1)
    assert daemon.status == "IDLE"
