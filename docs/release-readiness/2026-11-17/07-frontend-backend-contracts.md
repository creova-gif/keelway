# Frontend ↔ Backend Contracts

- Single REST surface on one FastAPI app (`core.main:app`). Studio calls via `api(path,{method,body})` helper → `/v1/*`. Web console calls same API. CLI talks HTTP for `dev`-adjacent commands.
- OpenAPI: `24-api-schemas/openapi.json` (159 paths) generated from the live app — authoritative.
- Known duplication: README documents a governance API on :8000; code contains governance origins config but no separate authoritative external contract — recorded as architecture risk, ADR pending.
- Contract drift check: every `api()` call path in studio.js was cross-checked against routes during UI sessions; runner enqueue body-shape bug found+fixed by live test (double-JSON-encoding). No codegen'd SDK clients exist → Phase 1 item.
