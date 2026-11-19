# KEEL-WEB-038 — Website v3 "Maritime Instrument": Fresh Rebuild, New Brand Kit, Dark-Native Brass System

- **TASK ID**: KEEL-WEB-038
- **TASK TITLE**: Full website rebuild to Paper-approved "Maritime Instrument" brand — instrument-black canvas, binnacle brass, K′ mark, reduced 8-route surface
- **CURRENT STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-web-038-maritime-instrument`
- **BASE**: `main`

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] Fresh-start rebuild per user direction ("delete the whole content… start afresh with new brand identity kit") implementing the Paper design file `Keelway — v3 Brand Kit & Homepage` (4 pages: Concept, Brand System, Website, Product & Components)
- [x] New brand kit: instrument black `#08090a` canvas, fog-lift surfaces (`white/4`, `white/8`), hairline `white/6` rules, fog ink `#f4f5f5`, muted `#9ba1a6`, dim `#5d6268` (decorative only), binnacle brass `#c9a45c` (rare: mark prime, primary CTAs, recommended/sealed states), semantic starboard green `#6fae8e` / port red `#b0564e` / flag blue `#6f87a3` — always paired with labels
- [x] `K′` mark (`components/site/Mark.tsx`) + restyled `favicon.svg` (brass prime replaces teal dot); wordmark Inter 700 sentence case
- [x] Type: Inter display `clamp(2.75rem,5.5vw,4.75rem)` w640 `-0.045em`; JetBrains Mono for `.kw-label`/`.kw-data` only; no gradients/glows/shadows/textures anywhere
- [x] Route set reduced to `/`, `/about`, `/product`, `/pricing`, `/changelog`, `/contact`, `/sign-in`, 404 + infra routes (`feed.xml`, `sitemap.xml`, `robots.txt`, `manifest.webmanifest`); deleted pages preserved in git history; `next.config.ts` 301s legacy paths to live equivalents
- [x] Homepage: eyebrow → "Agents that answer to you." → subline → CTAs → real `app-main.png` `FIG 0.1` → YOUR HARDWARE / YOUR POLICY / YOUR RECORDS columns → install line → footer
- [x] Pricing renders canonical 5-tier truth (Community $0, BYOM $15, Pro $29 brass-recommended, Team $49, Enterprise VPC) + 0% token markup
- [x] Honesty fixes: contact form drafts a GitHub issue (no invented mailbox — removed `contact@sorvexlabs.com`); sign-in magic-link is an honest "private preview" stub
- [x] A11y: interactive/small text at ≥4.5:1 (`--muted`), `--dim` only decorative captions; 3px brass focus ring; reduced-motion gates `.kw-rise` + smooth scroll; labeled inputs; `aria-expanded` mobile nav; `sr-only` email label
- [x] DESIGN.md §8 documents v3 and what it supersedes (§1 mark/colors, §7 theme model)

## FILES MODIFIED

- `website/src/app/globals.css`: full token rewrite to Maritime Instrument; `kw-*` utilities; reduced-motion + focus ring + disabled rules
- `website/src/app/{layout,page,not-found}.tsx` + `app/{about,product,pricing,changelog,contact,sign-in}/page.tsx`: v3 pages
- `website/src/components/layout/{Header,Footer}.tsx`: `K′` lockup, mobile nav, sparse brass CTAs, accurate tier strip
- `website/src/components/site/{Mark,ContactForm,MagicLinkForm}.tsx`: new
- `website/public/favicon.svg`: brass prime
- `website/{next.config.ts,app/feed.xml/route.ts,app/sitemap.ts,app/robots.ts,app/manifest.ts}`: redirects + SEO surfaces repointed to live routes
- Deleted routes (recoverable in git): `docs`, `api-reference`, `governance`, `models`, `marketplace`, `enterprise`, `brand`, `playground`, `search`, `api/*`
- `tests/test_website_facts.py`, `tests/test_phase13_homepage_studio_and_release.py`: updated to v3 route set (showcase remains self-contained, not mounted)
- `website/product-facts.json` (+ `public/` copy): repointed dead `code_path`s to live surfaces; parity verified
- `DESIGN.md`: §8 spec

## TESTS EXECUTED & EVIDENCE

- `npm run build`: clean, 15 routes generated, ~102 kB shared JS
- `pytest tests/test_website_facts.py tests/test_phase13_homepage_studio_and_release.py`: `7 passed, 2 warnings`
- Playwright @375px + @1440px across 8 routes: 0px overflow, 0 app console errors (expected 404 on `/nonexistent` probe only); home/pricing screenshots reviewed
- `product-facts.json` path audit: 0 missing `code_path`/`evidence_test` targets

## KNOWN RISKS & BLOCKERS

- Deleted marketing pages (`/docs`, `/marketplace`, `/governance`, `/models`, `/enterprise`) are gone by design; inbound external links 301 to nearest live route, not equivalents — content resurrection needs a deliberate page-by-page pass
- `GoldenThreadStudioShowcase` remains as a fact-pinned self-contained embeddable, unmounted on the v3 surface; `MarketplaceCatalogExplorer`/`PricingTiers` were deleted and their facts repointed to the live `/pricing` page
- Playwright workaround: local `chromium_headless_shell-1148` cache dir was symlinked to the 1254 build (project pins Playwright 1.64 but only 1248/1254 binaries are cached) — harmless for smoke checks; `npx playwright install` will replace it if a real 1148 is needed
- Pricing shows Team $49 — canonical per README/CHANGELOG/`releases.ts`; Paper mock's 3-card layout was a simplification

## NEXT RECOMMENDED ACTION

Commit → PR → merge → confirm `kora-sable.vercel.app` serves the new dark brass homepage; then decide which deleted pages to resurrect (docs is the likely first candidate).
