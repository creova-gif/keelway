# KEEL-APP-063 — Settings panel header grammar (Phase 4, increment 2)

## Status
`READY_FOR_REVIEW`

## Branch
`feature/keel-app-063-settings-panel-header`

## Objective
Normalize all eight Settings panel headers to the Paper 17.1 grammar via a shared
`SettingsPanelHeader` component: sentence-case 17px/600 title, 13px purpose line,
hairline bottom border, optional quiet right-side mono 11px `--dim` status.

## Source of truth
Paper `get_jsx` on `2AQ-0` (header row: `borderBottom var(--rule)`, `paddingBottom
16px`, title Inter 17px w600, purpose 13px `--muted`, status mono 11px `--dim`).

## Changes
- NEW `dev-app/src/components/screens/settings/SettingsPanelHeader.tsx` —
  shared grammar component (`title`, `purpose`, optional `status`)
- `SettingsPermissionsPanel.tsx` — header → component; status = `N manifests`
  (only when loaded, honest count)
- `SettingsModelsPanel.tsx` — header → component; status = `N local weights`
- `SettingsGovernancePanel.tsx` — header → component; status = `SQLite WAL`
  read live from `persistence.journalMode`
- `SettingsSystemPanels.tsx` — Network / Appearance / Labs / General /
  Keyboard headers → component; Network status = `Air-Gap locked` /
  `Egress measured` from the real `airGapEnabled` prop
- All prior h2/purpose copy preserved verbatim; no props/API/ARIA changes

## Tests / evidence
- `npx tsc --noEmit`: clean
- `npx vitest run`: 24 files, 120 passed (axe gates incl.)
- `npm run build`: green; `core/dev_app_dist` rebuilt
