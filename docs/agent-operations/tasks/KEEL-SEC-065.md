# KEEL-SEC-065 — RBAC Publisher-Role Gate on `/marketplace/publish`

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `SECURITY / SUPPLY-CHAIN / RBAC / MARKETPLACE` |
| **Agent** | Devin |
| **Date** | 2026-11-21 |
| **Branch** | `fix/keel-sec-065-marketplace-publish-rbac` |

## Objective
Documented follow-up from KEEL-SEC-061: package tier claims were crypto-gated, but
`POST /v1/platform/marketplace/publish` required only an authenticated principal — any role
(including `viewer`/`phone` ceilings) could attempt to publish packages into the registry.
Publishing is a supply-chain write operation and must be role-gated like every other write
surface in the platform.

## Design
- New permission `marketplace:publish` added to `ROLE_PERMISSION_MATRIX` in
  `core/platform/rbac_webhooks.py`:
  - `owner` — covered by `*`
  - `admin` — granted
  - `builder` — granted (engineering persona; publishes signed packages)
  - `operator` — **denied** (workflow-run/p10-approve persona, not a publisher)
  - `viewer` — **denied** (read-only)
- The endpoint reuses the canonical `_enforce_workspace_permission` helper from
  `platform_runtime_routes` (same helper that gates `workspace:manage`, `rbac:manage`,
  `secrets:write`, `p10:approve`, etc.) — principal role → ceiling via `_PRINCIPAL_ROLE_MAP`,
  optional `X-Keelway-Role` narrowing, `check_permission` verdict → 403.
- Enforcement order: auth → RBAC (403) → manifest security scanner (422). The role gate runs
  before `publish_package` so unauthorized callers never reach the signing/scan pipeline.
- Workspace resolution uses `payload.workspace_id` with `"default"` fallback.

## Acceptance Criteria
- [x] `viewer` / `operator` effective role → HTTP 403, reason names `marketplace:publish`
- [x] `builder` / `admin` / `owner` effective role → passes gate into scanner
- [x] Unsupported `X-Keelway-Role` → HTTP 400 (pre-existing helper behavior)
- [x] Scanner/security behavior unchanged — unsigned first-party still 422 (SEC-061 layering preserved)
- [x] All existing marketplace/persistence/unified-platform tests pass unmodified

## Files Modified
- `core/platform/rbac_webhooks.py` — `marketplace:publish` added to `admin` and `builder` sets
- `core/api/platform_routes.py` — `Request` import; `_enforce_workspace_permission` +
  `get_rbac_controller` + `WorkspaceRbacController` imports; gate call in
  `publish_marketplace_package` before `mp.publish_package`
- `tests/test_unified_platform.py` — role-gate regression cases: viewer+operator 403,
  builder reaches scanner (422), invalid role header 400

## Tests Executed
- `pytest tests/test_unified_platform.py -x -q` → `26 passed`
- `pytest tests/test_manifest_signing_key_management.py tests/test_marketplace_settlement_and_cluster_sdk.py tests/test_platform_persistence_and_enterprise.py tests/test_sdk_platform.py -x -q` → `33 passed, 3 skipped`
- `python3 -m py_compile core/api/platform_routes.py core/platform/rbac_webhooks.py` → clean (no local ruff; CI lint covers)

## Known Risks & Blockers
- `marketplace/scan` and `marketplace/install` remain auth-only (any role). Scan is a
  read-only analysis; install already takes a `workspace_id` and could gain an
  `install`-scoped permission in a follow-up if workspace-level install control is wanted.
- `_enforce_workspace_permission` is a private-name import across sibling route modules;
  promoting it to a shared helper module is a possible future refactor but out of scope.

## Next Recommended Action
- CI green → merge. Optionally follow up with an `install`-scoped permission on
  `/marketplace/install`.
