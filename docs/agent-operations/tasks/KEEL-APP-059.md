# KEEL-APP-059 — Reveal component + product figure tabs

## Summary
Closes the DESIGN.md §6 drift (`Reveal.tsx` documented but missing) and adds
the kit's interactive-motion layer to two more marketing surfaces.

## Changes
- `website/src/components/motion/Reveal.tsx` (new) — IntersectionObserver
  fade-rise per DESIGN.md §6: hidden state applied post-mount only when the
  element starts offscreen; SSR output fully visible; `prefers-reduced-motion`
  skips gating. Stagger via `delay={1|2}` (≤3 items).
- `website/src/app/globals.css` — `.kw-reveal` / `.kw-reveal-in` /
  `kw-reveal-delay-{1,2}` on `--dur-base` + `--ease-settle`.
- `website/src/components/site/FigureTabs.tsx` (new) — kit 09.3 feature
  carousel: brass-underlined tablist over the three ControlPlaneFigure
  variants (gate/flow/policy). `role="tablist"` + `tab`/`tabpanel`,
  `aria-selected`, manual control only (no auto-advance), panel remounts
  under `kw-land` for the land animation.
- `website/src/app/product/page.tsx` — stacked static figures replaced by
  FigureTabs; instrument cards wrapped in Reveal stagger + hover border.
- `website/src/app/pricing/page.tsx` — tier cards wrapped in Reveal stagger
  (capped at delay 2 per §6) + hover border.
- `DESIGN.md` §6 — drift resolved: Reveal now exists; timing pointed at §9
  canonical tokens.
- `docs/agent-operations/ACTIVE_TASKS.md` — KEEL-APP-058 marked
  VERIFIED_COMPLETE (PR #153 merged at d94dc83).

## Verification
- `website`: `npm run build` — all 15 routes compile, /product and /pricing
  prerender clean.
- dev-app untouched this task; APP-058 verified 119/119 tests + tsc clean.

## Follow-ups
- Remaining unmocked kit surfaces live in Paper p-12/p-13 specs.
- Candidate next: apply Reveal to /about, /changelog rows if scroll length
  warrants.
