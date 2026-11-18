"""
Tests for KFlow interval scheduling and the token/RBAC administration API.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.kflow import kflow_engine, FlowNode
from core.orchestration.scheduler import FlowScheduler, flow_scheduler, MIN_INTERVAL_SECONDS


@pytest.fixture(autouse=True)
def reset_kflow_and_schedules():
    with kflow_engine._lock:
        kflow_engine._flows.clear()
        kflow_engine._leases.clear()
    flow_scheduler._schedules.clear()
    yield
    with kflow_engine._lock:
        kflow_engine._flows.clear()
        kflow_engine._leases.clear()
    flow_scheduler._schedules.clear()


def _register_dag(flow_id: str = "flow_sched") -> None:
    kflow_engine.create_dag(
        flow_id=flow_id,
        goal="scheduled flow",
        nodes=[FlowNode(node_id="n1", name="n1", assigned_role="core_engineer", tool="bash", inputs={})],
    )


# --- FlowScheduler unit -------------------------------------------------------

def test_scheduler_add_requires_registered_flow():
    sched = FlowScheduler(executor=lambda fid: None)
    with pytest.raises(KeyError):
        sched.add("no-such-flow", 60)


def test_scheduler_add_rejects_short_interval():
    _register_dag()
    sched = FlowScheduler(executor=lambda fid: None)
    with pytest.raises(ValueError):
        sched.add("flow_sched", MIN_INTERVAL_SECONDS - 1)


def test_scheduler_run_due_executes_and_reschedules():
    _register_dag()
    ran: list[str] = []
    sched = FlowScheduler(executor=lambda fid: ran.append(fid))
    s = sched.add("flow_sched", 60)
    first_due = s.next_run_epoch
    assert sched.run_due(now=s.created_at_epoch) == 0  # not due yet
    assert sched.run_due(now=first_due) == 1
    assert ran == ["flow_sched"]
    d = sched.list()[0]
    assert d["runs_completed"] == 1
    assert d["last_status"] == "completed"
    assert d["last_run_epoch"] == first_due
    assert d["next_run_epoch"] == first_due + 60


def test_scheduler_failure_is_captured_not_raised():
    _register_dag()
    def boom(fid):
        raise RuntimeError("flow exploded")
    sched = FlowScheduler(executor=boom)
    s = sched.add("flow_sched", 60)
    assert sched.run_due(now=s.next_run_epoch) == 1
    d = sched.list()[0]
    assert d["last_status"] == "failed"
    assert "flow exploded" in d["last_error"]


def test_scheduler_remove():
    _register_dag()
    sched = FlowScheduler(executor=lambda fid: None)
    s = sched.add("flow_sched", 60)
    assert sched.remove(s.schedule_id) is True
    assert sched.remove(s.schedule_id) is False
    assert sched.list() == []


# --- Schedule API -------------------------------------------------------------

def test_schedule_crud_via_api():
    _register_dag()
    client = TestClient(app)
    res = client.post("/v1/schedules", json={"flow_id": "flow_sched", "interval_seconds": 300})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["flow_id"] == "flow_sched"
    sid = body["schedule_id"]

    res = client.get("/v1/schedules")
    assert res.status_code == 200
    data = res.json()
    assert data["persistent"] is False
    assert any(s["schedule_id"] == sid for s in data["schedules"])

    res = client.delete(f"/v1/schedules/{sid}")
    assert res.status_code == 200
    res = client.delete(f"/v1/schedules/{sid}")
    assert res.status_code == 404


def test_schedule_create_unknown_flow_404():
    client = TestClient(app)
    res = client.post("/v1/schedules", json={"flow_id": "ghost", "interval_seconds": 300})
    assert res.status_code == 404


def test_schedule_create_short_interval_400():
    _register_dag()
    client = TestClient(app)
    res = client.post("/v1/schedules", json={"flow_id": "flow_sched", "interval_seconds": 10})
    assert res.status_code == 422  # pydantic Field(ge=60) rejects before the handler


# --- Token & RBAC admin API ---------------------------------------------------

def test_rbac_matrix_lists_roles_and_permissions():
    client = TestClient(app)
    res = client.get("/v1/rbac/matrix")
    assert res.status_code == 200
    data = res.json()
    assert set(data["roles"]) == {"owner", "admin", "engineer", "auditor", "phone"}
    assert "manage_keys" in data["roles"]["owner"]
    assert "manage_keys" not in data["roles"]["engineer"]


@pytest.mark.asyncio
async def test_token_crud_via_api(monkeypatch):
    # auth-off runs are treated as the local owner, which holds MANAGE_KEYS
    client = TestClient(app)
    res = client.post("/v1/tokens", json={"name": "ci-bot", "role": "engineer", "expires_in_days": 30})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["role"] == "engineer"
    assert body["token"]
    assert body["expires_at"]
    tid = body["id"]

    res = client.get("/v1/tokens")
    assert res.status_code == 200
    listed = res.json()["tokens"]
    match = [t for t in listed if t["id"] == tid]
    assert match and match[0]["name"] == "ci-bot" and match[0]["revoked"] is False
    assert "token_hash" not in match[0]

    res = client.post(f"/v1/tokens/{tid}/revoke")
    assert res.status_code == 200
    listed = client.get("/v1/tokens").json()["tokens"]
    assert [t for t in listed if t["id"] == tid][0]["revoked"] is True

    res = client.post("/v1/tokens/ghost-id/revoke")
    assert res.status_code == 404


def test_token_create_rejects_unknown_role():
    client = TestClient(app)
    res = client.post("/v1/tokens", json={"name": "x", "role": "superuser"})
    assert res.status_code == 400
