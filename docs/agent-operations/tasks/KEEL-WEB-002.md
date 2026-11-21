# KEEL-WEB-002 — web-next CI coverage

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-002
- **TASK TITLE**: Add web-next to website-devapp-and-sdks CI job
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-002-ci

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] `web-next/package-lock.json` added to npm cache-dependency-path
- [x] New step: `npm --prefix web-next ci && typecheck && build` — fails CI on regression
- [x] Step placed right after the website build (same toolchain, node 22)

#### TESTS EXECUTED & EVIDENCE
- YAML diff only; the step's commands verified locally green in KEEL-WEB-001
- Full validation = this PR's own CI run (the job must build web-next itself)

#### NEXT RECOMMENDED ACTION
- Port Paper screens into web-next, or add a web-next Playwright a11y pass mirroring website's e2e.
