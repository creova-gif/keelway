# KEEL-APP-062 — Settings shell wired to Paper anatomy (Phase 4, increment 1)

## Status
`READY_FOR_REVIEW`

## Branch
`feature/keel-app-062-settings-shell-anatomy`

## Objective
First Phase-4 wiring unit: apply Paper artboard `17.1 — Settings anatomy & IA`
(`2AQ-0`) measurements to the Settings shell (`SettingsWorkspace.tsx`) while
preserving all backend wiring, props, ARIA contracts, and security behavior.

## Source of truth
Paper `get_jsx` output on `2AQ-0` — measured values, not screenshot estimates:
- Rail: `--surface` bg, `--rule` right border, `paddingBlock 20px`
- Rail header: mono 11px, `letter-spacing .14em`, `--dim`, `paddingInline 20px`, `paddingBottom 14px`
- Rail item: `paddingBlock 7px`, `paddingInline 20px`, sans 13px, `--muted`
- Active item: 2px `--accent` leading rule + `--ink` text — **no fill** (padding-left 18px)
- Content: `paddingBlock 28px`, `paddingInline 32px`, full width (no max-w constraint)
- Drift count: quiet mono count (right-side quiet status grammar)

## Changes
- `dev-app/src/components/screens/SettingsWorkspace.tsx`
  - `SettingsSubNav`: rail padding/header/item typography + spacing per artboard;
    active = accent leading rule, `bg-teal-surface` fill removed; drifted-rule
    count rendered as quiet `font-mono text-[11px] text-ochre` text (was
    `SemanticBadge` pill — `SemanticBadge` import dropped)
  - aside: `bg-chrome` → `bg-surface` (Paper rail surface token)
  - content column: `p-5` → `px-8 py-7`; `mx-auto max-w-4xl` removed (Paper
    content column fills the panel)
  - `aria-current="page"` on the active item preserved; all props/api wiring
    untouched

## Tests / evidence
- `npx tsc --noEmit`: clean
- `npx vitest run`: 24 files, 120 passed — incl. axe WCAG 2.2 AA gates and the
  `Settings sections` nav role assertions
- `npm run build`: green; `core/dev_app_dist` rebuilt

## Remaining Phase-4 increments
- Panel header grammar (title + purpose + quiet right status) per 17.1
- Per-panel wiring against 17.2–17.6 deep-dives
- Then P-10/Tasks (18.1), overlays (18.3), views (18.4), drawers (18.5),
  billing (18.2 — pending tier-count decision)
