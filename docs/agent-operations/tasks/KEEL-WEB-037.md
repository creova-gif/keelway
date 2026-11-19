# KEEL-WEB-037 — Website v2 "Editorial Precision": Hybrid Light/Dark, Near-Monochrome, Product-Forward Hero

- **TASK ID**: KEEL-WEB-037
- **TASK TITLE**: Website v2 redesign — editorial near-monochrome system, Linear-style dark product hero, real-app screenshot proof
- **CURRENT STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-web-037-editorial-precision`
- **BASE**: `main` @ `3513114`

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] New brand direction per user decision: hybrid light editorial / dark product surfaces, near-monochrome accent (teal demoted from CTA color)
- [x] Homepage hero rebuilt to Linear-style contract: one statement, one supporting line, minimal CTA pair, ONE full-width real `/app` product screenshot (`public/product/app-main.png`) in `kw-figure` hairline frame — stat grid, synthetic cockpit, and pill badge removed
- [x] Dark `data-theme` scoping retained for product surfaces: hero, `GoldenThreadStudioShowcase`, `QuickstartTerminal`, `ProductShowcase`, and app-adjacent pages (`/docs`, `/api-reference`, `/governance`, `/models`, `/marketplace`)
- [x] Light default theme: warm paper `#f6f5f2` canvas, ink `#141416`; `ThemeProvider` + `layout.tsx` default flipped to light; user toggle preserved
- [x] `kw-btn-primary` → inverted monochrome; decorative teal bullets/icons neutralized (`CustomerJourneyGrid`, `HeroCtaLinks`); proof strip flattened to hairline definition row
- [x] `.kw-display` enlarged to `clamp(2.625rem, 5.25vw, 4.5rem)` / `-0.045em`; `kw-fig-label` mono micro-captions replace decorative mono usage
- [x] DESIGN.md §7 documents v2 direction, theme model, chrome budget, hero contract
- [x] Verified: `npm run build` clean; `pytest tests/test_website_facts.py` 11 passed; Playwright 375px + 1440px across 9 routes: 0px overflow, 0 app console errors (only `_vercel/insights` 404s, local-only artifact)
- [x] Accessibility preserved: semantic `<figure>/<figcaption>`, `priority` LCP image with descriptive alt, skip link, focus-visible, reduced-motion rules untouched

## FILES MODIFIED

- `website/src/app/globals.css`: light token block → warm-paper editorial palette; `kw-btn-primary` monochrome; `kw-display` scale bump; new `kw-figure`/`kw-fig-label`
- `website/src/app/layout.tsx`: `data-theme="light"` default; themeColor updated
- `website/src/components/layout/ThemeProvider.tsx`: default + fallback → light
- `website/src/app/page.tsx`: hero rebuilt (statement + CTA + full-width real app screenshot); proof strip restyled
- `website/src/components/home/{GoldenThreadStudioShowcase,QuickstartTerminal,ProductShowcase}.tsx`: `data-theme="dark"` scoped bands
- `website/src/app/{docs,api-reference,governance,models,marketplace}/page.tsx`: dark-scoped product surfaces
- `website/src/components/home/{CustomerJourneyGrid,HeroCtaLinks}.tsx`: decorative teal neutralized
- `DESIGN.md`: §7 v2 "Editorial Precision" spec
- `docs/agent-operations/{ACTIVE_TASKS.md,tasks/KEEL-WEB-037.md}`: task records

## TESTS EXECUTED & EVIDENCE

- `npm run build`: compiled clean, all routes static/dynamic as before
- `pytest tests/test_website_facts.py`: `11 passed, 2 warnings in 0.58s`
- Playwright (Chromium headless shell): 18 route×viewport checks — 0px horizontal overflow, 0 real console errors; hero + docs + about + pricing screenshots reviewed at 1440px and 375px

## KNOWN RISKS & BLOCKERS

- `HeroControlCockpit` is now unreferenced (kept in tree for reuse; removal deferred to a cleanup pass)
- Pages not re-reviewed visually beyond screenshots: `/models`, `/marketplace` verified for overflow/console only
- Dark-scoped sections render dark regardless of user theme toggle — intentional per v2 spec, documented in DESIGN.md §7

## NEXT RECOMMENDED ACTION

PR → merge → confirm `kora-sable.vercel.app` deploy serves the new hero.
