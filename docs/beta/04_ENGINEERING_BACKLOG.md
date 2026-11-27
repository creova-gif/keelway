# 04 — Engineering Backlog (P0 blockers first, evidence-based)

Each P0 has a falsifiable acceptance criterion. Owner = lane from
`12_AGENT_COORDINATION.md`.

## P0 — release blockers

| ID | Work item | Evidence today | Acceptance criterion | Owner |
| -- | --------- | -------------- | -------------------- | ----- |
| P0-1 | **Persist conversations** — `InteractiveChatSession.history` is in-memory; survive restart | `core/orchestration/chat.py:134` `self.history: List[MessageSchema]` | New `ConversationRecord` in `core/storage/models.py`; `cli chat`/dev-app reload shows prior turns after server restart; pytest proves write+read | Backend |
| P0-2 | **Verify composed golden journey on beta env** — 30-step test exists since REL-063 | `tests/test_composed_coding_journey.py` | Green run recorded against a clean checkout + fresh `.keelway` state | QA |
| P0-3 | **Deploy smoke** — docker-compose stack actually serves | `docker-compose.yml` defines 2 services | `docker compose up` → `/v1/health` + studio index reachable; result in 13_RELEASE_REPORT | Backend+QA |
| P0-4 | **`?token=` in URL** — dev-app accepts bearer via query param | `dev-app/src/lib/api.ts:53` | Token accepted via header only, or limitation explicitly documented in 11_KNOWN_LIMITATIONS + onboarding | Security+Frontend |
| P0-5 | **Beta onboarding docs** — install → token → first agent run | none found in `docs/` | `docs/beta/onboarding` section in 09 runbook; verified by a cold-run | Docs/QA |
| P0-6 | **Ollama wedge guard** — `OllamaBridge` hardcodes `127.0.0.1:11434`, ignores `OLLAMA_BASE_URL`, hangs ~120 s when runner wedges | `core/opencore/runtime.py:363` | Bridge honors `OLLAMA_BASE_URL`; request timeout bounded ≤30 s with honest error | Backend |

## P1 — ship if validated

| ID | Work item | Acceptance criterion |
| -- | --------- | -------------------- |
| P1-1 | `MiroFishSwarmHarness` event-loop deadlock (`test_cli_swarm_offline_benchmark_json` hangs on clean HEAD) | Test passes deterministically or quarantined with reason |
| P1-2 | Usage analytics surfaced in dev-app (cost ledger exists) | Usage view reads real ledger rows; axe clean |
| P1-3 | File-intelligence upload path verified | Upload → process → retrieve journey green or feature-flagged off |
| P1-4 | Monaco LSP/symbol nav verified or labeled | Feature traceability updated with real state |
| P1-5 | Docker runner environment contract (create/exec/snapshot) | `GET /v1/runner/environment/status` honest + tests green |

## P2 — post-beta

- Multi-user accounts / SSO / SCIM (positioning decision first)
- Schema migration framework (alembic or equivalent)
- `keelway_core` removal after deprecation window
- dev-app bundle code-splitting (1.2 MB single chunk)
- `web-next` → `website` cutover
- `disallow_untyped_defs` mypy ratchet (176 errors/30 files)
- `packages` expansion beyond `core`
