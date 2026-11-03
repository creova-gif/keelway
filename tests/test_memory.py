"""
Tests for Keelway Memory Layer & Memory Service.
Verifies storage, scoped isolation, substring search, updates, and REST API endpoints.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from core.main import app
from core.storage.database import init_db, AsyncSessionLocal
from core.storage.memory import MemoryService, EmbeddingProvider, cosine_similarity
import tempfile
from pathlib import Path


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
            provenance_uri="https://keelway.dev/adr/001",
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
            "provenance_uri": "file:///keelway/EVAL-COMPARE-001.md",
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


@pytest.mark.asyncio
async def test_memory_hybrid_search_and_ingestion():
    async with AsyncSessionLocal() as db:
        service = MemoryService(db)

        # 1. Test Embedding Provider
        v1 = EmbeddingProvider.get_dense_embedding("autonomous coding agent sandbox")
        v2 = EmbeddingProvider.get_dense_embedding("autonomous coding agent sandbox")
        v3 = EmbeddingProvider.get_dense_embedding("banana pancake recipe breakfast")
        assert len(v1) == 128
        assert cosine_similarity(v1, v2) > 0.99
        assert cosine_similarity(v1, v3) < cosine_similarity(v1, v2)

        # 2. Test File Ingestion with Provenance
        with tempfile.NamedTemporaryFile("w+", suffix=".md", delete=False) as tmp:
            tmp.write(
                "# Security Architecture Guidelines\n\n"
                "## Layer 1: Boundary Isolation\n"
                "All shell executions must be sandboxed.\n\n"
                "## Layer 2: Approval Gate\n"
                "Tier 3 tasks require explicit human approval.\n"
            )
            tmp_path = Path(tmp.name)

        try:
            records = await service.ingest_file(tmp_path, scope="security_docs", chunk_lines=5)
            assert len(records) >= 1
            assert "file://" in records[0].provenance_uri
            assert "#L" in records[0].key

            # 3. Test Hybrid Search
            results = await service.search_hybrid(
                query_text="sandbox shell boundary",
                scope="security_docs",
                alpha=0.5,
                threshold=0.1,
            )
            assert len(results) >= 1
            top_rec, score = results[0]
            assert score > 0.1
            assert "sandboxed" in top_rec.content.lower()
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
