### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-058
- **TASK TITLE**: Maritime Instrument v3 Motion Layer — Shared Tokens, Interactive Figure, Dev-App Choreography
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-app-058-maritime-motion
- **HEAD COMMIT**: (pending)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Shared motion tokens (80/140/220/380ms + settle/state/release easings) in both `dev-app/src/styles/tokens.css` and `website/src/app/globals.css` — Paper kit page 07 codified
- [x] Choreography classes: `kw-land` (seal/toast settle), `kw-fade-in`/`kw-fade-fast` (modal fade, never scale), `kw-seal-ring` (single 380ms binnacle pulse), `kw-underline` (brass route/tab underline slide), `kw-draw` (draw-on once), `kw-skeleton` (static, never shimmer)
- [x] Homepage `ControlPlaneFigure` gate panel is a live demo: Allow once / Deny / ↺ replay transition chip, step, receipt, and tape-number states in place; denials seal like approvals. A11y: `role="group"` + `aria-live` receipts; buttons real `<button>`s; decorative rails stay `aria-hidden`
- [x] Site nav uses sliding brass underline (`data-active`/`aria-current` on Header links); ad-hoc durations (150/120/500ms) normalized to tokens
- [x] Dev-app wired: tailwind `duration-{snap,fast,base,slow}` + `ease-{settle,state,release}` utilities; palette/drawer entrance fades; all bare `transition-colors`/`transition-all` swept to tokens (16 files)
- [x] `prefers-reduced-motion` / `data-reduce-motion` guards collapse every duration; state still lands
- [x] DESIGN.md §9 documents the codified layer

#### WORK COMPLETED & FILES MODIFIED
- `dev-app/src/styles/tokens.css`: motion tokens + 6 choreography utilities/keyframes
- `dev-app/tailwind.config.ts`: `transitionDuration`/`transitionTimingFunction` token maps
- `dev-app/src/components/ui/Button.tsx`, `shell/DevAppShell.tsx`, `shell/CommandPalette.tsx`, `platform/*` (8), `screens/*` (6): token-duration sweep + palette/drawer fades + view-nav `kw-underline`
- `website/src/app/globals.css`: motion tokens, duration normalization, navlink underline, fig-btn/chip/state-wash/land/seal-ring styles
- `website/src/components/site/ControlPlaneFigure.tsx`: interactive gate demo (Allow/Deny/replay)
- `website/src/components/layout/Header.tsx`: `data-active` + `aria-current` nav state
- `DESIGN.md`: §9 motion spec

#### TESTS EXECUTED & EVIDENCE
- `npx tsc --noEmit` (dev-app): clean
- `npx vitest run` (dev-app): 24 files, 119 passed (incl. axe WCAG suites)
- `npm run build` (website): all 15 routes compile

#### KNOWN RISKS & BLOCKERS
- Sweep is token-level (150ms→140ms etc.); no layout/behavior change expected. Playwright a11y suite not run locally (requires server); CI covers it.

#### NEXT RECOMMENDED ACTION
- CI + merge; then consider `Reveal.tsx` doc-drift (DESIGN.md §6 mentions it; current site uses `kw-rise` classes instead — either implement or trim the §6 reference)
