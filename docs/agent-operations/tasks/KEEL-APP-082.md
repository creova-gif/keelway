# KEEL-APP-082 — Shell decongestion: VIEWS to sidebar, chrome collapse

## Status
READY_FOR_REVIEW

## Objective
User audit: "UI/UX was too congested, everything everywhere, not enterprise grade."
Root cause identified via live screenshots: three stacked chrome bars
(masthead + workspace-controls + golden-thread/view-nav row) plus a 9-item
horizontal view nav before any content — identical on all 10 views.

## Changes
- `PlatformWorkspaceBar.tsx`: removed the 9-item horizontal view nav from row 2
  (golden-thread journey bar remains — it is a functional cross-view navigator
  exercised by phase12 tests across Product/Automation/Agents/Security).
  Exported `PLATFORM_VIEWS` for reuse.
- NEW `PlatformViewList.tsx`: vertical VIEWS nav for the left sidebar —
  Paper 12.1 grammar (leading brass rule on active view, never filled chips),
  `aria-label="Unified platform views"` preserved for test/AT contract.
- `DevAppShell.tsx`: new `viewNavContent` slot rendered inside the sidebar
  `aside` ABOVE context content. Sidebar visibility split into
  `shouldRenderViewNav` (companion/hideSidebar) vs `shouldRenderSidebar`
  (+ record section) so the global VIEWS nav persists on Record/Security
  views where the contextual sidebar is intentionally hidden. Agents rail
  roster now collapsed by default (disclosure retained; "N need attention"
  summary still visible).
- `App.tsx`: passes `viewNavContent={<PlatformViewList ... />}`.

## Decisions
- Golden-thread journey bar stays global: phase12 tests treat it as the
  canonical cross-view navigator ("illuminates active stages across views").
- VIEWS nav lives in sidebar for all desktop sections (Paper 12.1 shows
  VIEWS in the left rail); suppressed on mobile companion.

## Regression fixed mid-flight
First version mounted view nav inside `shouldRenderSidebar` — nav unmounted
on record/Security views (stale-node clicks silently no-op'd). Nav now
independent of the contextual sidebar condition.

## Verification
- `npx tsc --noEmit` clean
- `npx vitest run` — 24 files, 126/126 passing
- `npm run build` — dev_app_dist regenerated
- Playwright screenshots (1440×900): Tasks view now shows one masthead +
  one journey bar + sidebar VIEWS + collapsed agents roster; Security view
  keeps nav visible with correct aria-current.
