# KEEL-ENG-080 — FilterBar primitives (UX-003 step 3, closes UX-003)

## Status: IN_REVIEW

`components/ui/FilterBar.tsx` — third and final composite primitive per the
component-inventory consolidation order (EmptyState → StatCard → FilterBar).
Four exports:

- `FilterBar` — filter-strip `<section>` (`flex flex-wrap items-end gap-2.5`,
  `aria-label` passthrough).
- `SearchField` — `type="search"` input with `htmlFor` + `useId` label
  association; `sr-only` label by default, `labelClassName` for the visible
  variant; canonical control chrome. Width belongs on the wrapping label
  (`className`), input stays `w-full`.
- `FilterChips` — `role="group"` + `aria-pressed` single-select toggle chips
  (accent active / muted surface inactive).
- `FilterSelect` — labeled enum `<select>`, lifted verbatim from
  `RecordAuditLedger`'s local component.

## Sites converted

- `RecordAuditLedger.tsx` — filter strip + labelled search + 6 `FilterSelect`s
  + clear/count slot; local `FilterSelect`/`searchId` removed.
- `MarketplaceAndDocsViews.tsx` — search + publisher-tier and category chip
  groups (both `role="group"`/`aria-pressed` patterns deduplicated).
- `AgentsWorkspaceView.tsx` — header-row agent filter (`w-64` on the label).
- `DocumentationWorkspaceView.tsx` — knowledge-base search.
- `FilesExplorerSidebar.tsx` — symbol filter (stable `symbolFilterId` kept).

Deliberately NOT converted: `KBrainMemoryGraphPanel` search — it is a
form-submit server query with a submit button, not a client filter strip.

Normalizations accepted: `rounded-xs`/`bg-canvas`/`px-2` input variants fold
to the canonical `rounded-sm`/`bg-surface`/`px-2.5` + `placeholder:text-fg-dim`
chrome; Marketplace strip `gap-3`/`items-center` → `gap-2.5`/`items-end`.

## Evidence

- `npx tsc --noEmit`: clean
- `npx vitest run`: 135/135 pass (25 files); FilterBar block added to
  `tokens-and-badges.test.tsx` incl. `runAxe` on the composed strip
- `COMPONENT_INVENTORY.md` FilterBar row → SHARED + consolidation order
  complete; audit UX-003 → FIXED, rolling backlog row closed

## Non-goals

- Sortable-table header component (only one table view sorts today).
