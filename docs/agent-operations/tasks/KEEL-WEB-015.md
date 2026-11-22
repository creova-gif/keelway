### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-015
- **TASK TITLE**: web-next SEO/discovery surfaces — sitemap, robots, manifest, feed, OG metadata, favicon
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-015-seo-surfaces

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] `sitemap.ts` enumerating all 8 public routes (`/`, /product, /pricing, /docs, /changelog, /about, /contact, /sign-in)
- [x] `robots.ts` → `robots.txt` allowing all + sitemap pointer
- [x] `manifest.ts` → `manifest.webmanifest` (standalone, theme `#08090A`)
- [x] `feed.xml` RSS route handler with the canonical release items
- [x] Root layout: `metadataBase`, title template `%s · Keelway`, canonical alternates, OG image, theme-color viewport, favicon
- [x] `SITE_URL` exported from `lib/utils` (env-overridable, default `https://kora-sable.vercel.app`)
- [x] `public/` created with `favicon.svg` + `og-image.jpg` copied from canonical site

#### WORK COMPLETED & FILES MODIFIED
- `web-next/src/app/sitemap.ts`, `robots.ts`, `manifest.ts`, `feed.xml/route.ts`: ported from canonical `website/src/app/` (route list + title/description adjusted to web-next product naming)
- `web-next/src/app/layout.tsx`: full metadata block (metadataBase, title template, OG, alternates, manifest, icons) + `viewport` export
- `web-next/src/lib/utils.ts`: `SITE_URL` constant
- `web-next/public/favicon.svg`, `web-next/public/og-image.jpg`: assets copied from `website/public/`

#### TESTS EXECUTED & EVIDENCE
- `npx tsc --noEmit`: clean
- `npm run build`: all routes incl. `/feed.xml`, `/manifest.webmanifest`, `/robots.txt`, `/sitemap.xml` prerendered successfully
- `npx playwright test`: **10 passed** (9 WCAG 2.2 AA route checks incl. 404, 1 perf smoke)

#### KNOWN RISKS & BLOCKERS
- None. Feed items mirror the canonical three releases; new changelog entries should append FEED_ITEMS in both apps (or be centralized later).
- `next@15.5.6` flagged CVE-2025-66478 on `npm ci`; tracked by existing dependabot PRs.

#### NEXT RECOMMENDED ACTION
- Merge after CI; consider single-source for FEED_ITEMS if changelog cadence increases.
