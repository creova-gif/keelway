"""Regression coverage for the KEEL-REL-061 `kora_*` -> `keelway_*` table rename.

Pre-rename installs persisted data in `kora_*` SQLite tables. `init_db()` must
rename them to `keelway_*` before `create_all()` so existing installs keep
their data under the canonical names.
"""

import asyncio
import sqlite3

from sqlalchemy.ext.asyncio import create_async_engine

import core.storage.database as db
from core.storage.database import init_db


def _engine_for(db_file):
    return create_async_engine(
        f"sqlite+aiosqlite:///{db_file}", connect_args={"check_same_thread": False}
    )


def _table_names(db_file):
    conn = sqlite3.connect(db_file)
    try:
        return {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()


def test_kora_tables_migrate_to_keelway(tmp_path, monkeypatch):
    db_file = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE kora_tasks (id TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE kora_audit_events (id INTEGER PRIMARY KEY, seq INTEGER);
        INSERT INTO kora_tasks VALUES ('t1', 'done');
        INSERT INTO kora_audit_events VALUES (1, 7);
        """
    )
    conn.close()

    monkeypatch.setattr(db, "engine", _engine_for(db_file))
    asyncio.run(init_db())

    names = _table_names(db_file)
    assert "kora_tasks" not in names
    assert "kora_audit_events" not in names
    assert "keelway_tasks" in names
    assert "keelway_audit_events" in names

    conn = sqlite3.connect(db_file)
    try:
        assert conn.execute(
            "SELECT status FROM keelway_tasks WHERE id='t1'"
        ).fetchone()[0] == "done"
        assert conn.execute(
            "SELECT seq FROM keelway_audit_events WHERE id=1"
        ).fetchone()[0] == 7
    finally:
        conn.close()


def test_kora_table_skipped_when_keelway_exists(tmp_path, monkeypatch):
    """If both names exist the canonical table wins; the legacy one is left untouched."""
    db_file = tmp_path / "conflict.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE kora_tasks (id TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE keelway_tasks (id TEXT PRIMARY KEY, status TEXT);
        INSERT INTO kora_tasks VALUES ('old', 'stale');
        INSERT INTO keelway_tasks VALUES ('new', 'current');
        """
    )
    conn.close()

    monkeypatch.setattr(db, "engine", _engine_for(db_file))
    asyncio.run(init_db())

    conn = sqlite3.connect(db_file)
    try:
        assert conn.execute(
            "SELECT status FROM keelway_tasks WHERE id='new'"
        ).fetchone()[0] == "current"
        # Legacy table retained for audit/manual inspection rather than dropped.
        assert conn.execute(
            "SELECT status FROM kora_tasks WHERE id='old'"
        ).fetchone()[0] == "stale"
    finally:
        conn.close()
