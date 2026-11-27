"""Versioned schema migration runner (KEEL-ENG-072)."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from core.storage.migrations import MIGRATIONS, run_pending_migrations


@pytest.mark.asyncio
async def test_fresh_sqlite_db_applies_all_migrations(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/m.db")
    async with engine.begin() as conn:
        # Simulate a pre-migration schema: tables exist, evolved columns absent.
        await conn.execute(text("CREATE TABLE keelway_memories (id INTEGER PRIMARY KEY)"))
        await conn.execute(text("CREATE TABLE keelway_api_tokens (id INTEGER PRIMARY KEY)"))
        applied = await run_pending_migrations(conn, is_sqlite=True)
        assert applied == [m.name for m in MIGRATIONS]
        cols = {r[1] for r in (await conn.execute(text("PRAGMA table_info(keelway_memories)"))).fetchall()}
        assert {"vector_embedding", "metadata_json"} <= cols
        tok = {r[1] for r in (await conn.execute(text("PRAGMA table_info(keelway_api_tokens)"))).fetchall()}
        assert "expires_at" in tok
    await engine.dispose()


@pytest.mark.asyncio
async def test_migrations_are_idempotent(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/m.db")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE keelway_memories (id INTEGER PRIMARY KEY, vector_embedding JSON, metadata_json JSON)"))
        await conn.execute(text("CREATE TABLE keelway_api_tokens (id INTEGER PRIMARY KEY, expires_at DATETIME)"))
        await run_pending_migrations(conn, is_sqlite=True)
    async with engine.begin() as conn:
        assert await run_pending_migrations(conn, is_sqlite=True) == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_user_version_records_progress(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/m.db")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE keelway_memories (id INTEGER PRIMARY KEY)"))
        await conn.execute(text("CREATE TABLE keelway_api_tokens (id INTEGER PRIMARY KEY)"))
        await run_pending_migrations(conn, is_sqlite=True)
        v = (await conn.execute(text("PRAGMA user_version"))).scalar()
        assert v == max(m.version for m in MIGRATIONS)
    await engine.dispose()
