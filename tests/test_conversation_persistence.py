"""P0-1: Conversation persistence — history survives session teardown and
is owner-scoped across the API surface."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.api.routes import router
from core.api.schemas import MessageSchema, Provider
from core.orchestration.chat import InteractiveChatSession
from core.storage.database import AsyncSessionLocal
from core.storage.models import ConversationRecord


@pytest.mark.asyncio
async def test_new_conversation_creates_owned_record():
    session = InteractiveChatSession(provider=Provider.LOCAL)
    conv_id = await session.new_conversation(owner="local")

    async with AsyncSessionLocal() as db:
        rec = await db.get(ConversationRecord, conv_id)
    assert rec is not None
    assert rec.owner == "local"
    assert rec.mode == "ask"
    assert rec.provider == "local"
    assert session.conversation_id == conv_id


@pytest.mark.asyncio
async def test_persist_and_load_roundtrip_restores_turns():
    session = InteractiveChatSession(provider=Provider.LOCAL)
    conv_id = await session.new_conversation(owner="local")
    session.history.append(MessageSchema(role="user", content="how do I rotate a token?"))
    session.history.append(MessageSchema(role="assistant", content="run keelway token create"))
    await session._persist_conversation()

    resumed = InteractiveChatSession(provider=Provider.LOCAL)
    assert await resumed.load_conversation(conv_id, owner="local") is True
    contents = [m.content for m in resumed.history]
    assert "how do I rotate a token?" in contents
    assert "run keelway token create" in contents


@pytest.mark.asyncio
async def test_load_conversation_enforces_owner_isolation():
    session = InteractiveChatSession(provider=Provider.LOCAL)
    conv_id = await session.new_conversation(owner="local")

    outsider = InteractiveChatSession(provider=Provider.LOCAL)
    assert await outsider.load_conversation(conv_id, owner="someone-else") is False
    assert outsider.conversation_id is None


@pytest.mark.asyncio
async def test_load_conversation_missing_returns_false():
    session = InteractiveChatSession(provider=Provider.LOCAL)
    assert await session.load_conversation("does-not-exist", owner="local") is False


@pytest.mark.asyncio
async def test_title_derived_from_first_user_turn():
    session = InteractiveChatSession(provider=Provider.LOCAL)
    conv_id = await session.new_conversation(owner="local")
    session.history.append(MessageSchema(role="user", content="summarize the release plan"))
    await session._persist_conversation()

    async with AsyncSessionLocal() as db:
        rec = await db.get(ConversationRecord, conv_id)
    assert rec is not None
    assert rec.title == "summarize the release plan"


@pytest.mark.asyncio
async def test_unbound_session_persist_is_noop():
    session = InteractiveChatSession(provider=Provider.LOCAL)
    session.history.append(MessageSchema(role="user", content="ephemeral"))
    await session._persist_conversation()  # must not raise
    assert session.conversation_id is None


def test_conversation_api_create_list_and_retrieve():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    resp = client.post("/v1/chat/message", json={"message": "hello from the beta audit"})
    assert resp.status_code == 200
    conv_id = resp.json().get("conversation_id")
    assert conv_id

    listed = client.get("/v1/conversations")
    assert listed.status_code == 200
    ids = [c["id"] for c in listed.json()["conversations"]]
    assert conv_id in ids

    fetched = client.get(f"/v1/conversations/{conv_id}")
    assert fetched.status_code == 200
    turns = fetched.json()["turns"]
    assert any(t["role"] == "user" and "hello from the beta audit" in t["content"] for t in turns)

    missing = client.get("/v1/conversations/nope")
    assert missing.status_code == 404
