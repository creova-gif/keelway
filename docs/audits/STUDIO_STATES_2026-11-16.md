# Studio State Audit — Empty / Loading / Error / Provenance

> KEEL-REL-054 · 2026-11-16 · Scope: `dev-app/` (Keelway Studio React workspace)

## Method
Grepped all platform panels and screens for loading, empty, and error
handling; traced the API client's fallback behavior; ran the full vitest
suite (106 tests) as regression baseline.

## Findings

### Empty states — mostly GOOD
Explicit empty states exist in the major list surfaces:
`AutomationAndOpsViews` (no runs), `EnterpriseIdentityAndQuorumPanel`
(no SCIM users / no quorum), `FlightTapeDebuggerPanel` (no traces, only
when `listSource === "live"`), `KBrainMemoryGraphPanel`,
`KSpacesCrdtAndKflowPanel`, `McpLockfileAndBenchPanel`,
`ShadowCacheAndDistillationPanel`, `FilesDiffAndCommit`.

### Loading states — PARTIAL
`SettingsModelsPanel` shows "Inspecting local OpenCore weights…".
Most panels render fixture/fallback data instantly, so a loading state
is rarely distinguishable from an empty result — acceptable for the
local-first model, but see provenance gap below.

### Error states — SYSTEMIC GAP (fixed in this task)
`requestSameOriginDecoded` (`dev-app/src/lib/api.ts`) silently substituted
bundled fallback fixtures on **any** failure: network error, non-2xx, or
decode failure. Callers could not distinguish live API data from demo
data — every panel looked "healthy" while offline. `fetchPlatformOverviewStatus`
existed to report `local_offline` but was **dead code** (no consumers).

**Fix shipped**: fallback responses now emit through
`subscribeDataFallbacks()`; `DevAppShell` subscribes and `StatusBarEgress`
renders `Offline data ×N` in the status bar whenever any panel served
fallback data. Sticky count (conservative — does not clear on later
successes within the session).

### Remaining gaps (not fixed)
- `exportAuditBundle` bypasses `requestSameOriginDecoded` and has its own
  silent fallback — does not emit provenance.
- Per-panel error detail is absent by design (fallback is the UX); the
  status-bar count is the aggregate signal. Per-panel "demo data" badges
  would be the next increment.
- SSE/streaming paths are outside this mechanism.

## Verification
- `tsc --noEmit` clean; 108 vitest tests pass (106 + 2 new provenance tests).
