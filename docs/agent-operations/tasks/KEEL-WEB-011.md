# KEEL-WEB-011 — web-next: apply V3 brand kit homepage

## Scope

Apply the new Paper V3 brand kit ("Keel Black & Brass — Maritime Instrument",
`Keelway — Brand Kit & Homepage` file, page 01) to the web-next surface.

Paper source: file `01M7T488WTKN3AQNQ2K9DB40TN`, page `01 - Homepage`
(artboards `1-0` brand V3 sheet, `V-0` homepage comp). Brand System page 04
confirms tokens are unchanged — same canvas/ink/accent values as canonical.

## Delivered

- Rewrote `web-next/src/app/page.tsx` to the V3 composition:
  - eyebrow `KEELWAY — SOVEREIGN AGENT PLATFORM` (mono micro label)
  - display `Agents that answer to you.` + working-voice body
  - brass `Install Keelway` CTA → repo README; `Read the docs →` text link
  - `FIG 0.1` control-plane panel: window chrome, tasks rail, P-10 gate /
    local / BYOM chips, execution receipts #1201–#1204 (sealed/awaiting),
    session cost / tape height / chain verified footer
  - YOUR HARDWARE / YOUR POLICY / YOUR RECORDS triptych
- Caption labels the panel honestly: `dev app surface` (sample render of the
  dev-app control plane, not a live capture claim).
- Existing shared header/footer + canonical tokens already match the kit.

## Verified

- `tsc --noEmit` clean; `next build` green (all 8 routes prerendered).
- `npm run test:e2e` — 9/9 green: axe WCAG 2.2 AA on all 8 routes incl. `/`,
  perf smoke within budget. First pass, no violations.

## Follow-ups

- V3 kit pages 02 (Product & Components) and 03 (Onboarding) are the next
  surfaces to port; product/onboarding pages pending.
- `website/` is the older Next surface — decide whether it gets V3 treatment
  or whether web-next becomes the canonical homepage.
- Parallel PR #193 (KEEL-WEB-010 demos) may conflict on `page.tsx` if it
  touches the landing page; rebase order TBD.
