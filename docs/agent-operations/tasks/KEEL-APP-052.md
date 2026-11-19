# KEEL-APP-052 — Shell Decongestion: Badge Budget + Breadcrumb Journey + Collapsible Rail

- **STATUS**: VERIFIED_COMPLETE
- **DATE**: 2026-11-21
- **BRANCH**: `feature/keel-app-052-shell-decongestion`
- **SCOPE**: `dev-app/` shell chrome (shared across all 10 views)

## OBJECTIVE & ACCEPTANCE CRITERIA

User-reported congestion ("a lot of things going on — arrangement, congestion of tools, accessibility"). Benchmarked against enterprise AI-tool surfaces (Linear, Vercel, Cursor, Datadog): one quiet chrome band, status as dot+text not bordered pills, progressive disclosure.

- [x] **Golden Thread stepper de-chromed.** `GoldenThreadJourneyBar`: 4 bordered pill buttons + boxed "Next in Golden Thread" CTA → quiet mono text breadcrumb (`✓/NN Stage → …`) + plain-text advance link. Identical ARIA contract preserved: `role="region"`, `aria-current="step"`, per-stage `aria-label`, `aria-label="Advance golden thread stage"` — phase12 tests pass unchanged.
- [x] **Workspace bar marketing text removed.** "Zero Context Loss" slogan dropped from the context breadcrumb pill; functional identity (path/branch/model/P-10 count) retained. `EXAMPLE DATA` honesty badge and `N P-10 pending` actionable badge kept.
- [x] **Badge budget on Agents rail.** Per-row `SemanticBadge` ("Ready" chip ×12) → silent default: `ready` renders nothing; non-default states render a status dot + label (ochre/running/dim/danger). Header shows `N need attention · M registered`.
- [x] **Agents rail collapsible.** Section header is a button with `aria-expanded`, chevron, and count — collapses to reclaim rail space for the task queue.
- [x] Accessibility held: `focus-visible` outlines, `aria-expanded`, `aria-current`, region labels; axe suites still 0 violations.

## FILES MODIFIED

- `dev-app/src/components/platform/GoldenThreadJourneyBar.tsx` — breadcrumb render (pills → text).
- `dev-app/src/components/platform/PlatformWorkspaceBar.tsx` — removed "Zero Context Loss" span.
- `dev-app/src/components/shell/DevAppShell.tsx` — `AGENT_STATUS_DOT` map, collapsible + de-badged `AgentsRailList`.
- `dev-app/src/__tests__/unified-10view-platform.test.tsx` — assertion swapped from marketing text to `1 P-10 pending`.
- `core/dev_app_dist` — rebuilt bundle.

## TESTS & EVIDENCE

- `npx vitest run` — **119/119** across 24 files incl. all axe WCAG 2.2 AA gates (0 violations), `npx tsc --noEmit` clean, Vite build clean.
- Live-stack screenshots before/after: journey bar pills → text breadcrumb; agents rail chips → quiet rows with attention count.

## FOLLOW-UPS (not in scope)

- Progressive disclosure inside Permission/Manifest table cells (HMAC/kill-switch behind expandable rows).
- Possible merge of RBAC/Tier selectors into a single workspace-menu in a later pass.
