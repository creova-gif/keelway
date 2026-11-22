# KEEL-APP-078 — Companion responsive contract vs Paper 08.1/08.2

- **TASK ID**: KEEL-APP-078
- **STATUS**: READY_FOR_REVIEW
- **BRANCH**: `feature/keel-app-078-companion-contract`
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22

## Objective

`SCREEN_INVENTORY.md` marked the mobile companion "partial (page 08) —
responsive contract needed for workspace surfaces." Applied the 08.1 test:
*"if the flow needs a keyboard, a wide diff, or a shell — it stays on the
bridge, not the watch."* Two violations found and fixed.

## Deltas

| Surface | 08.1 rule | Before | After |
|---|---|---|---|
| Logs drawer `terminal` tab | "no free-text terminal on mobile — buttons never shells" | all 3 tabs reachable in companion | `visibleLogsTabs` drops `terminal` when `effectiveMobileCompanion`; active `terminal` falls back to `logs` |
| `AgentComposer` | "authoring stays on desktop — every mobile flow is a decision or a read" | free-text prompt composer on companion Tasks tab | quiet note: "Authoring stays on the desktop — the watch is for gates and reads." (`isCompanion` prop threaded from `effectiveMobileCompanion`) |

## Verified-already-conformant (no change)

- Companion nav `min-h-11 min-w-11` (44px thumb targets, 08.2)
- P-10 approve/deny fully reachable — "the primary flow" per 08.2A
- Inline Review on `?companion=1` — kept deliberately: gates require
  "approve/deny with full context"; enshrined by existing test at
  `settings-and-app.test.tsx:703`
- Files section unreachable from companion nav (keyboard surface)
- Review sidebar/logs sidebar/top workspace bar suppressed on companion
- Network tab kept — read-only egress status + Air-Gap toggle (a decision,
  not a shell)

## Verification

- `npm run typecheck` — clean
- `npm run test` — 24 files / 126 tests passed
- `npm run build` — `core/dev_app_dist` regenerated
- Artboard evidence: `get_screenshot` on `YA-0` + `ZZ-0` (token hash `3cc7b891`)

## Residual

- RN app (mobile/) got 08.2A–C via MOB-001/002; the "offline = read-only,
  actions refuse" rule and biometric gate are RN-side contracts, not dev-app.
