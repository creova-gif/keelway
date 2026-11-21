# KEEL-WEB-003 — Shared tokens: canonical copy + freshness gate

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-003
- **TASK TITLE**: Eliminate dev-app/web-next token drift — generated copy + make tokens-check in CI
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-003-shared-tokens

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] web-next/src/styles/tokens.css is a GENERATED copy of dev-app/src/styles/tokens.css (canonical) — follows the studio-css pattern, no workspace package needed
- [x] make tokens-sync regenerates; make tokens-check fails on drift (verified: appended byte → STALE exit 1)
- [x] web-next tailwind config remapped to canonical --bg-* var names; globals.css updated
- [x] tokens-check wired into website-devapp-and-sdks CI step
- [x] typecheck + next build green on generated tokens

#### KNOWN RISKS & BLOCKERS
- website/ keeps its own --brass naming (documented alias); a three-way share needs a real package — out of scope for this increment.

#### NEXT RECOMMENDED ACTION
- Port Paper screens into web-next; consider extracting packages/tokens if a third consumer lands.
