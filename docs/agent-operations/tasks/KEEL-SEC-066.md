# KEEL-SEC-066 — RBAC gate on /marketplace/install + /uninstall

## Summary
Closes the residual gap noted in KEEL-SEC-065: install/uninstall required only
an authenticated principal. Installing a marketplace package introduces
executable content (skills, agents, hooks) into the workspace — a mutation
tiered above plain run/approve, so it is gated like publish.

## Changes
- `core/platform/rbac_webhooks.py` — new `marketplace:install` permission in
  `ROLE_PERMISSION_MATRIX`: owner (`*`), `admin`, `builder` granted;
  `operator` and `viewer` denied fail-closed.
- `core/api/platform_routes.py` — `/marketplace/install` and
  `/marketplace/uninstall` now call `_enforce_workspace_permission(...,
  req.workspace_id, "marketplace:install")` before touching the registry.
  Layering preserved: auth → RBAC 403 → registry (404 on unknown package).
- `tests/test_unified_platform.py` — viewer/operator → 403 naming
  `marketplace:install` on both install and uninstall; builder → 200.

## Role rationale
Install mutates workspace capability (new executable content lands on disk
and can run in subsequent runs) — tiered with `agents:dispatch`/`docs:write`
(builder+), not with `workflows:run`/`p10:approve` (operator). Viewer stays
read-only.

## Verification
- `pytest tests/test_unified_platform.py` → 26 passed
- `pytest tests/test_sdk_platform.py` (with above) → 27 passed, 2 skipped
- Baseline re-run without the change confirms no pre-existing failures.
- Note: whole-dir `pytest tests/` hits an environment quirk
  (`tests.package_a_profile` shadowed by an installed `tests` package) —
  pre-existing, unrelated; CI collects via explicit file paths.

## Follow-ups
- Marketplace surface is now gated end-to-end: browse (read:all via any role),
  install (builder+), publish (builder+ + SEC-061 signature/scanner).
- `purchase`/`entitlement` flows remain auth-only by design (billing webhook
  is signature-verified, not role-gated).
