import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core.config import settings
from core.main import app

client = TestClient(app)
HEALING_BODY = {"test_command": "true", "max_attempts": 1}


@pytest.mark.parametrize("host", ["localhost:7420", "127.0.0.1:7420", "[::1]:7420"])
def test_studio_same_origin_requests_allowed(host):
    resp = client.get("/health", headers={"Host": host, "Origin": f"http://{host}"})
    assert resp.status_code == 200


@pytest.mark.parametrize(
    "origin",
    ["https://evil.example", "http://localhost.evil.example", "null", "http://localhost:3000", "http://127.0.0.1:8080"],
)
def test_foreign_and_other_local_origins_cannot_execute_requests(origin, monkeypatch):
    called = []
    monkeypatch.setattr("core.orchestration.self_healing.SelfHealingLoop.run_repair_cycle", lambda *a, **k: called.append(1))
    resp = client.post(
        "/v1/healing/repair",
        content=b'{"test_command": "true", "max_attempts": 1}',
        headers={"Host": "127.0.0.1:7420", "Origin": origin},
    )
    assert resp.status_code == 403
    assert "access-control-allow-origin" not in resp.headers
    assert not called


def test_rebound_hostname_rejected():
    resp = client.get("/v1/tasks", headers={"Host": "evil.example:7420", "Origin": "http://evil.example:7420"})
    assert resp.status_code == 403


def test_originless_clients_allowed():
    assert client.get("/health").status_code == 200


def test_configured_extra_origin_allowed(monkeypatch):
    monkeypatch.setattr(settings, "allowed_origins", "http://localhost:8081")
    resp = client.get("/health", headers={"Host": "127.0.0.1:7420", "Origin": "http://localhost:8081"})
    assert resp.status_code == 200


def test_studio_ws_accepts_same_origin_and_originless_clients():
    for headers in ({"host": "localhost:7420", "origin": "http://localhost:7420"}, {}):
        with client.websocket_connect("/v1/ws/studio", headers=headers) as ws:
            assert ws.receive_json()["type"] == "handshake"


@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost:3000"])
def test_studio_ws_rejects_foreign_origin(origin):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/v1/ws/studio", headers={"host": "localhost:7420", "origin": origin}) as ws:
            ws.receive_json()
    assert exc.value.code == 1008
