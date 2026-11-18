# KEEL-REL-054 — Studio Data-Provenance Indicator (State Audit)

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / UI / HONEST-CLAIMS` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-REL-054-data-provenance` |

## Objective
Release gap: audit Studio empty/loading/error states. Found a systemic
honesty gap — silent fallback data with no user-visible signal.

## Implementation
- `docs/audits/STUDIO_STATES_2026-11-16.md` — full audit.
- `api.ts`: `subscribeDataFallbacks()` pub/sub; every fallback return in
  `requestSameOriginDecoded` increments a counter and notifies.
- `StatusBarEgress`: new `fallbackResponseCount` prop renders
  `Offline data ×N` warning when >0.
- `DevAppShell`: subscribes and passes the count.
- 2 new tests for subscribe/unsubscribe semantics.

## Evidence
- `npx tsc --noEmit` clean; `npx vitest run` — 108/108 pass.

## Known Limits
- Sticky session count (does not decrement on later live successes).
- `exportAuditBundle` bypass path not instrumented; SSE paths out of scope.
- Per-panel provenance badges remain future work.

## Next Recommended Action
Website a11y/perf CI; KEEL-PROD-041 weights decision (founder).
