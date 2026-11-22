# KEEL-WEB-008 — web-next /product + /changelog

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-008
- **TASK TITLE**: /product (instruments + PolicyDemo) and /changelog ports on web-next
- **CURRENT STATUS**: MERGED (PR #191)
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-008-product-changelog

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] /product — three instrument cards + interactive PolicyDemo (checkboxes → rule verdict, aria-live, status chips on canonical tokens)
- [x] /changelog — RELEASES data ported verbatim from website/src/data/releases.ts
- [x] Header NAV + footer nav updated; both routes added to e2e ROUTES
- [x] typecheck + build green; 6/6 e2e pass first try (incl. interactive demo)
- [ ] DEFERRED: FigureTabs/ControlPlaneFigure (252-line SVG vocabulary) — dedicated port task

#### NEXT RECOMMENDED ACTION
- Port FigureTabs/ControlPlaneFigure for full /product parity, or /about + /sign-in + /contact to finish website parity.
