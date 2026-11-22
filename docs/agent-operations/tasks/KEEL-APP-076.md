# KEEL-APP-076 — Paper pages 10–19 parity audit + chrome grammar fix

**Status**: READY_FOR_REVIEW
**Branch**: feature/keel-app-076-nav-leading-rule
**Paper source**: `Keelway — Brand Kit & Homepage`, pages 10–19
(Product Screens, Mock Chrome, App Interfaces, Interface Specs,
Accessibility, Iconography, Deck, Settings, Missing Surfaces,
Desktop Completeness)

## Audit result

All ten pages sampled against the live dev-app. Prior sessions had already
landed the heavy surfaces; the page-by-page verdict:

| Page | Verdict |
|---|---|
| 10.1 app-shell anatomy | **delta fixed** — active view was a filled chip; the kit says "brass leading rule, never a filled chip" |
| 10.2 records-not-git | compliant — append-only rows, `border-s-2 border-s-accent` on selected, denied stays visible, dot+word outcomes (`RecordOutcomeBadge`) |
| 11/12/13 | website + spec pages — already shipped (web-next) or documentation |
| 14 a11y | compliant — axe WCAG 2.2 AA gate in dev-app tests |
| 15 iconography | documentation (Lucide chrome icons + semantic glyphs in use) |
| 16 deck | out of product scope |
| 17 settings | compliant — verified by the earlier screenshot-parity session |
| 18.1 P-10 + run lane | compliant — card richer than the sketch (scoped rules, quorum, escalation); all four outcomes write receipts |
| 18.2 billing | compliant — usage measured from cost ledger, projections labeled, settlement ledger with signed splits |
| 18.3 onboarding + palette | compliant — verified earlier |
| 18.4/18.5 views + drawers | present — Automation/Security/Docs/PM views, review + live-execution drawers |
| 19.1 primitives | compliant — board documents dev-app components, it invents nothing |
| 19.2 agent composer | present |
| 19.3 workspace switcher + inbox | inbox compliant (three kinds, unread dot, no marketing); **gap: per-workspace attention state** — dev harness has no multi-workspace gate state to show; product-level work, flagged |
| 19.4 auth + about | compliant — About & updates is verbatim (version/channel/signature/SBOM/tape, "no trust anyway") |

## Change

Active-view navigation across the dev-app shell now uses the brass mark
with no fill, matching the settings rail that already followed the rule:

- `DevAppShell` primary glyph rail: `border-accent/50 bg-accent-subtle` →
  `border-s-2 border-s-accent` leading rule
- `PlatformWorkspaceBar` view nav: dropped the filled chip; the existing
  `kw-underline` brass underline is the active mark
- `DevAppShell` companion tabs: same — `kw-underline` + no fill
- `FilesExplorerSidebar` tree + changed-files items: `bg-accent-subtle` →
  `border-s-2 border-s-accent` leading rule

`core/dev_app_dist` rebuilt (committed bundle serves the app).

Not changed deliberately: `SemanticBadge` (status badges are a component
per the kit's own vocabulary; the dot+word rule governs ledger rows, which
already comply), segmented controls/tabs/filters (19.1's segmented
primitive), and the WS/RBAC/tier selects (dev-harness simulators, honest).

## Verification

- `npm run typecheck` — clean
- `npm test` — 126/126 green (jsdom + axe suites)
- `vite build` — dist regenerated and committed

## Follow-ups

- Full workspace-switcher dialog (⌘⇧W) with per-workspace pending-gate
  state once the runtime models multi-workspace gates.
