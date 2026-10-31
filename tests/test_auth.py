import pytest
from fastapi.testclient import TestClient

from core.main import app
from core.security.auth import launch_token

pytestmark = pytest.mark.auth


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def owner():
    return bearer(launch_token())


def mint(client, owner, role):
    resp = client.post("/v1/auth/tokens", json={"name": f"{role}-bot", "role": role}, headers=owner)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["token"].startswith("kora_")
    return body


def test_public_routes_need_no_token(client):
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("path", ["/v1/tasks", "/v1/memories", "/v1/flight/tapes", "/v1/mesh/peers", "/v1/studio/status", "/v1/audit"])
def test_api_rejects_missing_or_bad_token(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers=bearer("kora_not-a-real-token")).status_code == 401


def test_launch_token_is_owner(client, owner):
    me = client.get("/v1/auth/whoami", headers=owner).json()
    assert me["role"] == "owner"
    assert "manage_keys" in me["permissions"]


def test_engineer_can_execute_but_not_approve_pay_or_manage(client, owner):
    eng = bearer(mint(client, owner, "engineer")["token"])
    task = client.post("/v1/tasks", json={"title": "Engineer task"}, headers=eng)
    assert task.status_code == 201
    assert task.json()["owner"] == "engineer-bot"
    tid = task.json()["id"]
    for state in ("planned", "awaiting_approval"):
        assert client.post(f"/v1/tasks/{tid}/transition", json={"target_state": state}, headers=eng).status_code == 200
    assert client.post(f"/v1/tasks/{tid}/transition", json={"target_state": "running"}, headers=eng).status_code == 403
    assert client.post("/v1/payments/intent", json={"amount": 1, "recipient": "x"}, headers=eng).status_code == 403
    assert client.post("/v1/studio/airgap", json={"enabled": True}, headers=eng).status_code == 403
    assert client.post("/v1/auth/tokens", json={"name": "escalate", "role": "owner"}, headers=eng).status_code == 403

    admin = bearer(mint(client, owner, "admin")["token"])
    assert client.post(f"/v1/tasks/{tid}/transition", json={"target_state": "running"}, headers=admin).status_code == 200


def test_auditor_is_read_only(client, owner):
    aud = bearer(mint(client, owner, "auditor")["token"])
    assert client.get("/v1/tasks", headers=aud).status_code == 200
    assert client.get("/v1/audit", headers=aud).status_code == 200
    assert client.post("/v1/tasks", json={"title": "Nope nope"}, headers=aud).status_code == 403
    assert client.post("/v1/memories", json={"key": "k", "content": "c"}, headers=aud).status_code == 403


def test_revoked_token_stops_working(client, owner):
    created = mint(client, owner, "engineer")
    eng = bearer(created["token"])
    assert client.get("/v1/tasks", headers=eng).status_code == 200
    assert client.delete(f"/v1/auth/tokens/{created['id']}", headers=owner).status_code == 204
    assert client.get("/v1/tasks", headers=eng).status_code == 401
    listed = {t["id"]: t for t in client.get("/v1/auth/tokens", headers=owner).json()}
    assert listed[created["id"]]["revoked_at"] is not None
    assert "token" not in listed[created["id"]]


def test_denials_are_audited_and_chain_verifies(client, owner):
    aud = bearer(mint(client, owner, "auditor")["token"])
    client.post("/v1/tasks", json={"title": "Denied task"}, headers=aud)
    events = client.get("/v1/audit?limit=5", headers=owner).json()
    denied = [e for e in events if e["actor"] == "auditor-bot" and not e["allowed"]]
    assert denied and denied[0]["resource"] == "POST /v1/tasks"
    assert client.get("/v1/audit/verify", headers=owner).json()["valid"] is True


@pytest.mark.asyncio
async def test_tampering_breaks_the_chain(client, owner):
    from sqlalchemy import update
    from core.security.auth import verify_audit_chain
    from core.storage.database import AsyncSessionLocal
    from core.storage.models import AuditEventRecord

    client.get("/v1/auth/tokens", headers=owner)
    head = client.get("/v1/audit?limit=1", headers=owner).json()[0]
    async with AsyncSessionLocal() as db:
        await db.execute(update(AuditEventRecord).where(AuditEventRecord.seq == head["seq"]).values(allowed=not head["allowed"]))
        await db.commit()
    result = await verify_audit_chain()
    assert result["valid"] is False
    assert result["broken_at_seq"] == head["seq"]
    async with AsyncSessionLocal() as db:
        await db.execute(update(AuditEventRecord).where(AuditEventRecord.seq == head["seq"]).values(allowed=head["allowed"]))
        await db.commit()


def test_websocket_requires_token(client, owner):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/v1/ws/studio") as ws:
            ws.receive_json()
    assert exc.value.code == 1008
    with client.websocket_connect(f"/v1/ws/studio?token={launch_token()}") as ws:
        assert ws.receive_json()["type"] == "handshake"


def test_websocket_messages_enforce_role(client, owner):
    aud = mint(client, owner, "auditor")["token"]
    with client.websocket_connect(f"/v1/ws/studio?token={aud}") as ws:
        ws.receive_json()
        ws.send_json({"type": "run_self_healing", "test_command": "touch /tmp/should-not-run"})
        msg = ws.receive_json()
        assert msg["type"] == "error" and "execute_agent" in msg["message"]
