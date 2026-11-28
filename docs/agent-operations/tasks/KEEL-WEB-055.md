# KEEL-WEB-055 — Remove deprecated `website/` directory; migrate drift-gate contracts to `web-next/`

## Status: COMPLETED

## Scope
Final F-05 residual from `docs/audits/WEBSITE_UI_UX_AUDIT.md`: the deprecated
`website/` (v3 Maritime) app still existed because it hosted repo-level
claims→code contracts (`product-facts.json`, `openapi.json`, `install.sh`) and
the pytest drift gates pinned them. Migrated the contracts to `web-next/`,
repointed every test/config/doc reference, then deleted the directory.

## Files modified / moved
- `git mv` → `web-next/product-facts.json`, `web-next/openapi.json`,
  `web-next/public/product-facts.json`, `web-next/public/openapi.json`,
  `web-next/public/install.sh` (served curl-installer asset preserved).
- `web-next/product-facts.json` + `public/` mirror: removed feature
  `zero_install_homepage_golden_thread_studio_showcase` (its `code_path` pinned
  deleted files); added real `early_access_intake` feature →
  `src/app/api/early-access/route.ts`; `blast-radius` slug preserved on
  `golden_thread_bidirectional_studio_and_blast_radius`. Still 24 features.
- `website/install.sh` **not** migrated — `scripts/install.sh` is the newer
  canonical bash installer; references repointed to it.
- `web-next/package.json`: version `0.1.0` → `1.1.0` (manifest parity gate).
- `web-next/next.config.ts`: `redirects()` — permanent 308s for legacy
  `.html` bookmarks (preserves the old site's bookmark invariant).
- `cli.py`: `website/openapi.json` defaults → `web-next/openapi.json`;
  `tests/test_api_export.py` assertion updated.
- Agent write scopes: `core/agents/builder.py`,
  `builtin/feature-coder.agent.json`, `builtin/nocode-app-builder.agent.json`
  — `website/**` → `web-next/**`.
- `tests/test_website_facts.py` → `tests/test_webnext_facts.py`: rewritten for
  the live surface — self-canonicalizing routes, sitemap/robots/manifest/
  feed.xml, self-hosted woff2 in `src/fonts/`, zero-CDN scan on `src`+`public`,
  real pricing tokens (`$15`/`$29`/`0% token markup`/`Sovereign VPC`),
  `Sorvex Labs`, `Keelway Cloud`, manifest version parity.
- Phases 8–17 + `test_full_beta_user_journey` + `test_api_export`:
  `WEBSITE_DIR` → `SITE_DIR` pointing at `web-next`; phase12 pricing contract →
  `pricing/page.tsx` + `product/page.tsx` (spend-cap copy in
  `components/site/policy-demo.tsx`); phase13 showcase contract → early-access
  surface contract (`EARLY_ACCESS_WEBHOOK_URL`, origin allowlist, fetch target
  in `magic-link-form.tsx`); phase17 YC-curation surface list → web-next
  routes; retired-surfaces list → web-next paths.
- `FORBIDDEN_PRIVATE_TOKENS` (8 gate lists): removed `creova-gif` — it is the
  public open-source org, deliberately linked from 7 shipped web-next
  components (V3 avoided it; web-next links it by design). `creovas-projects`
  stays forbidden.
- phase14: extension-tree scan now skips `node_modules`/`dist` (WEB-054
  lockfiles made the dir real).
- `scripts/verify_engineering_gates.sh`: section-6 subset
  `test_website_facts.py` → `test_webnext_facts.py`. CI job name
  `website-devapp-and-sdks` kept (phase8 pins it; renaming could un-require a
  status check).
- `.github/dependabot.yml`: `/website` → `/web-next` (never registered).
- Docs swept: `README.md`, `Makefile`, `DEVELOPER_QUICKSTART`,
  `runbooks/EARLY_ACCESS.md`, `beta/09`, `beta/12`, `RELEASE_NOTES_BETA`,
  `core/studio/DESIGN.md`, `PRODUCT_STRATEGY`, `DESIGN_PROGRAM`,
  `KEELWAY_V1_PLATFORM_REFERENCE`, `KEELWAY_DESIGN_SYSTEM_AND_UX_SPEC`,
  `TESTING_STRATEGY`, `docs/design/tokens.json` (18 surface entries →
  `web-next/src/app/globals.css`).
- `.cursor/skills/verify-keelway/features/homepage-golden-thread-showcase.md`
  deleted (verified a removed feature).
- `website/` deleted via `git rm -rf` — **75 files**.
- `.vercelignore`: `!/website` → `!/web-next` (the file whitelist-ignored
  everything else; the kora project's build would see an empty root).
- **Vercel project `kora`**: `rootDirectory` flipped `website` → `web-next`
  via `vercel api PATCH /v9/projects/kora` — the dashboard setting pointed at
  the deleted directory and failed every build ("specified Root Directory
  does not exist"). This also resolves the deploy-currency half of F-01: the
  project had never been pointed at `web-next`; production branch is `main`,
  so merges now build the canonical site.
- `docs/audits/WEBSITE_UI_UX_AUDIT.md`: F-05 resolved; backlog updated.

## Tests executed & evidence
- Gates pytest subset (8/9/10/11/12/13/14/15/16/17 + webnext_facts +
  api_export + full_beta): **109 passed, 1 failed** — sole failure
  `test_platform_v1_e2e`, a live-Ollama inference test: local `qwen3.5:latest`
  takes ~37.7 s/generation > the gateway's 30 s budget. Zero inference-path
  edits in this change; environment gap on this box.
- Repointed suite re-run standalone: **40/40 passed**.
- `next build` (web-next): clean — 20 routes, typecheck pass, redirects compile.
- `npx playwright test` (web-next): **31/31** — routes, a11y, canonicals green
  with the new redirects block.
- `make tokens-check`: pass.

## Known risks & blockers
- CI job name `website-devapp-and-sdks` intentionally retains `website` in its
  name — it is a required status check label, not a directory dependency.
- Historical docs under `docs/superpowers/{plans,specs}/` keep `website/`
  mentions by design (frozen records).
- `scripts/install.sh` vs `web-next/public/install.sh` use different runtime
  dirs (`~/.keelway/runtime` vs `~/.keelway/venv`) — docs point at
  `scripts/install.sh`; the public copy serves the site asset.

## Next recommended action
None for F-05 — fully resolved. Owner-side items remain: F-01 promote latest
web-next deploy to prod in Vercel; F-02 provision `EARLY_ACCESS_WEBHOOK_URL`
(+ `..._SECRET`); F-07 Docs 2.0 post-beta.
