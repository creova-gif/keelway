# KEEL-WEB-010 — web-next interactive demo port

## Objective
Port the canonical website's remaining interactive demos to web-next on its own
token/component conventions (shadcn Button, `fg-*`/`accent`/`ok`/`danger`
semantic tokens, kebab-case filenames).

## Shipped
- `src/components/site/control-plane-figure.tsx` — gate (live P-10 demo: allow/deny →
  seal-ring + receipt state + tape increment) / flow / policy variants
- `src/components/site/figure-tabs.tsx` — kit 09.3 tab switcher on `/product` (role=tablist, kw-underline)
- `src/components/site/terminal-demo.tsx` — homepage session replay: typewriter run →
  P-10 gate → visitor allow/deny → sealed/denied receipt; reduced-motion instant path
- `src/components/site/install-command.tsx` — copyable install one-liner w/ ✓ copied
- `src/components/site/cost-compare.tsx` — `/pricing` workload slider ($0 open_weight vs ≈$10/1M frontier)
- `src/components/motion/reveal.tsx` — IntersectionObserver fade-rise, SSR-safe + reduced-motion safe
- Pages wired: `/` (terminal + install), `/product` (FigureTabs), `/pricing` (CostCompare), `/changelog` (Reveal rows)

## Verification
- `npx tsc --noEmit` clean
- `npx next build` — 9 routes compile (/product 14.6 kB First Load)
- `npx playwright test` — **9/9 green**: axe WCAG 2.2 AA on all 8 routes + perf smoke.
  Caught+fixed a real defect: ported `text-fg-dim` (#5d6268, 3.4:1 decorative-only)
  for informative text → `text-fg-muted`; same doctrine as kit page 14.

## Notes
- Task ID reassigned: KEEL-WEB-009 was taken by parallel work (/about + /contact + /sign-in).
- fg-dim remains decorative-only in web-next; informative text uses fg-muted.
