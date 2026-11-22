# KEEL-WEB-005 — web-next Playwright a11y + perf e2e

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-005
- **TASK TITLE**: web-next axe-core WCAG 2.2 AA + perf smoke e2e, wired into CI
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-005-web-next-e2e

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] @playwright/test + @axe-core/playwright deps, playwright.config.ts (port 3001), e2e/a11y.spec.ts mirroring website's gate
- [x] WCAG 2.1/2.2 AA axe pass on `/` + perf smoke (DCL <5s, load <8s, transfer <4MB)
- [x] Real a11y defect found and fixed on first run: fg-dim (#5d6268, ~3:1) labels → fg-muted
- [x] test:e2e step in website-devapp-and-sdks CI; artifacts gitignored

#### TESTS EXECUTED & EVIDENCE
- npm run test:e2e: 2 passed (axe WCAG AA + perf smoke), post-build
- CI: self-validating — new step runs in this PR's own job

#### NEXT RECOMMENDED ACTION
- web-next screens from Paper inventory.
