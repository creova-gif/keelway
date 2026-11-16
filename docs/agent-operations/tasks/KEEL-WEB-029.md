# KEEL-WEB-029 — Post-Merge Brand Polish: A11y, Token Drift & Dead-Code Sweep

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `WEBSITE / UX / DEV-APP / A11Y` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-WEB-029-brand-polish` |

## Objective
Resolve the medium/low findings from the post-merge review of KEEL-WEB-028 (`4b70bf8`): ARIA labeling on `BrandMark` lockups, leftover legacy amber/slate values in `web-console`, hardcoded dark-theme teal accents, raw Tailwind red classes bypassing `fault` tokens, stale Monaco theme color, and dead `.chip-amber` CSS.

## Acceptance Criteria
- [x] `BrandMark` (website + dev-app): `aria-label` is exposed via `role="img"` on the lockup wrapper; inner SVG is `aria-hidden` whenever the wordmark is rendered (no double naming)
- [x] `web-console/index.html`: no `rgba(245,181,71,*)` amber tints, no `#F5B547`/`#CBD5E1` literals; palette comment updated
- [x] `accent-[#2DD4BF]` hardcodes replaced with `accent-teal-accent` (theme-aware)
- [x] `P10InteractiveDeck` raw `red-*` classes migrated to `fault`/`fault-surface` semantic tokens
- [x] Monaco `keelway-dark` theme `editor.background` aligned to `#09090b`; test updated
- [x] Dead `.chip-amber` CSS removed
- [x] `GoldenThreadJourneyBar` warm-ochre glow rgba replaced with zinc
- [x] Website + dev-app typechecks pass
- [x] Website + dev-app production builds pass
- [x] `files-record-settings` vitest suite passes (11/11, incl. axe)
- [x] `tests/test_website_facts.py` passes (11/11)

## Files Modified
- `website/src/components/ui/BrandMark.tsx` — `role="img"` on labeled lockup wrapper
- `dev-app/src/components/ui/BrandMark.tsx` — mirrored aria-hidden/label logic + wrapper role
- `web-console/index.html` — zinc rgba tints, `var(--muted)` pre color, option label, palette comment
- `website/src/components/pricing/PricingTiers.tsx`, `home/EarlyAccessForm.tsx`, `governance/RoutingSimulator.tsx` — `accent-teal-accent`
- `website/src/components/home/P10InteractiveDeck.tsx` — `fault` token migration
- `website/src/app/globals.css` — removed dead `.chip-amber`
- `dev-app/src/components/platform/GoldenThreadJourneyBar.tsx` — zinc glow
- `dev-app/src/components/screens/FilesWorkspace.tsx`, `dev-app/src/__tests__/files-record-settings.test.tsx` — Monaco bg `#09090b`
- `core/dev_app_dist/` — rebuilt bundle (committed build artifact convention)

## Tests Executed
- `npx tsc --noEmit` (website): pass
- `npx tsc --noEmit` (dev-app): pass
- `npm run build` (website): pass
- `npm run build` (dev-app): pass (regenerates `core/dev_app_dist`)
- `npx vitest run src/__tests__/files-record-settings.test.tsx`: 11 passed
- `.venv/bin/pytest tests/test_website_facts.py -q`: 11 passed

## Known Risks & Blockers
- `dev-app` dark `--status-warning` and `--status-running` remain visually near-identical zinc values (intentional monochrome direction; differentiation rests on labels/icons). Deferred as a design-token decision, not a defect.
- `docs/decisions/ADR-UI-001` and `docs/handoff/assets/brand-direction-v0.2.html` still reference the pre-refresh palette — documentation drift, non-blocking.
- `extensions/vscode-keelway` webview CSS remains on the legacy slate palette — separate surface, out of scope.
- **Security note (not fixed here):** `core/platform/signing.py::get_sorvex_first_party_keypair` derives the first-party Ed25519 seed from a public constant — anyone can reproduce the "Sorvex Labs" signing key. Acceptable only while first-party manifests are self-issued seed data; must be replaced with a managed key before any multi-publisher marketplace trust boundary ships. Tracked as backlog item.

## Next Recommended Action
Merge to `main`; schedule KEEL-SEC task for deterministic first-party signing key remediation before marketplace GA.
