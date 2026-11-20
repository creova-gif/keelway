# KEEL-APP-053 — Permissions & Manifests content decongestion

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-053
- **TASK TITLE**: Permissions & Agent Manifests progressive-disclosure pass (content-level decongestion)
- **CURRENT STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2026-06-29
- **BRANCH**: feature/keel-app-053-permissions-decongestion
- **HEAD COMMIT**: see PR #116

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Manifest registry default row shows only decision-critical info: agent id, description, signature state, autonomy, kill-switch (verified via screenshot + tests)
- [x] Constant `Schema` column removed — `keelway.agent/v1` rendered once per row as muted microtext in the agent cell (kept in DOM for contract test)
- [x] Bordered `SemanticBadge` pills replaced by dot + text status: signature (● Verified / ● Unsigned / ● Invalid), network (● network allowed vs `· offline`), Tier as plain text (verified)
- [x] Verbose security warnings collapsed behind a `<details>` disclosure with a visible `N warnings` summary — signal retained, chrome removed (verified)
- [x] Kill-switch button unchanged: accessible name `Kill-switch for <name>@<version>: <state>`, `aria-pressed`, RBAC-gated, real `POST /v1/agents/registry/{name}/{version}/toggle` (verified by existing test)
- [x] Zero accessibility regressions: axe WCAG 2.2 AA passes in the settings test and the App-level a11y suite (verified — 12/12 settings tests, 119/119 suite)
- [x] No backend/behavior changes — presentational-only restructure of `SettingsPermissionsPanel.tsx` (verified)

#### WORK COMPLETED & FILES MODIFIED
- `dev-app/src/components/screens/settings/SettingsPermissionsPanel.tsx`:
  - `renderSignatureBadge` → `renderSignatureStatus` (dot + text, no bordered pill)
  - Manifest table: 5 columns → 4 (`Agent | Signature | Autonomy | Kill-Switch`); `colSpan` updated for loading/empty rows
  - Schema version moved to muted 10px mono microtext under the description
  - Security warnings wrapped in `<details>`/`<summary>` disclosure with count summary
  - Autonomy cell de-chromed: `Tier N` plain mono text, `· offline` dim suffix, `● network allowed` warning dot + text
- `core/dev_app_dist/`: production bundle rebuilt (`npm run build`)

#### TESTS EXECUTED & EVIDENCE
- `npx vitest run src/__tests__/settings-and-app.test.tsx`: 12 passed
- `npx vitest run` (full dev-app suite): 24 files, 119 passed — includes axe WCAG 2.2 AA
- `npx tsc --noEmit`: clean
- `npm run build`: green (pre-existing font-path + chunk-size warnings only)
- Live screenshot on isolated stack `/app` → Settings → Permissions & Manifests: compact 4-column table, disclosure summary visible, kill-switch immediate

#### KNOWN RISKS & BLOCKERS
- None. Warnings remain in the DOM (a11y-discoverable via disclosure summary); the `keelway.agent/v1` contract string remains present for the parity-style test assertion.

#### NEXT RECOMMENDED ACTION
- Same disclosure pattern is a candidate for the RBAC/Tier control cluster in `PlatformWorkspaceBar` and for in-card metadata in `SettingsGovernancePanel`, if the owner wants another pass.
