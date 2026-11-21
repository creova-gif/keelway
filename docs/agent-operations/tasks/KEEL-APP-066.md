# KEEL-APP-066 — Settings Models deep-dive wiring (Paper 17.4 `2H0-0`)

## Status
READY_FOR_REVIEW

## Deltas wired (chrome only — all props, backend calls, ARIA preserved)
1. Runtime right-status: `SemanticBadge opencore` → quiet mono `127.0.0.1 · loopback only` per 17.4 grammar
2. Host memory meter: `(39%)` → `· measured` honesty marker per artboard
3. Dry-run right-status: `kind="live"` → `kind="simulated"` labeled `Simulated · $0.00 · 0 tokens` — a simulator must never read as live

## Verified
- `tsc --noEmit` clean
- `vitest run`: 24 files / 120 tests pass (incl. axe WCAG 2.2 AA gates)
- `vite build` green; `core/dev_app_dist` regenerated

## Next
KEEL-APP-067: Network & Egress deep-dive (17.5 `2JZ-0`) + light-panel details (17.6 `2LS-0`).
