"""
Tests for Kora AI Memory Layer & Memory Service.
Verifies storage, scoped isolation, substring search, updates, and REST API endpoints.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from core.main import app
from core.storage.database import init_db, AsyncSessionLocal
from core.storage.memory import MemoryService


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    await init_db()


@pytest.mark.asyncio
async def test_memory_service_crud_and_search():
    async with AsyncSessionLocal() as db:
        service = MemoryService(db)

        # 1. Store
        rec = await service.store(
            key="adr_001_core",
            content="ADR-001 establishes the shared AI Core for CLI and Personal Agent.",
            scope="project",
            provenance_uri="https://kora.tech/adr/001",
        )
        assert rec.id is not None
        assert rec.key == "adr_001_core"
        assert rec.scope == "project"

        # 2. Get
        fetched = await service.get(key="adr_001_core", scope="project")
        assert fetched is not None
        assert fetched.content == rec.content

        # 3. Search
        search_results = await service.search(query_text="ADR-001 shared Core", scope="project")
        assert len(search_results) >= 1
        assert search_results[0].key == "adr_001_core"

        # 4. Upsert (update)
        updated = await service.store(
            key="adr_001_core",
            content="ADR-001 updated: added 4-tier human approval gate.",
            scope="project",
        )
        assert updated.id == rec.id
        assert "4-tier" in updated.content

        # 5. Delete
        deleted = await service.delete(key="adr_001_core", scope="project")
        assert deleted is True

        post_delete = await service.get(key="adr_001_core", scope="project")
        assert post_delete is None


@pytest.mark.asyncio
async def test_memory_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create
        create_payload = {
            "key": "eval_rubric_001",
            "content": "EVAL-COMPARE-001 scores on summary, ranked risks, next actions, and citations.",
            "scope": "evaluation",
            "provenance_uri": "file:///kora-ai/EVAL-COMPARE-001.md",
        }
        res_create = await client.post("/v1/memories", json=create_payload)
        assert res_create.status_code == 201
        data = res_create.json()
        assert data["key"] == "eval_rubric_001"
        assert data["scope"] == "evaluation"

        # Search
        res_search = await client.get("/v1/memories", params={"q": "rubric", "scope": "evaluation"})
        assert res_search.status_code == 200
        items = res_search.json()
        assert len(items) >= 1
        assert items[0]["key"] == "eval_rubric_001"

        # Get by key
        res_get = await client.get("/v1/memories/eval_rubric_001", params={"scope": "evaluation"})
        assert res_get.status_code == 200
        assert res_get.json()["key"] == "eval_rubric_001"

        # Delete
        res_del = await client.delete("/v1/memories/eval_rubric_001", params={"scope": "evaluation"})
        assert res_del.status_code == 204

        # Verify 404 after delete
        res_check = await client.get("/v1/memories/eval_rubric_001", params={"scope": "evaluation"})
        assert res_check.status_code == 404
