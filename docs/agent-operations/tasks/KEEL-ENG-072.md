# KEEL-ENG-072 — versioned schema migration framework

- **Status**: COMPLETED
- **Agent**: Devin
- **Date**: 2026-11-27
- **Branch**: `feat/keel-eng-072-migrations`

## Objective & acceptance

P2 backlog: "schema migration framework (alembic or equivalent)".
Acceptance: ordered, tracked, idempotent migrations replacing the
hand-rolled `ALTER TABLE` evolutions in `init_db`; zero new runtime
dependencies; tests green.

## Design decision

Stdlib runner over alembic: the repo enforces zero-unapproved-runtime-deps
(AGENTS.md §1; `scripts/check_python_lock.sh`), and the backlog's
"or equivalent" licenses a lighter mechanism. `keelway_core`'s own
stdlib+SQLite posture set precedent.

- `core/storage/migrations.py`: `Migration(version, name, apply)` +
  ordered `MIGRATIONS` list + `run_pending_migrations(conn, is_sqlite)`.
- Bookkeeping: `PRAGMA user_version` on SQLite;
  `keelway_schema_version` table on non-SQLite engines.
- The three pre-existing evolutions are backfilled as migrations 1–3
  (`vector_embedding`, `metadata_json`, `expires_at`) — all idempotent
  (PRAGMA column check / `IF NOT EXISTS`), so existing DBs re-record
  version without re-running ALTERs.
- `init_db` now delegates to the runner; the `except: pass` around the
  memories ALTERs is gone — migration failures propagate (fail-closed
  rather than silently booting on a drifted schema).

## Contract for future schema work

Append `Migration(N, "table.column", fn)` — never inline ALTERs in
`init_db`. Non-SQLite branches must use `IF NOT EXISTS`/`ON CONFLICT`.

## Evidence

- `mypy` (2.4.1): 0 errors, 347 files (migrations.py under the
  disallow_untyped_defs gate)
- `ruff check .`: clean
- `pytest`: 3/3 new migration tests + 19 api/memory/audit/entitlements
- Verified against simulated pre-migration schema: columns added,
  `user_version` recorded, re-run is a no-op

## Residual

- `kora_%`→`keelway_%` table rename predates the framework (kept inline;
  it is a rename sweep, not a column evolution, and runs before
  create_all by design).
- Postgres path exercised only in unit shape (`keelway_schema_version`
  DDL/upsert), not against a live PG — same limitation the previous
  inline code had.
