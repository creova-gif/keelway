# KEEL-REL-055 — Website Accessibility & Performance CI

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / WEBSITE / A11Y / CI` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-REL-055-website-a11y-ci` |

## Objective
Release gap: no accessibility or performance gate on the public website (dev-app already had axe-core in vitest).

## Implementation
- `website/playwright.config.ts` + `website/e2e/a11y.spec.ts`: axe-core WCAG 2.2 AA scan (`wcag2a/2aa/21a/21aa/22aa`) across all 8 routes + homepage perf smoke (DCL <5s, load <8s, transfer <4MB — localhost budgets).
- `npm run test:e2e` script; `@playwright/test@1.64.0` + `@axe-core/playwright@4.14.0` + aligned `playwright-core@1.64.0` (avoids dual-version type conflict).
- CI: new step in `website-devapp-and-sdks` job — `playwright install --with-deps chromium` then `test:e2e`.

## Violations found & fixed (the gate caught real bugs on first run)
- `label-content-name-mismatch` (serious, all pages): Header search button aria-label didn't contain visible "Search ⌘K".
- `nested-interactive` (serious, 3 pages): interactive `<g role="button">` nodes inside `role="img"` SVGs → changed to `role="group"` (GoldenThreadStudioShowcase, LatencyCostFrontierChart).
- `label-content-name-mismatch` on SVG graph nodes: visible `<text>` concatenates without separators → added separating spaces inside text elements and aligned aria-labels.
- `aria-valid-attr-value` (CRITICAL, /models + /api-reference): Radix `Tabs.Trigger` used as pure filters with no `Tabs.Content` → `aria-controls` pointed at nonexistent panels. Replaced with `role="group"` + `aria-pressed` toggle buttons (semantically correct for filters).
- `scrollable-region-focusable` (serious): added `tabIndex={0}`+`role="region"`+`aria-label` to scrollable AST map, API response `<pre>`, and 3 marketplace snippet `<pre>`s.

## Evidence
- `npx playwright test`: **9/9 pass** — all 8 routes axe-clean + perf smoke.
- `tsc --noEmit` clean; `next build` clean.

## Known Limits
- Perf budgets are localhost smoke thresholds, not Core Web Vitals field data.
- axe covers WCAG 2.2 AA automated rules only (~30-50% of WCAG); manual audit still needed for full conformance.
- Playwright browser download adds ~100MB to CI setup.

## Next Recommended Action
All engineerable release-readiness items complete. Remaining: KEEL-PROD-041 weights decision (founder), live vendor re-probe post-quota, OpenCode/Cline/ACP adapters.
