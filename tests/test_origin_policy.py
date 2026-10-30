import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core.main import app

client = TestClient(app)


@pytest.mark.parametrize("origin", ["http://localhost:7420", "http://127.0.0.1:7420", "http://[::1]:7420"])
def test_cors_allows_loopback_origins(origin):
    resp = client.options(
        "/v1/healing/repair",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin


@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost.evil.example", "null"])
def test_cors_rejects_foreign_origins(origin):
    resp = client.options(
        "/v1/healing/repair",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )
    assert "access-control-allow-origin" not in resp.headers


def test_studio_ws_accepts_same_origin_and_originless_clients():
    for headers in ({"origin": "http://localhost:7420"}, {}):
        with client.websocket_connect("/v1/ws/studio", headers=headers) as ws:
            assert ws.receive_json()["type"] == "handshake"


def test_studio_ws_rejects_foreign_origin():
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/v1/ws/studio", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()
    assert exc.value.code == 1008
