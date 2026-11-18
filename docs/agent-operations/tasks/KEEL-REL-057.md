# KEEL-REL-057 — Single API Authority (D-001): Fallback Server `/v1` Shadow Surface

| Field | Value |
|---|---|
| **Status** | `READY_FOR_REVIEW` |
| **Category** | `RELEASE / API / SECURITY` |
| **Agent** | Devin |
| **Date** | 2026-11-18 |
| **Branch** | `fix/KEEL-REL-057-single-api-authority` (stacked on `feature/KEEL-P0-063-permissions-depth`) |
| **ADR** | `docs/decisions/ADR-0045-single-api-authority.md` |

## Objective
Release-readiness Phase 1 item "D-001": designate a single authoritative `/v1`
API surface and remove the shadow implementation.

## Verified finding
`cli.py cmd_dev`/`cmd_desktop` installed a zero-dependency `http.server`
fallback (`SovereignStudioHandler`) when uvicorn was unavailable and
`AUTH_REQUIRED=false`. It re-implemented `/v1/*` paths against the service
layer directly:
- `POST /v1/files/save` — **unauthenticated file write; no principal, no P-10
  gate, no audit event** (governance bypass).
- `GET /v1/flight/tapes` → `{"tapes": []}`, `GET /v1/agent/status` → hardcoded
  `"idle"`, `POST /v1/agent/run` → fabricated *completed* plan — stub data
  rendered as product truth (the defect class KEEL-P0-029 removed client-side).

## Implementation
- **ADR-0045** records the decision: `core.main:app` is the sole `/v1`
  authority; auxiliary servers must proxy or use non-`/v1` prefixes; new routes
  live in `core/api/` + `current_principal`/documented allowlist.
- New `core/api/fallback_server.py`: `StaticFallbackHandler` serves only `/`,
  `/studio`, `/index.html`, and `/health` (`status: degraded`,
  `api_available: false`). Every `/v1/*` GET/POST → `503` +
  `{"api_available": false}`. Extracted to module level so it is importable
  and test-pinned.
- `cli.py`: ~170-line nested handler replaced with `serve_static_fallback()`.

## Evidence
- `pytest tests/test_fallback_server.py` — **12 passed**: studio shell + CSP,
  degraded health, 8 `/v1` GET paths → 503 (no stub keys), `/v1/files/save`
  refused and writes nothing, `/v1/agent/run` returns no fabricated plan,
  source-level guard asserting cli.py holds no `/v1` handler branches.
- `pytest tests/test_keelway_core_cli.py` — 7 passed.
- Full backend suite: **1479 passed, 2 skipped** (`pytest tests/ -q`, 6m13s).
  Includes `test_system_doctor.py` pin fix — catalog assertions updated 8 → 14
  skills, missed in the earlier kstack expansion (`541cd88`).
- `py_compile` on `cli.py`, `fallback_server.py` — clean. Ruff unavailable.
- Dev-app: `tsc --noEmit` clean, 111/111 vitest, `vite build` fresh.

## Frontend consumer audit (D-001 closure)
Extracted **229 `/v1` call sites** across `dev-app/src` + `core/studio` and
diffed against the real `core.main:app` OpenAPI inventory (**317 routes**) plus
the `/v1/ws/studio` WebSocket route:
- **Every frontend call resolves to a real route.** Studio's
  `POST /v1/files/save`, `/v1/agent/run`, `/v1/agent/runs` all exist on the
  real API and are principal-gated (`EXECUTE_AGENT`) — the removed fallback
  shadows break no consumer; under the fallback they now get an honest 503.
- One honesty defect found and fixed (`fe0ce91`): seeded example workflow
  `WF-02` in `platformData.ts` advertised `POST /v1/webhooks/git-push` —
  a non-existent route — as its trigger spec. Now reads
  `git push event (registered via POST /v1/platform/webhooks)`.

## Known limits
- Static fallback still serves cwd files via `SimpleHTTPRequestHandler`
  fallback for non-`/v1` unknown paths (parity with prior behavior).
- Route-inventory guard scans `cli.py`; other files adding `/v1` servers would
  need the same check — a full inventory linter is follow-up scope.

## Next recommended action
- Release-readiness Phase 1 continues: remaining D-items per owner review of
  ADR-0045; ratify status to `Accepted` on merge.
