"""Versioned schema migrations for the Keelway store.

Stdlib-only runner (ADR-agnostic "or equivalent" to alembic): each entry in
``MIGRATIONS`` is an idempotent async callable applied exactly once, ordered by
``version``. New schema work lands as a new ``Migration`` here — never as an
inline ``ALTER`` in ``init_db``.

Version bookkeeping: ``PRAGMA user_version`` on SQLite; the
``keelway_schema_version`` table on other engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[AsyncConnection, bool], Awaitable[None]]


async def _sqlite_columns(conn: AsyncConnection, table: str) -> List[str]:
    res = await conn.execute(text(f"PRAGMA table_info({table})"))
    return [row[1] for row in res.fetchall()]


async def _m001_memories_vector_embedding(conn: AsyncConnection, is_sqlite: bool) -> None:
    if is_sqlite:
        if "vector_embedding" not in await _sqlite_columns(conn, "keelway_memories"):
            await conn.execute(text("ALTER TABLE keelway_memories ADD COLUMN vector_embedding JSON"))
    else:
        await conn.execute(text("ALTER TABLE keelway_memories ADD COLUMN IF NOT EXISTS vector_embedding JSONB"))


async def _m002_memories_metadata_json(conn: AsyncConnection, is_sqlite: bool) -> None:
    if is_sqlite:
        if "metadata_json" not in await _sqlite_columns(conn, "keelway_memories"):
            await conn.execute(text("ALTER TABLE keelway_memories ADD COLUMN metadata_json JSON DEFAULT '{}'"))
    else:
        await conn.execute(text("ALTER TABLE keelway_memories ADD COLUMN IF NOT EXISTS metadata_json JSONB DEFAULT '{}'::jsonb"))


async def _m003_api_tokens_expires_at(conn: AsyncConnection, is_sqlite: bool) -> None:
    if is_sqlite:
        if "expires_at" not in await _sqlite_columns(conn, "keelway_api_tokens"):
            await conn.execute(text("ALTER TABLE keelway_api_tokens ADD COLUMN expires_at DATETIME"))
    else:
        await conn.execute(text("ALTER TABLE keelway_api_tokens ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE"))


MIGRATIONS: List[Migration] = [
    Migration(1, "keelway_memories.vector_embedding", _m001_memories_vector_embedding),
    Migration(2, "keelway_memories.metadata_json", _m002_memories_metadata_json),
    Migration(3, "keelway_api_tokens.expires_at", _m003_api_tokens_expires_at),
]


async def _current_version(conn: AsyncConnection, is_sqlite: bool) -> int:
    if is_sqlite:
        res = await conn.execute(text("PRAGMA user_version"))
        return int(res.scalar() or 0)
    await conn.execute(text(
        "CREATE TABLE IF NOT EXISTS keelway_schema_version ("
        "version INTEGER PRIMARY KEY, applied_at TIMESTAMP WITH TIME ZONE DEFAULT now())"
    ))
    res = await conn.execute(text("SELECT COALESCE(MAX(version), 0) FROM keelway_schema_version"))
    return int(res.scalar() or 0)


async def _record_version(conn: AsyncConnection, is_sqlite: bool, version: int) -> None:
    if is_sqlite:
        await conn.execute(text(f"PRAGMA user_version = {int(version)}"))
    else:
        await conn.execute(
            text("INSERT INTO keelway_schema_version (version) VALUES (:v) ON CONFLICT DO NOTHING"),
            {"v": version},
        )


async def run_pending_migrations(conn: AsyncConnection, is_sqlite: bool) -> List[str]:
    """Apply unapplied migrations in version order; return names applied."""
    applied: List[str] = []
    current = await _current_version(conn, is_sqlite)
    for migration in sorted(MIGRATIONS, key=lambda m: m.version):
        if migration.version <= current:
            continue
        await migration.apply(conn, is_sqlite)
        await _record_version(conn, is_sqlite, migration.version)
        applied.append(migration.name)
    return applied
