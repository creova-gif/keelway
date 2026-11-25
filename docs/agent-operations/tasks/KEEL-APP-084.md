# KEEL-APP-084 — Masthead decongestion: Workspace & access popover

## Status
READY_FOR_REVIEW

## Objective
Continue the enterprise decongestion program (KEEL-APP-082 → 083). The
masthead's right cluster carried 8 competing items: persona toggle, `+ New`
workspace button, create-workspace form, RBAC select, tier select + price,
Inbox, and the conditional No-Code CTA. Secondary workspace configuration
belonged behind a single disclosure — Paper "Maritime Instrument" grammar:
chrome shows state, menus hold configuration.

## What changed (`dev-app/src/components/platform/PlatformWorkspaceBar.tsx`)

**Kept visible in masthead** (primary, per-view controls):
- Workspace switcher — moved into the left identity cluster next to
  BrandMark / path / branch / model (Paper 12.1's identity grammar)
- Compact `owner ▾` RBAC select — a live governance control exercised by
  7 test files; stays a real `<select>`
- Inbox popover trigger
- Conditional "Open No-Code Builder" CTA

**Collapsed into new `Workspace` menu popover** (mirrors `InboxPopover`:
`useId` panel id, outside-mousedown + Escape close, `aria-haspopup="dialog"`,
`aria-label="Workspace & access"`):
- `PERSONA` — Builder / Guided Non-Coder toggle
- `TIER` — select + price label
- `+ New workspace` — expands the existing create form inside the panel

## Token defects found via screenshot verification
- `bg-surface` = `rgba(255,255,255,0.04)` — a 4% wash, not an opaque panel.
  In dark theme the popover bled page content through. Panel now uses
  `bg-chrome` (opaque `#0a0b0d` dark / `#f4f4f5` light). Same fix applied to
  `InboxPopover`, which had the identical latent defect.
- `w-72` is not in the custom token scale (panel rendered 234px); corrected
  to `w-80`, matching `InboxPopover`.
- Workspace-select option text shortened from `${id} · ${name}` to `name`
  only — the id is the option value; tests select by value (`hipaa-intake`),
  not by label.
- Price label given `shrink-0` so `$29 / seat / mo` stays on one line.

## Test contract preserved
- `/Active RBAC role/` select — untouched semantics.
- `/Active workspace switcher/` — still a real select in the masthead.
- `/Experience persona/` group moved inside the popover; the two test sites
  that use it now open the menu first (one-line change each):
  `phase12-golden-thread-studio.test.tsx`, `unified-10view-platform.test.tsx`.
- Tier select and `+ New` are untested; accessible names kept.

## Verification
- `npx tsc --noEmit`: clean
- `npx vitest run`: 130/130 across 25 files
- `npm run build`: dist regenerated (`index-DGkrYiLn.js`)
- Playwright @1440×900 (`/tmp/app084-closed.png`, `/tmp/app084-menu.png`):
  masthead renders as one line; popover is opaque, right-anchored, and
  contains all three sections.

## Remaining decongestion backlog
- View-level congestion audit: IDE/Tasks, Agents, Security, Operations
  sub-chrome.
- Record vs Paper 10.2 "Compare detail" — last open compare row.
