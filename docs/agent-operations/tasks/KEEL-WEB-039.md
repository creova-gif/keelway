# KEEL-WEB-039 — Brand-Native Sample Figures Replace Stale Product Screenshots

- **TASK ID**: KEEL-WEB-039
- **TASK TITLE**: Replace real `/app` captures with code-rendered brand sample figures ahead of product UI changes
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-web-039-sample-figures`
- **BASE**: `main`

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] Remove `public/product/app-*.png` captures (user: "we will change them") — all 3 files + refs deleted
- [x] New `components/site/ControlPlaneFigure.tsx` — code-rendered Maritime Instrument instrument mock matching the Paper homepage mock structure
- [x] Three variants: `gate` (tasks rail + P-10 gate + plan steps + sealed/awaiting receipts + cost/tape strip — hero FIG 0.1), `flow` (KFlow DAG strip — product FIG 1.1), `policy` (pre-egress rules table — product FIG 1.2)
- [x] Honest captions: "sample render" (not "captured live")
- [x] A11y: `role="img"` + descriptive `aria-label`; inner mock `aria-hidden`, no fake interactive elements (`<span>` buttons)

## FILES MODIFIED

- `website/src/components/site/ControlPlaneFigure.tsx`: new
- `website/src/app/page.tsx`, `website/src/app/product/page.tsx`: `<Image>` → `<ControlPlaneFigure>`
- `website/public/product/`: deleted (3 PNGs)

## TESTS EXECUTED & EVIDENCE

- `npm run build`: clean, 15 routes
- `pytest tests/test_website_facts.py tests/test_phase13_homepage_studio_and_release.py`: `7 passed`
- Playwright 375px + 1440px: 0px overflow; home/product screenshots reviewed both widths

## KNOWN RISKS & BLOCKERS

- Sample figures are illustrative, not product truth — swap in real captures once the new `/app` UI lands

## NEXT RECOMMENDED ACTION

PR → merge → prod verify; later, replace samples with fresh captures of the redesigned app.
