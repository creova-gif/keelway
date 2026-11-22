# KEEL-WEB-012 — web-next: V3 component grammar + /product restyle

## Scope

Apply Paper page 02 ("Product & Components" — `04.1` component library +
`04.2` product screens & states) to web-next.

## Delivered

- `web-next/src/components/ui/chip.tsx` — status chip primitive with the
  four kit variants: `gate` (brass), `sealed` (starboard green), `denied`
  (port red), `neutral`
- `web-next/src/components/site/receipt-table.tsx` — mono hairline receipts
  table (no zebra, hover fog-lift, sealed/awaiting status column)
- `web-next/src/app/product/page.tsx` rewritten to V3:
  - eyebrow + display "Every action on the tape. Yours to replay." (kit voice
    example, marketing register)
  - gateway/policy/tape instrument triptych with chips
  - `FIG 1.1` receipts table — honestly captioned `sample render`
  - `FIG 1.2` interactive PolicyDemo — caption declares it runs locally in
    the page, no backend call implied

## Verified

- `tsc --noEmit` clean; `next build` green.
- `npm run test:e2e` — 9/9: axe WCAG 2.2 AA all 8 routes + perf smoke.
  First pass, no violations.

## Follow-ups

- Paper `04.2` app-state patterns (onboarding modal, P-10 dialog, empty/
  error/notification centers, mobile nav) belong to the dev-app surface —
  most already exist there; a parity sweep could map each artboard to the
  live components.
- Onboarding page 03 artboards are the next V3 web surface.
