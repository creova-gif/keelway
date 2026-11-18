### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-029
- **TASK TITLE**: Migrate unique `kora-ai/website` content into canonical site, fix responsive/a11y defects, deprecate divergent site
- **CURRENT STATUS**: COMPLETED (merged to main)
- **LAST AGENT**: Devin
- **DATE**: 2026-11-16
- **BRANCH**: feature/website-kora-content-migration
- **HEAD COMMIT**: 9041958

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Inventory `kora-ai/website` content/components/assets and compare against canonical `keelway/website`
- [x] Migrate unique content adapted to the canonical design system (no duplicated pages/components)
- [x] Integrate migrated content into existing routes/navigation (sitemap unchanged — no new routes)
- [x] Fix discovered accessibility/responsive defects (mobile horizontal overflow on all pages)
- [x] `npm run build` passes; site runs locally with zero JS errors
- [x] `kora-ai/website` reduced to README + meta-refresh redirect stub pointing at https://kora-sable.vercel.app/

#### WORK COMPLETED & FILES MODIFIED
- `website/src/components/home/SettlementRails.tsx` (new): "Sovereignty Beyond US Credit Cards" multi-rail settlement explorer (M-Pesa STK Push, PIX EMVCo, UPI 2.0, L402 Lightning) with `role=radiogroup`, `aria-checked`, 44px+ touch targets; mounted in `src/app/page.tsx` (`/#settlement`) after `QuickstartTerminal`
- `website/src/components/models/SpeculativeDecodingLab.tsx` (new): tandem 0.5B-draft/7B-target speculative-decoding velocity slider (k=1–8, aria-labeled, `aria-live` readout); mounted on `/models` after `ModelExplorer`
- `website/src/components/governance/SelfHealingWorktreeLab.tsx` (new): closed-loop AST self-healing worktree demo with `aria-pressed` air-gap toggle; mounted on `/governance` labs section (`#self-healing-worktree`)
- `website/src/lib/analytics.ts`: added `settlement_rail_selected`, `spec_decoding_k_changed`, `self_healing_demo_run`, `airgap_enabled`, `airgap_disabled` events
- `website/src/app/globals.css`: wrapped `.kw-btn*` rules in `@layer components` — unlayered CSS was overriding Tailwind's `hidden` utility, so `hidden xl:inline-flex` buttons rendered at all breakpoints
- `website/src/components/layout/Header.tsx`: `⌘K` hint hidden below `sm:` to prevent mobile header overflow
- `website/src/components/pricing/PricingTiers.tsx`: `[overflow-wrap:anywhere]` on FAQ answers — unbreakable token `CREDENTIAL_TYPE_UNSUPPORTED_CONSUMER_SUBSCRIPTION` caused 113px overflow
- `website/src/components/marketplace/MarketplaceCatalogExplorer.tsx`: `min-w-0` on `lg:col-span-*` grid children — grid `min-width:auto` caused 310px overflow
- `docs/agent-operations/ACTIVE_TASKS.md`: registry row added

#### TESTS EXECUTED & EVIDENCE
- `npm run build`: pass — all routes prerendered, no errors
- `.venv/bin/pytest tests/test_website_facts.py -q`: `11 passed in 0.60s`
- `npx next start` + Playwright (headless Chromium): all 3 migrated demos interactive (rail tabs, k-slider → 83.5 tok/s, self-heal patch, air-gap toggle); zero page errors; only expected local `/_vercel/insights/script.js` 404
- Mobile (375px) horizontal overflow measured per route: `/`, `/models`, `/governance`, `/pricing`, `/marketplace`, `/docs`, `/api-reference`, `/brand` — all `0px` (was 51/113/310px)

#### DECISIONS MADE AUTONOMOUSLY
- Settlement → homepage (sovereign-economy differentiator); speculative decoding → `/models` (inference economics context); self-healing → `/governance` labs (verified-patch governance framing)
- Sitemap/nav unchanged: no new routes added; section anchors only
- NOT migrated (already covered better by canonical): hero/stat strip, install command (`QuickstartTerminal`), audience steps (`CustomerJourneyGrid`), FAQ (pricing FAQ + docs), features bento, footer
- Divergent site deprecated via README + `index.html` meta-refresh stub rather than keeping a second Next.js app

