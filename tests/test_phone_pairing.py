"""Phone pairing: single-use, expiring codes swapped for a phone token that can only view runs and approve steps."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from core.api import routes
from core.main import app
from core.security.auth import launch_token
from core.storage.database import AsyncSessionLocal
from core.storage.models import ApiTokenRecord, PairingCodeRecord

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


def pair(client, owner):
    code = client.post("/v1/auth/pairing-codes", headers=owner)
    assert code.status_code == 201, code.text
    resp = client.post("/v1/auth/pair", json={"code": code.json()["code"], "device_name": "test phone"})
    assert resp.status_code == 200, resp.text
    return code.json()["code"], resp.json()


def test_pairing_code_needs_manage_keys(client, owner):
    assert client.post("/v1/auth/pairing-codes").status_code == 401
    eng = client.post("/v1/auth/tokens", json={"name": "eng", "role": "engineer"}, headers=owner).json()["token"]
    assert client.post("/v1/auth/pairing-codes", headers=bearer(eng)).status_code == 403


def test_code_is_single_use_and_not_a_bearer_token(client, owner):
    code, paired = pair(client, owner)
    assert paired["role"] == "phone"
    assert datetime.fromisoformat(paired["expires_at"]) > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=29)
    assert client.post("/v1/auth/pair", json={"code": code}).status_code == 401
    assert client.get("/v1/auth/whoami", headers=bearer(code)).status_code == 401
    assert client.post("/v1/auth/pair", json={"code": "keelway_pair_made-up"}).status_code == 401


@pytest.mark.asyncio
async def test_expired_code_is_refused(client, owner):
    code = client.post("/v1/auth/pairing-codes", headers=owner).json()["code"]
    async with AsyncSessionLocal() as db:
        await db.execute(update(PairingCodeRecord).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        await db.commit()
    assert client.post("/v1/auth/pair", json={"code": code}).status_code == 401


@pytest.mark.asyncio
async def test_phone_token_expires(client, owner):
    _, paired = pair(client, owner)
    phone = bearer(paired["token"])
    assert client.get("/v1/auth/whoami", headers=phone).status_code == 200
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ApiTokenRecord).where(ApiTokenRecord.role == "phone")
            .values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        await db.commit()
    assert client.get("/v1/auth/whoami", headers=phone).status_code == 401


def test_phone_can_view_runs_and_status(client, owner):
    phone = bearer(pair(client, owner)[1]["token"])
    me = client.get("/v1/auth/whoami", headers=phone).json()
    assert me["role"] == "phone" and me["permissions"] == ["approve_agent_steps"]
    assert client.get("/v1/agent/runs", headers=phone).status_code == 200
    assert client.get("/v1/studio/status", headers=phone).status_code == 200


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/v1/files/tree", None),
    ("GET", "/v1/git/status", None),
    ("GET", "/v1/tasks", None),
    ("GET", "/v1/audit", None),
    ("GET", "/v1/auth/tokens", None),
    ("POST", "/v1/auth/pairing-codes", None),
    ("POST", "/v1/agent/run", {"goal": "x"}),
    ("POST", "/v1/terminal/exec", {"command": "id"}),
    ("POST", "/v1/files/save", {"path": "a.txt", "content": "x"}),
    ("POST", "/v1/studio/airgap", {"enabled": False}),
    ("POST", "/v1/agent/cancel/t1", None),
    ("GET", "/v1/events/stream", None),
])
def test_phone_is_refused_everywhere_else(client, owner, method, path, body):
    phone = bearer(pair(client, owner)[1]["token"])
    resp = client.request(method, path, headers=phone, json=body)
    assert resp.status_code == 403, (path, resp.status_code, resp.text)


class _PendingAgent:
    def __init__(self):
        self.pending_approval = {"tool_name": "write_file", "arguments": {"path": "a.py"}}
        self.decisions = []

    async def approve_pending(self, approved):
        self.decisions.append(approved)
        return {"approved": approved}


def test_phone_approves_one_step_but_cannot_allow_always(client, owner, monkeypatch):
    phone = bearer(pair(client, owner)[1]["token"])
    agent = _PendingAgent()
    monkeypatch.setitem(routes._active_agent_loops, "t-phone", agent)

    async def publish(_agent):
        return {}

    monkeypatch.setattr(routes, "_publish_agent", publish)
    denied = client.post("/v1/agent/approve/t-phone", json={"approved": True, "remember": {"scope": "a.py"}}, headers=phone)
    assert denied.status_code == 403
    assert agent.decisions == []
    ok = client.post("/v1/agent/approve/t-phone", json={"approved": True}, headers=phone)
    assert ok.status_code == 200, ok.text
    assert agent.decisions == [True]


def test_revoked_phone_token_is_refused(client, owner):
    phone = bearer(pair(client, owner)[1]["token"])
    me = client.get("/v1/auth/whoami", headers=phone).json()
    tokens = client.get("/v1/auth/tokens", headers=owner).json()
    phone_id = next(t["id"] for t in tokens if t["name"] == me["actor"])
    assert client.delete(f"/v1/auth/tokens/{phone_id}", headers=owner).status_code == 204
    assert client.get("/v1/auth/whoami", headers=phone).status_code == 401


def test_phone_has_no_studio_websocket(client, owner):
    from starlette.websockets import WebSocketDisconnect

    token = pair(client, owner)[1]["token"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/v1/ws/studio?token={token}", headers={"origin": "http://localhost:7420", "host": "localhost:7420"}):
            pass
