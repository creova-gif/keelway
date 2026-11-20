# KEEL-APP-060 — Reveal sweep: /about + /changelog

## Summary
Completes the marketing-site motion sweep by applying the APP-059 Reveal
component to the remaining long-list routes.

## Changes
- `website/src/app/about/page.tsx` — P-01..P-04 principle rows stagger-reveal
  (delay capped at 2 per DESIGN.md §6); row semantics unchanged.
- `website/src/app/changelog/page.tsx` — each release article reveals on
  scroll (delay 0; rows reveal individually as they enter the viewport).

## Verification
- `website` `npm run build` — all 16 routes compile (pre-existing
  `@vercel/flags` optional-peer warning, unrelated).

## Follow-ups
- Website motion vocabulary is now complete: seal-land gate demo, underline
  nav, figure tabs, scroll reveals, hover borders — all tokenized,
  reduced-motion safe.
- Remaining kit gaps live in Paper: accessibility spec page, icon catalog,
  deck template.
