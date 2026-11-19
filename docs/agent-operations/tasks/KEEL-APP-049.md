# KEEL-APP-049 — Agents View: Kill-Switch Toggle UI + Registry Refetch

- **STATUS**: VERIFIED_COMPLETE
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-app-049-registry-killswitch-ui`
- **SCOPE**: `dev-app/` frontend (mutation path on top of KEEL-APP-048's read overlay)

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] `postAgentRegistryToggle(name, version, enabled)` client for `POST /v1/agents/registry/{name}/{version}/toggle` with `{enabled}` body + `decodeRegistryToggle` decoder; returns `null` on failure/offline.
- [x] `refreshAgentRegistry` extracted in `useUnifiedPlatformState`; mount effect reuses it; `handleToggleRegistryEntry` posts then refetches so badges/header reflect the DB truth without a page reload.
- [x] Per-card `Disable`/`Enable agent manifest <name>` control rendered only for agents with a real registry record (`reg` non-null) and only when `onToggleRegistryEntry` is provided — unregistered/custom agents and unavailable-registry states get no control.
- [x] RBAC gate matching the backend (`APPROVE_TIER3` = owner/admin): control is `aria-disabled` for builder/operator/viewer; `clickOnly` requires a trusted user event (consistent with P-10 controls).
- [x] Per-card pending state (`Working…`, button disabled) while the POST+refetch is in flight.
- [x] Live-verified on an isolated stack, full round-trip through the real UI:
  - Trusted CDP click `Disable agent manifest devops-sre` → header `12 manifests registered · 11 enabled`, card `Disabled`, button flips to `Enable agent manifest devops-sre`; `keelway_agent_manifests.enabled = 0` in `keelway.db`.
  - Trusted click `Enable agent manifest devops-sre` → header back to `12 enabled`, card `Live · digest …`, button back to `Disable`, DB `enabled = 1`.

## FILES MODIFIED

- `dev-app/src/lib/apiDecoders.ts` — `decodeRegistryToggle`.
- `dev-app/src/lib/api.ts` — `postAgentRegistryToggle`.
- `dev-app/src/components/platform/useUnifiedPlatformState.tsx` — `refreshAgentRegistry`, `handleToggleRegistryEntry`, wired to view.
- `dev-app/src/components/platform/AgentsWorkspaceView.tsx` — `onToggleRegistryEntry` prop, pending state, `canToggleRegistry` gate, hoisted `reg` lookup, toggle control beside Inspect & Supervise.
- `dev-app/src/__tests__/tokens-and-badges.test.tsx` — overlay + kill-switch test (enabled/disabled/unregistered badges, admin fires toggle, viewer locked, unavailable-registry renders no controls).
- `core/dev_app_dist` — rebuilt bundle.

## TESTS & EVIDENCE

- `npx vitest run` — 113/113 (incl. axe gate), `npx tsc --noEmit` clean, Vite build clean.
- `/tmp/keelway-evidence-reg/toggle-after.aria.txt` — post-disable ARIA (`11 enabled`, `Disabled` badge, `Enable` button).
- `/tmp/keelway-evidence-reg/toggle-final.aria.txt` + `.png` — post-reenable ARIA/screenshot (`12 enabled`, `Live · digest d13bd2a9`).
- SQLite readback: `SELECT name, enabled FROM keelway_agent_manifests WHERE name='devops-sre'` → `0` after disable, `1` after re-enable.

## HONEST LIMITS

- Toggle is a governance mutation, not an agent-run action — it does not require P-10; the backend audits each call (`manifest_enabled` / `manifest_disabled_kill_switch`) and enforces `APPROVE_TIER3` server-side regardless of the frontend gate.
- No optimistic update — the UI waits for the POST then refetches, so displayed state is always the server's truth.
