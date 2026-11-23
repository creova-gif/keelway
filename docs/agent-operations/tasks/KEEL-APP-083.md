# KEEL-APP-083 — Companion-mode chrome cleanup: hide desktop status bar

## Status
READY_FOR_REVIEW

## Objective
Continue the enterprise decongestion audit (KEEL-APP-082). Findings:
- Desktop status bar is already disciplined — every right-side egress element
  is conditional on real state; no slimming needed.
- Real defect found at 390px: the desktop `Workspace status bar` footer
  rendered under the companion bottom nav, duplicating chrome and cramming
  `Record · Logs · Offline · API error` text into the watch surface.
- Paper 08.1 contract: companion is "the bridge watch, not the engine room"
  — its chrome is the 4-tab nav (Approvals/Tasks/Record/Status), not the
  desktop status instrument.

## Changes
- `DevAppShell.tsx`: status-bar `<footer>` now renders only when
  `!effectiveMobileCompanion`. Desktop unchanged (F6 landmark cycle,
  aria-live announcements, egress instrument all preserved).

## Deferred deliberately
- Journey-bar relocation to sidebar: rejected — would relocate congestion
  into the nav column; it is the product's signature cross-view navigator.
- Workspace-controls cluster collapse (ws/RBAC/persona/tier): blocked by
  test contract — phase12/RBAC tests getByRole these controls directly;
  any popover/disclosure breaks reachability.

## Verification
- `npx tsc --noEmit` clean
- `npx vitest run` — 25 files, 130/130
- `npm run build` — dev_app_dist regenerated
- Playwright 390×844: companion view bottom shows only the 4-tab nav;
  desktop 1440×900 unchanged.
