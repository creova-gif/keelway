# KEEL-WEB-040 — /docs Route Resurrected as Brand-Native Docs Index

- **TASK ID**: KEEL-WEB-040
- **TASK TITLE**: Restore `/docs` as a Maritime Instrument docs index linking to canonical repo documentation
- **CURRENT STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-web-040-docs-index`
- **BASE**: `main`

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] New `/docs` page: "Everything is on the record." — 4 groups (START, ARCHITECTURE, OPERATE, PRODUCT & AGENTS), 15 rows on hairline rules, brass group labels, mono arrows
- [x] Every link verified against the repo filesystem before inclusion (GitHub blob URLs; `/install.sh` served locally)
- [x] Header nav gains Docs (Product / Pricing / Docs / Changelog / About); footer unchanged
- [x] `sitemap.ts` ROUTES += `/docs`; `/docs.html` legacy redirect repointed changelog → `/docs`
- [x] `tests/test_website_facts.py` updated (redirect dest, route file, sitemap row)

## FILES MODIFIED

- `website/src/app/docs/page.tsx`: new
- `website/src/components/layout/Header.tsx`, `website/src/app/sitemap.ts`, `website/next.config.ts`, `tests/test_website_facts.py`

## TESTS EXECUTED & EVIDENCE

- `npm run build`: clean, /docs statically generated
- `pytest tests/test_website_facts.py tests/test_phase13_homepage_studio_and_release.py`: `7 passed`
- Playwright 375px + 1440px: 0px overflow; full-page screenshot reviewed

## KNOWN RISKS & BLOCKERS

- None — links point at repo files that exist on `main` today; a docs IA overhaul (rendered docs site) is future work if wanted

## NEXT RECOMMENDED ACTION

PR → merge → prod verify.
