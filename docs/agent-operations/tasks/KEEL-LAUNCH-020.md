# Task Specification: KEEL-LAUNCH-020

- **Title**: Phase 13 — Zero-Install Homepage Golden-Thread Studio Showcase (`/#studio-showcase`) & Official Signed `v1.1.0` GitHub Release
- **Status**: `VERIFIED_COMPLETE`
- **Assigned Agent**: Google Antigravity (`13A` Homepage Studio Showcase Lead, `13B` `v1.1.0` Release & Parity Lead)
- **Branch**: `main` (`v1.1.0`)

---

## 1. Scope & Strict File Ownership Boundaries

### Workstream 13A — Zero-Install Homepage Golden-Thread Studio Engine & Interactive Showcase (`website/`)
- `website/src/lib/goldenThreadShowcaseEngine.ts` *(new, < 280 lines)*
- `website/src/components/home/GoldenThreadStudioShowcase.tsx` *(new, < 460 lines)*
- `website/src/lib/analytics.ts` *(add 4 typed Golden-Thread funnel events)*
- `website/src/app/page.tsx` *(mount `<GoldenThreadStudioShowcase />`)*
- `website/src/components/layout/CommandPalette.tsx` *(add `"Try Golden-Thread Studio Showcase"` -> `"/#studio-showcase"`)*
- `website/src/app/api/search-index/route.ts` *(add Golden-Thread showcase item & fix `"$39 Pro"` -> `"$15 BYOM, $29 Pro"`)*

### Workstream 13B — Synchronized `v1.1.0` Release Metadata, OpenAPI Export, Changelog & Parity Suite
- `pyproject.toml`, `core/main.py`, `cli.py`, `core/platform/enterprise_identity_siem.py`, `sdk/typescript/package.json`, `website/package.json`, `Formula/keelway.rb`, `.github/workflows/release-artifacts.yml`, `CHANGELOG.md`
- `website/product-facts.json` & `website/public/product-facts.json` (`version: "1.1.0"`, `21` features)
- `website/openapi.json` & `website/public/openapi.json` (`info.version: "1.1.0"`, `273` paths)
- `tests/test_cli_init_and_banner.py`, `tests/test_phase7_packaging_and_sdk.py`, `tests/test_phase9_enterprise_identity_siem_metrics.py`, `tests/test_website_facts.py`, `scripts/verify_engineering_gates.sh`
- `tests/test_phase13_homepage_studio_and_release.py` *(new, < 320 lines)*
- `.cursor/skills/verify-keelway/features/homepage-golden-thread-showcase.md` *(new)*