#### KNOWN RISKS & BLOCKERS
- None functional. Settlement/demo figures are illustrative marketing values, consistent with existing site conventions.
- `kora-ai/website` node_modules/app code deleted — content preserved in git history and now lives in canonical components.

#### NEXT RECOMMENDED ACTION
Review diff, merge `feature/website-kora-content-migration` to `main`, deploy to Vercel; confirm `kora-ai` deployment (if any) resolves to the redirect stub.

---

## POST-MERGE FOLLOW-UP — /changelog route + production perf audit (Devin)

**Commit:** `9faefe4` (main, pushed)

### Added
- `website/src/app/changelog/page.tsx` — real Changelog & Release Notes page rendering `src/data/releases.ts` (mirrors `CHANGELOG.md`; Keep a Changelog + SemVer). Errata-excluded: external-IdP OIDC claim and uncommitted TLA+ spec not presented as functionality.
- `website/src/data/releases.ts` — structured v1.1.0 / v1.0.0 highlight data.
- `/changelog` added to `sitemap.ts` (priority 0.7) and Developer footer column.

### Verification
- `npm run build`: clean; `pytest tests/test_website_facts.py`: 11 passed (one caught and fixed — facts test rejects `creova-gif` org links in website source; replaced GitHub link with `CHANGELOG.md` code reference).
- Playwright @375px: 0px overflow, 0 JS errors.

### Production perf audit (Playwright, live, ms)
| Route | TTFB | Load | LCP | CLS |
|---|---|---|---|---|
| / | 114 | 396 | 388 | 0 |
| /models | 67 | 331 | 328 | 0 |
| /governance | 111 | 317 | 352 | 0 |
| /pricing | 73 | 262 | 248 | 0 |
| /changelog | 76 | 437 | 336 | 0 |

All LCP < 400ms (target <2.5s), CLS 0.0 — comfortably "good" CWV. Live `/changelog` returns 200.

---

## COMPETITIVE-GAP PASS — product proof, corporate surfaces, docs depth (Devin)

**Branch:** `feature/website-product-proof`

### Added
- **Real product proof (gap 1):** `src/components/home/ProductShowcase.tsx` — tabbed gallery of actual `/app` captures (`public/product/app-main.png` P-10 gate + receipts, `app-automation.png` KFlow DAG studio, `app-security.png` governance posture). Mounted on homepage after Quickstart; `role="tablist"`/`aria-selected`, lazy-loaded imgs, `product_showcase_tab` analytics event registered in `KeelwayAnalyticsEvent` union.
- **Verifiable-facts strip (gap 4):** honest proof layer on homepage — Apache-2.0 open core, Python/TS/Go SDK parity, 16-probe eval suite, 0% BYOM markup. No logos/testimonials fabricated.
- **Corporate surfaces (gap 2):** `/about` (Sorvex Labs positioning + beliefs), `/enterprise` (VPC/air-gap, identity w/ honest OIDC-scope caveat, P-10 quorum, SIEM export, 4-step design-partner onboarding), `/contact` (reuses `EarlyAccessForm` → `/api/early-access`). All with canonical + OG metadata.
- **Docs depth (gap 3):** DocsHub gained `05 Troubleshooting` (keelway doctor commands + symptom/resolution table incl. AirGapViolationError, P-10 quorum, credential-type, ledger-verification) and `06 Releases & Community` (changelog/RSS/openapi/contact links).
- **Nav wiring:** `/enterprise`, `/about`, `/contact` in sitemap + Enterprise & Trust footer column; `/releases` → `/changelog` 308 redirect in `next.config.ts`.

### Verification
- `npm run build`: clean — 3 new routes static (~106–107 kB first load each).
- `pytest tests/test_website_facts.py`: 11 passed.
- Playwright @375px: 0px overflow on /, /about, /enterprise, /contact, /docs; 0 JS errors. Screenshot tabs switch images correctly; lazy-loaded shot confirmed loading on scroll (1440×900 intrinsic).

### Decisions
- `/contact` reuses `EarlyAccessForm` rather than a new endpoint — one intake, contextual copy distinguishes demo/enterprise intent.
- No `/status` page: no real uptime data exists; live-product signal satisfied via changelog + `/releases` redirect + footer links (per "no fake activity" constraint).

### Deferred
- `keelway.dev` domain cutover + `SITE_URL` update (user-deferred).
