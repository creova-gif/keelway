# KEEL-WEB-004 — Website token unification: --brass → --accent

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-004
- **TASK TITLE**: Rename website --brass* tokens to canonical --accent*
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-004-website-accent

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] All `--brass*` CSS vars renamed to `--accent*` in website globals.css (--accent, --accent-deep, --accent-ink, --accent-8, --accent-40, --accent-ring)
- [x] All call sites migrated: var(--brass*) → var(--accent*), kw-label-brass → kw-label-accent, kw-chip-brass → kw-chip-accent, pricing tier flag brass → accent, ControlPlaneFigure tone union "brass" → "accent"
- [x] Only prose mentions of the brass color remain (figure caption "P-10 gate in brass" describes the color, not the token)
- [x] All three surfaces now name the canonical accent identically: dev-app --accent (canonical), web-next generated copy, website --accent
- [x] typecheck + next build green; tokens.json/TOKENS.md updated

#### TESTS EXECUTED & EVIDENCE
- npm run typecheck: clean; npm run build: green (all routes prerender)
- Zero remaining brass token/class refs outside prose

#### NEXT RECOMMENDED ACTION
- web-next screens or Playwright a11y e2e.
