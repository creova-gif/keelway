# KEEL-WEB-051 — `/legal` on the deployed site (website/)

## Objective

Close the credibility gap on the production surface: the deployed site
(`website/` — Vercel Root Directory per `.vercelignore`, the `kora`
project) had no Terms/Privacy page. KEEL-WEB-048 shipped `/legal` to
`web-next/` (the Paper-13 replacement scaffold), but that surface does
not deploy yet — production needed the route now.

## Shipped

- `website/src/app/legal/page.tsx` — Terms (T-01..T-05) + Privacy
  (P-01..P-04) clause rows, ported from `web-next/src/app/legal` into
  `website/` conventions: `kw-*` classes, `var(--rule)`/`var(--muted)`
  tokens, `kw-row-hover`, `Reveal` staggered motion. Claims kept
  honest-only: Apache-2.0 core, private-preview cloud, 0% token markup,
  magic-link-only auth, contact data never routed to public trackers,
  "signed agreement governs" scope note.
- `Footer.tsx` — `Legal` added to footer nav (discoverability).
- `sitemap.ts` — `/legal` indexed.
- `e2e/a11y.spec.ts` — `/legal` added to the WCAG 2.2 AA route surface.

## Scope decision

Only `/legal` was ported — the one route with a real production
consequence (a marketing site with no terms/privacy). `/blog`,
`/signup`, `/offline` stay scoped to `web-next/` — the scaffold is the
intended future surface, and `/sign-in` + `/contact` already cover
their critical user paths on production.

## Verification

- `npm run typecheck` + `npm run build` clean; `/legal` prerenders
  static at 592 B
- `npx playwright test -g "legal"`: axe WCAG 2.2 AA — 0 violations
