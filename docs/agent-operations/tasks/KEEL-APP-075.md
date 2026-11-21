# KEEL-APP-075 — Accent token rename: canonical --accent + Tailwind scale migration

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-075
- **TASK TITLE**: Retire the misleading teal-* token names — canonical --accent everywhere
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: refactor/keel-app-075-accent-rename

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] --accent / --accent-subtle / --accent-ink canonical in tokens.css (dark #c9a45c, light #a8854a) — the documented tokens.json resolution
- [x] --teal-* and --attn-ochre-* survive only as CSS-var aliases (var(--accent*)) — zero visual delta
- [x] Tailwind teal scale removed; canonical accent scale added; ochre scale kept as alias
- [x] All ~245 call sites migrated (teal-accent→accent, teal-surface→accent-subtle, teal-ink→accent-ink) incl. border-s-*, outline-*, accent-*, opacity modifiers
- [x] TOKENS.md + tokens.json marked RESOLVED; pure rename, no value changes

#### WORK COMPLETED & FILES MODIFIED
- dev-app/src/styles/tokens.css: canonical --accent* in both themes + alias block
- dev-app/tailwind.config.ts: teal scale → accent scale
- 50 src files: class-name migration via sed sweep
- docs/design/tokens.json, docs/design/TOKENS.md: debt marked resolved
- core/dev_app_dist/: rebuilt

#### TESTS EXECUTED & EVIDENCE
- npx tsc --noEmit: clean
- npx vitest run: 126 passed (24 files), incl. axe gates
- npm run build: clean, dist regenerated; built CSS verified to emit --accent canonical + aliases

#### KNOWN RISKS & BLOCKERS
- Alias vars remain intentionally for external consumers; removal is a future hard cut.

#### NEXT RECOMMENDED ACTION
- Remaining deferred: web-next scaffold (paused per user).
