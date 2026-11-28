# KEEL-WEB-052 — Public website UI/UX audit + motion-token fix

## Status: COMPLETED

## Scope
Full evidence-based audit of `web-next/` (canonical marketing site) against the
enterprise website-audit rubric: baseline capture, findings register, scorecard,
prioritized backlog. Fix confirmed findings in scope.

## Deliverable
`docs/audits/WEBSITE_UI_UX_AUDIT.md` — baseline method, findings register
(F-01..F-07), weighted scorecard (~83/100 vs 90 release threshold), checklist
verdicts, prioritized backlog.

## Findings implemented
- **F-03 fixed**: `motion/reveal.tsx` used `duration-[var(--dur-base)]` /
  `ease-[var(--ease-settle)]`, which Tailwind 3.4 flags ambiguous — arbitrary
  `var()` values on non-numeric utilities can be silently dropped, killing the
  reveal transition. Replaced with `transition-[opacity,transform]` +
  `[transition-duration:...]`/`[transition-timing-function:...]` arbitrary
  properties. `next dev` recompiles with zero ambiguous-class warnings;
  typecheck clean.

## Findings not implemented (need decision or non-code action)
- **F-01 (HIGH)**: prod `kora-sable.vercel.app` 404s on `/blog` + `/signup`
  (WEB-048 merged but never deployed). Vercel project config — needs owner.
- **F-02 (HIGH)**: magic-link form discards the email. Needs either a private
  webhook destination for a real `/api/early-access` port, or a product call to
  replace the form with an honest link.
- F-04 route-smoke e2e spec, F-05 legacy `website/` deprecation, F-06 homepage
  OG metadata, F-07 Docs 2.0 — backlog items in the audit doc.

## Tests executed & evidence
- `npm run typecheck` (web-next): clean
- `next dev` fresh compiles post-fix: 0 ambiguous-class warnings (was 4)
- 22-route Playwright capture at 1440px + 390px: no overflow, no render defects
- Prod probes: `/blog`,`/signup` → 404 (deploy lag); all other routes 200; HSTS
  preload header verified

## Next recommended action
Owner: check Vercel production deploy for web-next (F-01). Then F-02 product
call on the early-access intake path.
