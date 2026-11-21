# KEEL-APP-064 — Settings Permissions deep-dive wiring (Paper 17.2)

## Status
IN_PROGRESS → pending CI/merge

## Scope
Wire `dev-app/src/components/screens/settings/SettingsPermissionsPanel.tsx` section chrome to the Paper deep-dive `17.2 — Permissions & Manifests` (node `2CG-0`), preserving all backend calls, handlers, aria-labels, disclosures, tables, and the validator.

## Changes
- Section titles normalized from `text-xs uppercase tracking-wide` to sentence-case `text-[15px] font-semibold`, matching the deep-dive header grammar established by `SettingsPanelHeader`.
- Standing-rules section header gains a quiet mono right-status `{n} scoped` (hidden while `rulesLoading` — no fabricated count).
- P-10 invariants band header becomes title + quiet right-status `immutable`, reinforcing the authority-order design (operator grants → limits → registry → validator).
- Section order, aria-labels (`Standing Allow always rules`, `Immutable P-10 governance invariants`, `Agent manifest registry and validator`), Revoke-all confirm flow, SemanticBadge `locked`/`Always ask` markers, kill-switch toggles, and JSON validator are unchanged.

## Verification
- `npx tsc --noEmit` — clean
- Targeted: `settings-and-app`, `files-record-settings`, `p10-approval-safety` — 30/30 pass
- Full suite: 24 files / 120 tests pass
- `npm run build` — clean; `core/dev_app_dist` regenerated (`index-kzFgBdij.js`, `index-l9I545Lb.css`)

## Remaining Phase-4 queue
Governance (17.3), Models (17.4), Network (17.5), light panels (17.6), then P-10/Tasks (18.1), overlays (18.3), views (18.4), drawers (18.5), billing (18.2 — tier-count decision open).
