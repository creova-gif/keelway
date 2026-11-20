# KEEL-APP-055 — Workspace-bar control cluster & Governance panel decongestion

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-055
- **TASK TITLE**: Control-cluster consolidation + Governance card-in-card de-chroming
- **CURRENT STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2026-06-29
- **BRANCH**: feature/keel-app-055-control-cluster-decongestion
- **HEAD COMMIT**: see PR #118

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Workspace-bar right cluster: 4 bordered control boxes (WS / RBAC / persona / Tier) merged into ONE bordered container with `│` separators — all aria-labels and the `Experience persona` role=group preserved (verified: phase5 + unified-10view tests unchanged & green)
- [x] `+ New` workspace trigger de-chromed to quiet teal text button (aria-label + `aria-expanded` intact)
- [x] Governance persistence strip: `SemanticBadge` pill → `● SQLite WAL Crash-Safe` / `● Ephemeral memory · not WAL` dot + text (exact strings kept for contract test)
- [x] Nested card-in-card chrome removed: DLP checkbox, OpenCore fallback checkbox, and SBOM row lose inner bordered boxes; SBOM separated by a single `border-t` divider
- [x] Scope chips de-chromed: `border` removed → borderless `bg-code` muted tokens
- [x] Secondary verify-key form collapsed behind `<details>` "Verify a scoped key…" disclosure (input label preserved for the labelled-input contract)
- [x] Verify result badge → dot + text (`● Key valid` / `● Key rejected`)
- [x] Zero a11y regressions: axe WCAG 2.2 AA green; all role/label queries unchanged
- [x] No backend/behavior changes — presentational only (verified)

#### WORK COMPLETED & FILES MODIFIED
- `dev-app/src/components/platform/PlatformWorkspaceBar.tsx`: single shared control container, internal separator spans (`aria-hidden`), borderless `+ New`, persona buttons de-boxed
- `dev-app/src/components/screens/settings/SettingsGovernancePanel.tsx`: dot-status persistence strip, unboxed checkbox rows, border-t SBOM divider, borderless scope chips, `<details>` verify disclosure, dot-status verify result, dead `SemanticBadge` import removed
- `core/dev_app_dist/`: production bundle rebuilt

#### TESTS EXECUTED & EVIDENCE
- `npx vitest run src/__tests__/settings-and-app.test.tsx unified-10view-platform.test.tsx phase5-runtime-vault-rbac.test.tsx`: 24 passed (1 initial failure from a renamed label — fixed by restoring the contract label text; disclosure summary carries the new affordance)
- `npx vitest run` (full suite): 24 files, 119 passed — axe AA included
- `npx tsc --noEmit`: clean; `npm run build`: green
- Live screenshots on isolated `/app` stack: consolidated control cluster + de-chromed Governance panel verified

#### KNOWN RISKS & BLOCKERS
- None.

#### NEXT RECOMMENDED ACTION
- Decongestion program is effectively complete across shell + content. Optional remaining surfaces: Records/Files in-card metadata, onboarding modal density.
