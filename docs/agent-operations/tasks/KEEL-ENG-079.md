# KEEL-ENG-079 — StatCard shared primitive (UX-003 step 2)

## Status: IN_REVIEW

`components/ui/StatCard.tsx` — second composite primitive per the
component-inventory consolidation order (EmptyState → StatCard → FilterBar).
Props: `label`, `value`, optional `delta`, `emphasis` (accent value tone),
`framed` (bordered canvas chrome — `false` for cells inside an
already-framed `<dl>`). Emits `<dt>`/`<dd>` inside the cell `<div>` so a
`<dl>` grid stays valid; delta renders inside the `<dd>` (axe
`definition-list` requires the grouping div to contain only dt/dd).
`unicode-bidi-isolate` + `dir="ltr"` on the mono value per call-site
convention.

## Sites converted (true stat cards only)

- `QuotaAndPricingSimulatorPanel.tsx` — 4-cell KPI grid; compound
  `label: value, delta` strings restructured into label/value/delta; grid
  is now a `<dl>` (was `<div>`).
- `SettingsModelsPanel.tsx` — 6-cell explainability grid;
  `framed={false}` (border lives on the outer `<dl>`).
- `SettingsBillingPanel.tsx` — 3-cell settlement ledger `<dl>`.

Deliberately NOT converted (inline definition rows, not cards):
`P10ApprovalCard`, `RecordEntryInspector`, `SettingsPermissionsPanel`,
`SettingsSystemPanels`.

## Evidence

- `npx tsc --noEmit`: clean
- `npx vitest run`: 133/133 pass (25 files); StatCard block added to
  `tokens-and-badges.test.tsx` incl. `runAxe` on the dl structure;
  pricing-simulator assertions rewritten from compound strings to
  label/value/delta queries
- `COMPONENT_INVENTORY.md` StatCard row → SHARED; audit UX-003 note +
  stale axe-coverage backlog row corrected (only the two logic-only test
  files lack axe); board WEB-056 duplicate row removed

## Non-goals

- FilterBar (UX-003 step 3) — next opportunistic primitive.
