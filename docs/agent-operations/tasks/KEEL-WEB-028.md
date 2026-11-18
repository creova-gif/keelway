# KEEL-WEB-028 — Brand/UI Refresh: Monochrome Zinc, BrandMark & PWA/SEO

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `WEBSITE / UX / DEV-APP` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `feature/KEEL-WEB-028-brand-refresh` |
| **Head Commit** | `ef7c936` |

## Objective
Ship the brand/UI refresh reconstructed from the interrupted prior session: monochrome zinc palette with teal reserved for the K mark/CTA, shared `BrandMark` component, PWA manifest + `feed.xml` SEO surfaces, and token/component propagation across `website/` and `dev-app/`.

## Acceptance Criteria
- [x] Monochrome zinc palette replaces legacy colors; teal limited to K mark/CTA and verified/local states
- [x] `BrandMark` component shared by website and dev-app shells
- [x] `manifest.ts` and `feed.xml/route.ts` added; favicons updated
- [x] All touched surfaces consistent; no leftover old palette values
- [x] Website + dev-app typechecks pass
- [x] Website + dev-app production builds pass
- [x] Dev-app unit tests pass
- [x] `tests/test_website_facts.py` focused test passes

## Files Modified
- `dev-app/src/components/ui/BrandMark.tsx` (new), `dev-app/src/components/shell/DevAppShell.tsx`, `dev-app/src/components/platform/*`, `dev-app/src/styles/tokens.css`
- `website/src/components/ui/BrandMark.tsx` (new), `website/src/app/manifest.ts` (new), `website/src/app/feed.xml/route.ts` (new)
- `website/src/app/{layout,globals,brand/docs/marketplace/pricing}/*`, `website/src/components/**` (~30 components), `website/favicon.svg`, `website/public/favicon.svg`, `web-console/index.html`, `DESIGN.md`, `tests/test_website_facts.py`

## Tests Executed
- Website typecheck: pass
- Dev-app typecheck: pass
- Website production build: pass
- Dev-app production build: pass
- Dev-app unit tests: pass
- `pytest tests/test_website_facts.py` (focused): pass

## Known Risks & Blockers
- None. Changes are presentation-layer only; no API, governance, or security-surface modifications.

## Next Recommended Action
Merge `feature/KEEL-WEB-028-brand-refresh` to `main` after review; continue product backlog per `docs/agent-operations/ACTIVE_TASKS.md` §3.
