# KEEL-DSN-005 — Code-side sync of DSN-004 tokens + font-weight audit

## Status: COMPLETED

Two open code-side items from KEEL-DSN-004's Paper session:

1. **Spacing scale sync** — Paper's 6-step scale (`--space-xs`..`--space-2xl`:
   8/14/24/40/56/80px) added to `dev-app/src/styles/tokens.css` root block
   (theme-invariant). `tokens.json` spacing statuses flipped code-missing →
   synced. `web-next` has no token layer (Tailwind defaults) — noted.
2. **font-weight 700 audit** — TOKENS.md flagged "no code-side audit run" for
   Inter >640 weights. Found 13 `font-bold` (Tailwind 700) sites: 11 dev-app
   (wordmark, badges, verdict/wave chips, diff markers, callout icon) + 2
   web-next (site Mark, header wordmark). All → `font-[640]` (Inter is a
   variable font 100–900; 640 renders natively and matches the Paper
   correction). Zero remaining.

Evidence: `tsc --noEmit` clean; full vitest suite 133/135 — the 2 failures in
`phase6-ops-pricing-simulator.test.tsx` are the documented full-suite load
flake (file passes in isolation on branch AND clean origin/main).
