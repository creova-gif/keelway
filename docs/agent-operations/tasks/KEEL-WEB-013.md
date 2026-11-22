# KEEL-WEB-013 — web-next: V3 404 ("off the chart")

## Scope

Complete the Paper page 03 V3 site-page set. Audit showed all V3 headlines
already landed via the parallel demos PR (#193): /about "Built by Sorvex
Labs.", /pricing "Priced like a ledger.", /changelog "The logbook, public.",
/contact "Talk to a human.", /sign-in "Sign in to Keelway Cloud." The only
missing V3 surface was the 404 (Paper `03.3c`).

## Delivered

- `web-next/src/app/not-found.tsx` — V3 404:
  - `ERR 404 — off the chart` eyebrow (brass watch channel — see below)
  - display "This page isn't on the tape." + honest body
  - brass `Back to bridge` → `/`, `Search docs →` → `/docs`
  - honest trace line: `trace: — · client-side 404, nothing logged`
    (the artboard's `logged & sealed` claim would be false — no logging exists)
- `e2e/a11y.spec.ts` — new axe case visits `/__not-found-test__` so the 404
  renders under the WCAG 2.2 AA gate (10/10 green)

## Verified

- `tsc --noEmit` clean; `next build` green.
- e2e 10/10: axe caught a real defect on first run — `text-danger`
  (#B0564E) measures 3.84:1 on canvas, below AA 4.5:1 for 11px text
  (Paper's own table claims 4.6:1 — doesn't hold at micro size).
  Fixed by using the kit's designated `watch` channel (brass `--accent`,
  8.1:1) for the ERR eyebrow.
- Env note: Playwright chromium binary had been evicted from the local
  cache — reinstalled via `npx playwright install chromium`.

## Follow-ups

- Page 08 Mobile artboards remain — check for V3 deltas vs the existing
  responsive layouts.
- dev-app product-state parity sweep vs Paper `04.2` (onboarding modal,
  P-10 dialog, empty/error/notification patterns).
