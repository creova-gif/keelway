import pytest
from fastapi.testclient import TestClient

from core.api import routes
from core.main import app
from core.orchestration.flight_recorder import FlightRecorder


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "FLIGHT_RECORDINGS_DIR", tmp_path)
    rec = FlightRecorder(task_id="task_demo", recordings_dir=tmp_path)
    rec.record_event("prompt", {"text": "hello"})
    rec.record_event("model_response", {"text": "hi"})
    rec.record_event("tool_call", {"cmd": "pytest"})
    rec.save_tape()
    with TestClient(app) as c:
        yield c


def test_list_flight_tapes(client):
    resp = client.get("/v1/flight/tapes")
    assert resp.status_code == 200
    assert [t["task_id"] for t in resp.json()["tapes"]] == ["task_demo"]


def test_get_flight_tape(client):
    resp = client.get("/v1/flight/tape/task_demo")
    assert resp.status_code == 200
    assert resp.json()["event_count"] == 3


def test_get_missing_flight_tape(client):
    assert client.get("/v1/flight/tape/nope").status_code == 404


def test_fork_flight_tape(client, tmp_path):
    resp = client.post("/v1/flight/fork", json={"task_id": "task_demo", "at_index": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert body["forked_task_id"].startswith("task_demo_fork_")
    forked = client.get(f"/v1/flight/tape/{body['forked_task_id']}").json()
    assert forked["event_count"] == 2


@pytest.mark.parametrize("bad_id", ["../etc", "a/b", ".."])
def test_fork_rejects_path_traversal(client, bad_id):
    resp = client.post("/v1/flight/fork", json={"task_id": "task_demo", "new_task_id": bad_id})
    assert resp.status_code in (400, 404)


def test_fork_rejects_existing_destination(client):
    resp = client.post("/v1/flight/fork", json={"task_id": "task_demo", "new_task_id": "task_demo"})
    assert resp.status_code == 409


@pytest.mark.parametrize("bad_index", [-1, 4])
def test_fork_rejects_out_of_range_index(client, bad_index):
    resp = client.post("/v1/flight/fork", json={"task_id": "task_demo", "at_index": bad_index})
    assert resp.status_code == 400


def test_rejects_oversized_task_id(client):
    assert client.get("/v1/flight/tape/" + "a" * 244).status_code == 400


def test_back_to_back_default_forks_get_unique_ids(client):
    a = client.post("/v1/flight/fork", json={"task_id": "task_demo", "at_index": 1})
    b = client.post("/v1/flight/fork", json={"task_id": "task_demo", "at_index": 1})
    assert a.status_code == b.status_code == 200
    assert a.json()["forked_task_id"] != b.json()["forked_task_id"]


def test_default_fork_of_long_source_id(client, tmp_path):
    long_id = "t" * 243
    rec = FlightRecorder(task_id=long_id, recordings_dir=tmp_path)
    rec.record_event("prompt", {"text": "x"})
    rec.save_tape()
    assert client.get(f"/v1/flight/tape/{long_id}").status_code == 200
    assert client.post("/v1/flight/fork", json={"task_id": long_id, "at_index": 1}).status_code == 200
