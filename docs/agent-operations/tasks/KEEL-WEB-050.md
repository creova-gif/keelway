# KEEL-WEB-050 — website token-gap fix + embeddable audit correction

## Objective

Sweep `website` for dead code and stale token config; landed as a small
corrective fix after the audit corrected the original premise.

## Audit correction (important)

`website/src/components/home/GoldenThreadStudioShowcase.tsx` looks like
dead code (zero importers; uses tailwind color classes nothing else uses),
but it is **deliberately unmounted** — `test_phase13_homepage_studio_and_release.py`
enforces the file exists with a contract (`id="studio-showcase"`, stage
labels, `useReducedMotion`, `<500` lines) AND asserts the homepage must
*not* mount it: "v3 Maritime Instrument rebuild (KEEL-WEB-038): the
marketing homepage must not mount the studio showcase; it remains a
self-contained embeddable." `product-facts.json` registers it as
`AVAILABLE`; CHANGELOG 1.1.0 anchors `/#studio-showcase`.

Its foreign token namespace (`--bg-canvas`, `--fg-*`, `--teal-*`,
`--radius-*`, `data-theme="dark"` on the section root) is intentional —
the embeddable speaks the workspace/dev-app namespace, and
`website/tailwind.config.ts`'s `colors`/`borderRadius`/`darkMode` blocks
are its support config, not dead aliases. Deleting it broke
`test (3.11)`/`test (3.14)` — correctly.

## Shipped (single real fix)

`globals.css` now defines the missing radius scale on the dev-app values:

```css
--radius-sm: 6px;
--radius-md: 10px;
--radius-lg: 12px;
```

This makes the tailwind `borderRadius` aliases functional on this surface
and fixes `Mark.tsx`'s `rounded-md`, which previously resolved
`var(--radius-md)` → undefined → silently rendered at `border-radius: 0`.

## Not done (correctly)

- The remaining `colors` vars the embeddable references (`--bg-canvas`,
  `--fg-*`, `--teal-*`, `--amber-*`, `--red-*`) are still undefined in
  `globals.css`. They are only needed where the embeddable is mounted —
  defining them on the marketing surface would alias two namespaces that
  intentionally differ (marketing `--ink`/`--canvas` vs workspace
  `--fg-*`/`--bg-canvas`). If the embeddable is ever mounted inside
  `website`, those vars should be scoped under its `data-theme="dark"`
  root, not added to `:root`.

## Verification

- `tsc --noEmit`: clean
- `next build`: all routes prerender
- Full `pytest` suite must pass (the contract test governs this file)
