# TASK: KEEL-WEB-006 — Next.js 15 Flagship Company Website Redesign & Competitive Upgrades

## 1. METADATA
- **TASK ID**: KEEL-WEB-006
- **CATEGORY**: WEBSITE / DX / BRAND
- **LAST ASSIGNED AGENT**: Google Antigravity
- **CURRENT STATUS**: VERIFIED_COMPLETE
- **DATE**: 2026-11-13
- **TARGET BRANCH**: `main`

---

## 2. OBJECTIVE & MOTIVATION
Redesign and upgrade Keelway's company website (`keelway/website/`) from static HTML pages into an interactive, WCAG AA-accessible, sovereign-first **Next.js 15 + React 19 + TypeScript + Tailwind CSS + Radix UI + Framer Motion** application faithfully implementing `DESIGN.md` ("Calm Utility over AI Theater") and `brand.html`, including 4 competitive developer-platform upgrades.

---

## 3. ACCEPTANCE CRITERIA
- [x] **7 Production Routes (`Stages 1–5`)**: Implemented `/`, `/models`, `/governance`, `/pricing`, `/brand`, `/docs`, and `/api-reference`, plus permanent `308` redirects for legacy `/index.html`, `/docs.html`, `/api.html`, and `/brand.html` in `website/next.config.ts`.
- [x] **Global `Cmd+K` Instant Search Palette**: Static build-time `/api/search-index` indexing all pages, doc sections, 15 hybrid models, and 186 OpenAPI 3.1 endpoints (`226` total jump targets) with deep `?q=` query-parameter filtering.
- [x] **Real 60fps Studio & Metal CLI Demo Loops**: Recorded and encoded `studio-approval-loop.{webm,mp4}` and `cli-metal-stream.{webm,mp4}` (captured against live Apple Silicon MLX `qwen3.5:latest`) with `prefers-reduced-motion` compliance.
- [x] **Empirical Latency & Quality Scatter Plots**: Interactive SVG scatter plots (`LatencyCostFrontierChart.tsx`) on `/models` and `/governance` comparing measured Warm TTFT (ms), Blended Cost (\$/1M), Quality Index, and Throughput (tok/s) with keyboard-focusable points and an accessible `<table>` view.
- [x] **Live Connected Sandbox Mode**: Rate-limited read-only `POST /api/sandbox/routing-explain` endpoint (`30 req / 60s`, pre-egress secret scrubbing, 4D provenance receipts) wired to both `/api-reference` (`LiveRoutingSandbox.tsx`) and Lens 2 of `HeroControlCockpit.tsx`.
- [x] **Sovereign Asset & Fact Integrity**: Zero external Google Fonts or third-party CSS/JS CDNs; self-hosted `Inter` and `JetBrains Mono` `.woff2` variable fonts verified by `tests/test_website_facts.py`.

---

## 4. HANDOFF RECORD
### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-006
- **TASK TITLE**: Next.js 15 Flagship Company Website Redesign & Competitive Upgrades
- **CURRENT STATUS**: COMPLETED
- **LAST AGENT**: Antigravity
- **DATE**: 2026-11-13
- **BRANCH**: `main`
- **HEAD COMMIT**: `5b2fbc3` (working tree verified)

#### WORK COMPLETED & FILES MODIFIED
- `vercel.json`, `api/early-access.js`: Updated Vercel monorepo Next.js build routing and lead-capture parity.
- `website/package.json`, `website/next.config.ts`, `website/tailwind.config.ts`, `website/tsconfig.json`: Next.js 15 App Router scaffold & `308` redirects.
- `website/src/app/**`, `website/src/components/**`, `website/src/data/**`, `website/public/demos/**`: Complete 7-page interactive platform showcase + 4 flagship upgrades.
- `website/openapi.json`, `website/public/openapi.json`, `website/product-facts.json`, `website/public/product-facts.json`: Synchronized OpenAPI 3.1 (`186` endpoints) and verified product-facts manifests.

#### TESTS EXECUTED & EVIDENCE
- `cd website && npm run typecheck && npm run build`: `0 errors, 15/15 static routes + dynamic sandbox compiled cleanly`
- `pytest tests/test_website_facts.py tests/test_api_export.py -v`: `8 passed`

#### KNOWN RISKS & BLOCKERS
- None.

#### NEXT RECOMMENDED ACTION
- Ready for `git commit` and Vercel production deployment (`https://kora-sable.vercel.app/`).
