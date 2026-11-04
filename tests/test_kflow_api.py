"""
Tests for KFlow Durable Task DAG Orchestration REST API endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.kflow import kflow_engine, FlowNode, FlowStatus


@pytest.fixture(autouse=True)
def reset_kflow():
    with kflow_engine._lock:
        kflow_engine._flows.clear()
        kflow_engine._leases.clear()
    yield
    with kflow_engine._lock:
        kflow_engine._flows.clear()
        kflow_engine._leases.clear()


def test_list_kflow_dags_empty():
    client = TestClient(app)
    res = client.get("/v1/kflow/dags", headers={"Authorization": "Bearer dev_token"})
    assert res.status_code == 200
    data = res.json()
    assert "dags" in data
    assert isinstance(data["dags"], list)
    assert len(data["dags"]) == 0


def test_create_and_get_kflow_dag():
    client = TestClient(app)
    payload = {
        "flow_id": "flow_ci_pipeline",
        "goal": "Verify CI pipeline end-to-end",
        "max_fanout": 2,
        "nodes": [
            {
                "node_id": "step_build",
                "name": "Build Codebase",
                "assigned_role": "build_engineer",
                "tool": "bash",
                "dependencies": [],
            },
            {
                "node_id": "step_test",
                "name": "Run Pytest Suite",
                "assigned_role": "qa_engineer",
                "tool": "pytest",
                "dependencies": ["step_build"],
            },
            {
                "node_id": "step_seal",
                "name": "Cryptographically Seal Proof Packet",
                "assigned_role": "security_lead",
                "tool": "crypto",
                "dependencies": ["step_test"],
            },
        ],
    }

    create_res = client.post("/v1/kflow/dag", json=payload, headers={"Authorization": "Bearer dev_token"})
    assert create_res.status_code == 200
    created = create_res.json()
    assert created["flow_id"] == "flow_ci_pipeline"
    assert created["goal"] == "Verify CI pipeline end-to-end"
    assert len(created["nodes"]) == 3
    assert created["checkpoint_sha256"] != ""

    get_res = client.get("/v1/kflow/dag/flow_ci_pipeline", headers={"Authorization": "Bearer dev_token"})
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["flow_id"] == "flow_ci_pipeline"
    assert retrieved["status"] == "pending"


def test_run_kflow_dag_and_seal_proof():
    client = TestClient(app)
    payload = {
        "flow_id": "flow_execute_demo",
        "goal": "Execute topological DAG and verify proof packet",
        "nodes": [
            {
                "node_id": "node_1",
                "name": "Spec Ingestion",
                "assigned_role": "architect",
                "tool": "read_spec",
                "dependencies": [],
            },
            {
                "node_id": "node_2",
                "name": "Unit Testing",
                "assigned_role": "qa_engineer",
                "tool": "pytest",
                "dependencies": ["node_1"],
            },
        ],
    }
    client.post("/v1/kflow/dag", json=payload, headers={"Authorization": "Bearer dev_token"})

    run_res = client.post(
        "/v1/kflow/dag/flow_execute_demo/run",
        json={"git_head_sha": "a1b2c3d4e5f6"},
        headers={"Authorization": "Bearer dev_token"},
    )
    assert run_res.status_code == 200
    body = run_res.json()
    assert body["status"] == "completed"
    assert "proof_packet" in body
    proof = body["proof_packet"]
    assert proof["flow_id"] == "flow_execute_demo"
    assert proof["all_tests_passed"] is True
    assert proof["nodes_executed"] == 2
    assert proof["proof_sha256"] != ""
    assert proof["base_commit_sha"] == "a1b2c3d4e5f6"


def test_cancel_kflow_dag():
    client = TestClient(app)
    payload = {
        "flow_id": "flow_cancel_me",
        "goal": "Test cancellation",
        "nodes": [
            {"node_id": "n1", "name": "Task 1", "assigned_role": "worker", "tool": "bash", "dependencies": []}
        ],
    }
    client.post("/v1/kflow/dag", json=payload, headers={"Authorization": "Bearer dev_token"})

    cancel_res = client.post(
        "/v1/kflow/dag/flow_cancel_me/cancel",
        headers={"Authorization": "Bearer dev_token"},
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    get_res = client.get("/v1/kflow/dag/flow_cancel_me", headers={"Authorization": "Bearer dev_token"})
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "cancelled"
