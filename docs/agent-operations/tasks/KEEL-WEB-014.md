# KEEL-WEB-014 — V3 Mobile rules on web-next (Paper page 08)

**Status**: READY_FOR_REVIEW
**Branch**: feature/keel-web-014-v3-mobile
**Paper source**: `Keelway — Brand Kit & Homepage` page `08 - Mobile` (p-8-0), artboards 08.1 + 08.2

## Scope

Paper page 08 defines the *product app's* mobile doctrine ("the bridge watch,
not the engine room" — gates/receipts/watch are mobile-native; authoring,
diffs, orchestration, shells stay desktop). The React Native `mobile/` app is
the true home for artboards 08.2A–C (gate, watch, receipt at 390px) — a larger
increment tracked separately.

This task applies the kit's *enforceable* mobile rules to the shipped web-next
site surface: thumb-reach targets >=44px (08.2), one-hand mobile nav.

## Changes

- `web-next/src/components/site/header.tsx`: mobile menu toggle and nav links
  now meet the kit's 44px thumb-target rule. Uses explicit `44px` values —
  the site sets `html { font-size: 13px }`, so rem utilities shrink
  (`h-11` = 35.75px actual, caught by the new test).
- `web-next/e2e/a11y.spec.ts`: new `mobile viewport (390px)` describe block —
  axe WCAG 2.2 AA pass on `/` at 390x844, plus a thumb-target assertion
  (toggle bounding box >= 44px, every mobile nav link row >= 44px).

## Verification

- `npm run typecheck`: clean
- `npm run build`: clean
- `npm run test:e2e`: 12/12 green (8 routes + 404 + perf smoke + 2 mobile tests)
  - First run caught real defects: toggle 35.75px, nav rows ~36px (13px root
    font-size shrinks all rem utilities — documented above).

## Follow-ups

- `mobile/` RN app: port 08.2A–C screens (gate/wait/receipt, biometric
  confirm, offline read-only). Requires device/simulator verification —
  separate task.
