# KEEL-APP-065 — Settings section-title grammar (deep-dives 17.3–17.6)

## Status
IN_PROGRESS → pending CI/merge

## Scope
Completes the section-header grammar normalization started in KEEL-APP-064 across the remaining Settings panels: Governance & Keys (17.3 / `2EL-0`), Models & 4D Routing (17.4), Network & Egress (17.5), and the light panels in `SettingsSystemPanels.tsx` (17.6).

## Changes
- `SettingsGovernancePanel.tsx`: 3 section h3s (Data Residency & DLP, USD Spend Caps, Scoped Tenant API Keys) normalized `text-xs uppercase tracking-wide` → `text-[15px] font-semibold` sentence case; scoped-keys header gains quiet mono `{n} keys` count beside the mint button.
- `SettingsModelsPanel.tsx`: 3 section h3s normalized identically.
- `SettingsSystemPanels.tsx`: 3 section h3s (Network posture, Color Theme, General) normalized identically.
- Field-label `text-[10px] uppercase` micro-labels in Permissions intentionally preserved (form grammar, not section grammar).
- Zero prop/handler/aria/backend changes.

## Verification
- `npx tsc --noEmit` — clean
- Full suite: 24 files / 120 tests pass
- `npm run build` — clean; `core/dev_app_dist` regenerated (`index-B5WzCcK1.js`)

## Note
With this + APP-062/063/064 merged, all 8 Settings panels match the Paper 17.x grammar: shared panel header, sentence-case section titles, quiet right-statuses, hairline rows. Remaining Phase-4: P-10/Tasks (18.1), overlays (18.3), views (18.4), drawers (18.5), billing (18.2 — tier decision open).
