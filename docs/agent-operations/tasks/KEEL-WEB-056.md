# KEEL-WEB-056 — CWV smoke spec for web-next

## Status: COMPLETED

`web-next/e2e/cwv.spec.ts` — 2 tests on the existing Playwright harness
(zero new deps): home-page LCP/CLS/JS-payload budgets via a
`PerformanceObserver` installed with `addInitScript` (LCP + layout-shift
are observer-only entry types), plus first-contentful-paint on `/`,
`/pricing`, `/product`. Thresholds documented as local-server tripwires
(6s LCP / 0.25 CLS / 1.5MB JS), not field CWV — the point is catching
regressions in CI, not asserting lab vitals.

## Evidence
- `npx playwright test e2e/cwv.spec.ts`: 2/2 pass
- `npx playwright test` full suite: 33/33 pass
- Closes audit UX-006's CWV-harness gap for the marketing surface.
