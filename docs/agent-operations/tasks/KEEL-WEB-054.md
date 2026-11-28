# KEEL-WEB-054 — Website canonical fix + CI decoupling from legacy `website/`

## Status: COMPLETED

## Scope
Two audit items from `docs/audits/WEBSITE_UI_UX_AUDIT.md`: F-06 page metadata
(scope expanded on inspection — the real defect was a site-wide canonical bug)
and the F-05 residual part 1 (decouple CI from the deprecated `website/` app).

## Files modified
- `web-next/src/app/layout.tsx`: removed `alternates.canonical: "/"` — it was
  inherited by **every route**, so all 12 pages claimed the homepage as their
  canonical URL (subpage de-indexing risk).
- `web-next/src/app/page.tsx`, `product/page.tsx`, `offline/page.tsx`: new
  `metadata` exports — `/` canonicalizes to `/`; `/product` and `/offline`
  gained title + description + self-canonical (`/product` previously had none).
- `web-next/src/app/{about,blog,changelog,contact,docs,legal,pricing,sign-in,signup}/page.tsx`:
  `alternates.canonical` self-references added.
- `web-next/e2e/routes.spec.ts`: new `self-canonicalizes` assertion — every
  route's `<link rel=canonical>` pathname must equal its own path (31 e2e total).
- `sdk/typescript/package.json` + `package-lock.json`: `typescript@^6.0.3`
  devDependency — compiles itself, no longer borrows `website/node_modules`.
- `extensions/vscode-keelway/package.json` + `package-lock.json`: same devDep;
  `build` script repointed from `../../website/node_modules/.bin/tsc` to local
  `tsc`; `typecheck` script added. Zero runtime deps preserved both packages.
- `.github/workflows/ci.yml`: removed `website/` build/typecheck and e2e steps;
  SDK/extension compiles now `npm --prefix <pkg> ci` + `run typecheck`; npm
  cache-dependency-path and Playwright cache key repointed to the real
  lockfiles; Playwright cache restore moved before the install it serves.
- `scripts/verify_engineering_gates.sh`: tsc paths repointed to package-local
  toolchains (guarded as before).
- `website/README.md`: deprecation banner updated — app no longer runs in CI.
- `docs/audits/WEBSITE_UI_UX_AUDIT.md`: F-05/F-06 statuses + backlog re-sorted.

## Tests executed & evidence
- `npm run typecheck` (web-next, sdk/typescript, vscode-keelway): all clean
- `next build` (web-next): clean
- `npx playwright test e2e/routes.spec.ts`: **15/15**; full suite **31/31**
- `python3 yaml.safe_load(ci.yml)` + `bash -n verify_engineering_gates.sh`: valid
- `sdk/typescript` `npm test` unaffected (node --test, no deps); zero-runtime-dep
  invariant kept (devDependency only; `test_website_facts.py:212` still passes)

## Known risks & blockers
- `website/` directory itself remains — pytest drift gates
  (`test_website_facts.py`, `test_phase15/16/17_*website*`) pin its files;
  removal task must migrate or retire those first.
- Sibling PRs touching `website/` will still pass CI now that the app is no
  longer built — acceptable, the drift gates still guard its committed state.

## Next recommended action
Follow-up task: migrate the website drift gates to web-next (or retire), update
agent file scopes in `core/agents/builtin/*.agent.json`, then delete `website/`.
Owner-side: F-01 Vercel prod promotion + `EARLY_ACCESS_WEBHOOK_URL` remain.
