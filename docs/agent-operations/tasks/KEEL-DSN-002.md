# KEEL-DSN-002 — Token registry delta closure (TOKENS.md open rows)

- **Status**: READY_FOR_REVIEW
- **Agent**: Devin
- **Date**: 2026-11-23
- **Branch**: `feature/keel-dsn-002-token-deltas`

## Objective

Close the three rows TOKENS.md left open after KEEL-DSN-001's
Paper↔code reconciliation, and remove staleness in `tokens.json`.

## Resolutions

| Row | Decision | Why |
|---|---|---|
| `--fs-body` 17px vs website `.kw-body` 16px | **website adopted 17px** (`1.0625rem`) | TOKENS.md's own recommendation; Paper is canonical for values |
| `--dim` `#5D6268` vs website `#8a9096` | **Exception recorded** | Website `--dim` colors content-bearing captions (dates, `/seat/mo`, input placeholders). Canonical `#5d6268` is 3.5:1 — decorative-only per DESIGN.md and would fail WCAG AA on real content. `#8a9096` (~6:1) is the correct intentional divergence |
| `--fs-heading`/`--fs-display` | `resolved-convention` | Already decided in TOKENS.md (fluid `clamp()` wins; Paper values are 1440-grid reference points) — JSON status synced |

## Staleness fixes in `tokens.json`

- `color.accentWash.paper`: `14%` → `12%` (Paper was updated 2026-11-22;
  the registry still recorded the old value)
- `color.accent.website` / `color.accentWash.website`: `--brass*` names →
  `--accent*` (KEEL-WEB-004 renamed; globals.css carries no `brass` tokens)

## Files

- `website/src/app/globals.css` — `.kw-body` `font-size: 1rem` → `1.0625rem`
- `docs/design/tokens.json` — resolutions + stale-value corrections
- `docs/design/TOKENS.md` — open rows marked resolved

## Verification

- `npm --prefix website run typecheck` — clean
- `tokens.json` parses; every `delta-flagged` status now resolved/recorded
- Mobile `theme/index.ts` audited against the registry — already
  value-identical (KEEL-MOB-001); no change needed

## Follow-ups

- None open in the registry. Next token change should follow the
  TOKENS.md §Sync workflow (Paper first, `tokens.json` in the same PR).
