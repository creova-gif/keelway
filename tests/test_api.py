"""
Integration tests for the Kora AI Core FastAPI service.
Tests health checks, task creation, retrieval, and state transitions.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from core.main import app
from core.storage.database import init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Ensure database schema is created before tests."""
    await init_db()


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert data["database_connected"] is True


@pytest.mark.asyncio
async def test_task_lifecycle_and_state_transition():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create Task
        create_payload = {
            "title": "Evaluate model arbitrage",
            "description": "Compare Claude and local Qwen on PR brief",
            "owner": "founder",
            "budget_usd": 0.25,
            "payload": {"repo": "kora-ai"},
        }
        res_create = await client.post("/v1/tasks", json=create_payload)
        assert res_create.status_code == 201
        task = res_create.json()
        assert task["title"] == create_payload["title"]
        assert task["state"] == "created"
        task_id = task["id"]

        # 2. Get Task by ID
        res_get = await client.get(f"/v1/tasks/{task_id}")
        assert res_get.status_code == 200
        assert res_get.json()["id"] == task_id

        # 3. Valid State Transition: CREATED -> PLANNED
        res_trans_1 = await client.post(
            f"/v1/tasks/{task_id}/transition",
            json={"target_state": "planned"},
        )
        assert res_trans_1.status_code == 200
        assert res_trans_1.json()["state"] == "planned"

        # 4. Valid State Transition: PLANNED -> AWAITING_APPROVAL
        res_trans_2 = await client.post(
            f"/v1/tasks/{task_id}/transition",
            json={"target_state": "awaiting_approval"},
        )
        assert res_trans_2.status_code == 200
        assert res_trans_2.json()["state"] == "awaiting_approval"

        # 5. Invalid State Transition: Cannot jump from AWAITING_APPROVAL to COMPLETED
        res_invalid = await client.post(
            f"/v1/tasks/{task_id}/transition",
            json={"target_state": "completed"},
        )
        assert res_invalid.status_code == 409  # Conflict
        assert "Invalid task state transition" in res_invalid.json()["detail"]


@pytest.mark.asyncio
async def test_get_nonexistent_task():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/tasks/non-existent-uuid")
        assert response.status_code == 404
