# KEEL-WEB-036 — DESIGN.md v1.1 "Precision Instrument" Website Refinement

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `WEBSITE / UX / DESIGN-SYSTEM` |
| **Agent** | Devin |
| **Date** | 2026-11-19 |
| **Branch** | `feature/keel-web-036-precision-design` |

## Objective
Implement the user-approved DESIGN.md v1.1 "Precision Instrument" update on the
canonical website (`website/`): formal fluid typography scale, uniform section
rhythm, restrained component polish, and minimal functional motion — the "calm
engineering" north star. No palette/brand changes; zinc + single teal retained.

## Changes
- `DESIGN.md`: appended Section 6 documenting the v1.1 layer (fluid type
  scale, section rhythm + index rule, `frame-teal-rule` emphasis, reveal
  motion spec); Display Header row updated to new clamp values;
  `gstack: design-md-format=legacy-keep` marker added (file intentionally
  kept in hand-authored format, not gstack spec).
- `website/src/app/globals.css`: added `.kw-display`, `.kw-h2`, `.kw-kicker`,
  `.kw-section-index`, `.frame-teal-rule`, `.kw-reveal` (+`is-visible`,
  stagger delays) utilities; unified chip recipe (`rounded-sm`, 11px mono,
  `border-strong`); reduced-motion gate preserves all reveal/motion rules.
- `website/src/components/motion/Reveal.tsx`: new client component —
  IntersectionObserver fade-rise, hidden state applied post-mount only to
  offscreen elements (fully visible without JS; no-op under
  `prefers-reduced-motion`).
- `website/src/app/page.tsx`: hero `h1` → `.kw-display`; `ProductShowcase`
  wrapped in `<Reveal>`.
- `website/src/components/home/ProductShowcase.tsx`: `py-16 sm:py-24`
  rhythm, `kw-section-index` ("01 / PROOF"), `kw-kicker` badge, `kw-h2`
  heading, `frame-teal-rule` on the interactive proof figure.
- `website/src/app/{about,enterprise,contact}/page.tsx`: `h1` → `.kw-display`.
- `AGENTS.md`: added `## 10. DESIGN SYSTEM` section (read DESIGN.md before
  UI work; flag mismatches in review).

## Acceptance Criteria
- [x] Fluid type scale implemented and applied to hero + corporate h1s
- [x] Section rhythm + index utility added (applied to ProductShowcase only — capped usage per proposal)
- [x] Teal top rule limited to the interactive proof figure
- [x] Reveal motion: CSS transition, ≤3 stagger, JS-gated hidden state, reduced-motion safe
- [x] `npm run build` clean; `pytest tests/test_website_facts.py` 11 passed
- [x] Playwright @375px: 0px horizontal overflow on `/`, `/about`, `/enterprise`, `/contact`; no console errors; reveal activates on scroll; `.kw-display` renders 60px @1440px
- [x] `gstack-design-md check DESIGN.md` → `DESIGN_MD_MARKER: legacy-keep`

## Tests Executed
- `npm run build`: clean (all routes compiled)
- `pytest tests/test_website_facts.py`: **11 passed**
- Playwright chromium: overflow 0px ×4 routes; 0 pageerror; reveal
  `is-visible` after scroll

## Known Risks & Blockers
- `kw-section-index` used once (ProductShowcase); extending to more sections
  should follow the "major sections only" cap in DESIGN.md §6.
- Reveal hidden state is applied post-mount; pre-hydration markup renders
  fully visible (intentional — no CLS, no SEO/a11y penalty).

## Next Recommended Action
- Merge via PR; optionally extend `kw-h2`/`kw-kicker` alignment to remaining
  marketing pages in a follow-up sweep.
