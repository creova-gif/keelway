# KEEL-APP-068 — Light panels sweep (Paper 17.6 `2LS-0`)

## Status
READY_FOR_REVIEW

## Finding
17.6 confirmed shipped grammar for Appearance/Labs/Keyboard — no changes needed; Labs epistemic cards are intentionally richer than artboard rows (honesty wins).

## Wired
- **Session token row** on General & Workspace — real `getStudioToken()`, prefix-only (`xxxxxxxx…`) + "rotate via CLI"; honest absent state: "not configured — unauthenticated loopback"

## Verified
- `tsc --noEmit` clean · `vitest run`: 24/120 pass incl. axe · `vite build` green · `dev_app_dist` regenerated
