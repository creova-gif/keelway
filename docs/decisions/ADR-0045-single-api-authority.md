# ADR-0045: `core.main:app` Is the Single Authority for All `/v1/*` API Paths

- **Status**: Accepted (release-readiness decision D-001, 2026-11-18; task KEEL-REL-056)
- **Supersedes**: implicit policy that any process may serve `/v1` paths as a convenience fallback
- **Informed by**: decision-precedence §3 (sovereign fail-closed policy), §4 (single runtime invariant), KEEL-P0-029 (no fabricated state behind real API contracts)

## Context

Verified findings in this tree:

1. `core.main:app` is a single FastAPI application aggregating ~20 routers
   (`core/api/*.py`) under `/v1/*`. Every mutating route is gated by
   `current_principal` / `require(Permission.*)`; approvals, revocations, and
   denials are written to the append-only Merkle audit chain.
2. `cli.py`'s `cmd_dev`/`cmd_desktop` install a **second, independent HTTP
   server** — a zero-dependency `http.server` fallback ("SovereignStudioHandler")
   that engages when uvicorn is unavailable and `AUTH_REQUIRED=false`. It
   re-implemented `/v1/*` paths directly against the service layer:
   - `POST /v1/files/save` wrote workspace files with **no principal, no P-10
     approval gate, no audit event** — a standing-approval and governance bypass.
   - `GET /v1/flight/tapes` → `{"tapes": []}`, `GET /v1/agent/status` →
     hardcoded `"idle"`, `POST /v1/agent/run` → a fabricated *completed* plan.
     The Studio UI rendered these stubs as real product truth (the exact defect
     class KEEL-P0-029 removed from the dev-app client).
   - `GET /v1/files/*`, `/v1/git/*`, `/v1/index/*` called `WorkspaceFilesystem`
     and `CodebaseSemanticIndex` directly, bypassing `current_principal`, rate
     limiting, and audit.
3. Static UI surfaces (`/app`, `/studio`, `/console`) are not API authorities.
   The marketing site's `api/early-access.js` serverless function lives on a
   separate domain, serves no `/v1` path, and is out of scope.
4. `core/demo.py` delegates to `cmd_dev`; no other `/v1` server exists.

## Decision

1. **`core.main:app` is the sole authoritative HTTP surface for `/v1/*`.** Only
   routers under `core/api/` mounted in `core/main.py` may define `/v1` paths.
2. **The zero-dependency fallback server is static-serving only.** It may serve
   `/`, `/studio`, its assets, and `/health` (which must report
   `api_available: false`, `status: degraded`). Any `/v1/*` request returns
   `503` with `{"error": "...", "api_available": false}` — honest degradation.
   It must never return stub resource data and never call the service layer.
3. **New `/v1` routes** must live in a `core/api/*_routes.py` router, be
   registered in `core/main.py`, delegate to the service layer (no
   re-implementation), and declare `current_principal` — or appear on a
   documented public-path allowlist (`/health`, the auth-token mint surface).
4. **Future auxiliary servers** (mobile pairing, mesh peer endpoints) must
   either proxy to `core.main:app` or use a distinctly-prefixed internal
   surface. They may not bind `/v1` paths.
5. **Enforcement**: the fallback handler is extracted to
   `core/api/fallback_server.py` so it is importable and pinned by tests
   (`tests/test_fallback_server.py`); a route-inventory assertion keeps `/v1`
   definitions inside `core/api/`.

## Consequences

- **Positive**: the unauthenticated file-write and fake-run hole is closed;
  degraded installs show honest unavailability instead of plausible-looking
  fabricated state; every `/v1` consumer is guaranteed the RBAC + audit-gated
  contract; one schema/behavior owner per path.
- **Negative**: a zero-dependency install can no longer browse or save files in
  Studio — it previously "worked", but silently insecurely. That is the
  intended fail-closed trade-off.
- **Migration**: none required for consumers — the real server's contract is
  unchanged. The fallback's `/v1` surface is removed, not redirected.
