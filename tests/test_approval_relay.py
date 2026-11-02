import asyncio
import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from core.api import messaging_routes
from core.api.approval_relay import RelayConfig
from core.main import app
from core.models.gateway import gateway


class FakeTelegram:
    """Records outbound calls; getUpdates returns whatever button presses the test queued."""

    def __init__(self):
        self.calls, self.updates = [], []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}")
        self.calls.append((request.url.host, request.url.path, body))
        if request.url.path.endswith("/getUpdates"):
            out, self.updates = self.updates, []
            return httpx.Response(200, json={"ok": True, "result": out})
        return httpx.Response(200, json={"ok": True, "result": {}})

    def nonce(self):
        sent = [b for _, p, b in self.calls if p.endswith("/sendMessage") and "reply_markup" in b][-1]
        return sent["reply_markup"]["inline_keyboard"][0][0]["callback_data"].split(":")[2]

    def press(self, nonce, approve=True, sender="42", chat="42"):
        self.updates.append({"update_id": len(self.calls) + 1, "callback_query": {
            "id": "cb", "data": f"kw:{'a' if approve else 'd'}:{nonce}",
            "from": {"id": int(sender)}, "message": {"chat": {"id": int(chat)}},
        }})


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from core.api import routes
    from core.storage.workspace_fs import WorkspaceFilesystem
    monkeypatch.setattr(routes, "_workspace_fs", WorkspaceFilesystem(root_dir=str(tmp_path)))
    monkeypatch.setattr(routes, "_active_agent_loops", {})
    fake = FakeTelegram()
    relay = messaging_routes.relay
    client = TestClient(app)
    client.__enter__()  # start the app before configuring channels, so no background poller races the test
    monkeypatch.setattr(relay, "config", RelayConfig(
        telegram_token="T", telegram_chat_id="42", telegram_approver_ids=["42"],
        whatsapp_token="W", whatsapp_phone_id="P", whatsapp_to="254700000000", whatsapp_app_secret="S",
    ))
    monkeypatch.setattr(relay, "transport", httpx.MockTransport(fake))
    monkeypatch.setattr(relay, "_pending", {})
    monkeypatch.setattr(gateway.air_gap, "enabled", False)
    yield client, fake, tmp_path
    client.__exit__(None, None, None)


def _pause_write(client, task="m1", path="note.txt"):
    client.post("/v1/agent/run", json={"task_id": task, "goal": "g", "steps": ["w"]})
    r = client.post(f"/v1/agent/step/{task}", json={"tool_name": "write_file", "arguments": {"path": path, "content": "hi\n"}, "step_id": "step_1"})
    assert r.json()["step_result"]["status"] == "paused_for_approval"


def _poll():
    return asyncio.run(messaging_routes.relay.poll_telegram_once(timeout=0))


def test_telegram_button_approves_exactly_the_pending_call(env):
    client, fake, root = env
    _pause_write(client)
    hosts = {h for h, p, _ in fake.calls if p.endswith("/sendMessage")}
    assert hosts == {"api.telegram.org"}
    fake.press(fake.nonce())
    assert _poll() == 1
    assert (root / "note.txt").read_text() == "hi\n"
    assert client.get("/v1/agent/status/m1").json()["pending_approval"] is None


def test_non_approver_and_replayed_buttons_do_nothing(env):
    client, fake, root = env
    _pause_write(client)
    nonce = fake.nonce()
    fake.press(nonce, sender="7")
    _poll()
    assert not (root / "note.txt").exists()
    fake.press(nonce, approve=False)
    _poll()
    assert client.get("/v1/agent/status/m1").json()["pending_approval"] is None
    _pause_write(client, task="m2")
    fake.press(nonce)  # the old nonce can't approve the new request
    _poll()
    assert client.get("/v1/agent/status/m2").json()["pending_approval"] is not None


def test_air_gap_blocks_all_messaging_egress_and_remote_answers(env, monkeypatch):
    client, fake, root = env
    _pause_write(client)
    nonce = fake.nonce()
    monkeypatch.setattr(gateway.air_gap, "enabled", True)
    before = len(fake.calls)
    _pause_write(client, task="m2")
    assert client.post("/v1/messaging/test").status_code == 409
    fake.press(nonce)
    assert _poll() == 0
    assert len(fake.calls) == before
    assert not (root / "note.txt").exists()
    assert client.get("/v1/messaging/status").json()["blocked"] is True


def _signed(body: bytes, secret="S"):
    return {"x-hub-signature-256": "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest(),
            "content-type": "application/json"}


def test_whatsapp_webhook_requires_signature_and_approver(env):
    client, fake, root = env
    _pause_write(client)
    whatsapp = [b for h, p, b in fake.calls if h == "graph.facebook.com"][-1]
    nonce = whatsapp["interactive"]["action"]["buttons"][0]["reply"]["id"].split(":")[2]

    def msg(sender):
        return json.dumps({"entry": [{"changes": [{"value": {"messages": [
            {"from": sender, "interactive": {"button_reply": {"id": f"kw:a:{nonce}"}}}]}}]}]}).encode()

    assert client.post("/v1/messaging/whatsapp/webhook", content=msg("254700000000"), headers=_signed(msg("254700000000"), "wrong")).status_code == 401
    client.post("/v1/messaging/whatsapp/webhook", content=msg("15550000000"), headers=_signed(msg("15550000000")))
    assert not (root / "note.txt").exists()
    r = client.post("/v1/messaging/whatsapp/webhook", content=msg("254700000000"), headers=_signed(msg("254700000000")))
    assert r.status_code == 200 and (root / "note.txt").exists()


def test_whatsapp_verify_handshake(env):
    client, _, _ = env
    assert client.get("/v1/messaging/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "c"}).status_code == 403
