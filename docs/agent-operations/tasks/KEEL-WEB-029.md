### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-029
- **TASK TITLE**: Migrate unique `kora-ai/website` content into canonical site, fix responsive/a11y defects, deprecate divergent site
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-16
- **BRANCH**: feature/website-kora-content-migration
- **HEAD COMMIT**: <pending — set at commit>

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
