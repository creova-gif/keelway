# KEEL-ENG-066 — Conversation Persistence (Beta P0-1)

**Status:** COMPLETED
**Owner:** Devin
**Date:** 2026-11-27
**Branch:** `feature/keel-beta-p0-conversations`

## Objective & Acceptance Criteria

Beta P0 requirement: "Conversations — history, persistence and retrieval."

- [x] Conversations survive process restart (persisted to `keelway_conversations` table)
- [x] `POST /v1/chat/message` accepts optional `conversation_id`; creates a bound record otherwise and returns `conversation_id` in the result
- [x] `GET /v1/conversations` lists the actor's conversations (owner-scoped, newest first, capped at 100)
- [x] `GET /v1/conversations/{id}` returns the full turn history; 404 on missing or foreign-owned records (no existence disclosure)
- [x] `keelway chat --conversation <id>` resumes a persisted conversation; new REPL sessions auto-create a record
- [x] Persistence failures degrade gracefully (logged warning) — they never break the chat path

## Files Modified

- `core/storage/models.py`: `ConversationRecord` (id, title, mode, provider, owner idx, timestamps, `turns` JSON)
- `core/orchestration/chat.py`: `new_conversation`, `load_conversation`, `_persist_conversation`; `step()` persists after mode dispatch
- `core/api/routes.py`: `conversation_id` handling in `/v1/chat/message`; two retrieval endpoints
- `cli.py`: `--conversation` flag threaded into `cmd_chat`
- `tests/test_conversation_persistence.py`: 7 tests (record creation, roundtrip restore, owner isolation, missing-id, title derivation, unbound no-op, API create/list/retrieve/404)

## Tests Executed

- `pytest tests/test_conversation_persistence.py`: **7 passed**
- `python -m mypy` (2.4.1): **0 errors / 297 files**
- `ruff check .`: clean

## Known Risks

- `turns` JSON column stores the full serialized history per write — acceptable for local single-operator workloads; a turn-row table is the scale-out follow-up if needed
- API-created conversations are owned by the token actor (`launch-token`); CLI-created ones by `local` — cross-surface resume is intentionally owner-scoped; documented in release notes
- Persistence swallows DB errors by design (chat must not fail on storage hiccup); failures surface only via `logger.warning` — monitoring should alert on it
