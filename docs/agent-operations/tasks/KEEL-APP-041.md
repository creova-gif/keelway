# KEEL-APP-041 — Dev App Maritime Instrument Token Retheme (P1)

- **TASK ID**: KEEL-APP-041
- **TASK TITLE**: Retheme `/app` dev surface to Maritime Instrument via `tokens.css` semantic restoration
- **CURRENT STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-app-041-maritime-retheme`
- **BASE**: `main`

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] Teal `#2dd4bf` accent → binnacle brass `#c9a45c` (all ~290 `teal-accent` usages flip via Tailwind token mapping — zero component edits)
- [x] Accent decoupled from success: `--status-ok` → starboard green `#6fae8e`; `--status-running` → flag blue `#6f87a3`; `--red-danger` → port red `#b0564e`
- [x] `--attn-ochre` restored from dead-white `#e4e4e7` to brass — `needs-approval`/P-10 gate states render brass (brass = attention/meaning)
- [x] `--status-warning` → brass (brand: warning shares accent)
- [x] Hairline borders `white/6` & `white/12` (was `#27272a`/`#3f3f46`); fog-lift surfaces `white/4` & `white/8`; canvas `#08090a`; focus ring brass
- [x] Inter geometric OpenType features `cv01`+`ss03` enabled (Linear spec)
- [x] Light theme remapped in parallel (deep brass `#a8854a`, deep starboard `#3d7a5c`, deep port `#94392f`, deep flag `#4a6480`)

## FILES MODIFIED

- `dev-app/src/styles/tokens.css`: 32 dark + 18 light token remaps + font-feature-settings
- `core/dev_app_dist/`: rebuilt via `npm run build` (tsc clean)

## TESTS EXECUTED & EVIDENCE

- `npx vitest run` in `dev-app`: **117 passed (24 files)** incl. axe 0-violation gate
- `npm run build`: clean
- verify-keelway isolated stack (port 49948): all 10 views screenshotted after retheme — `/tmp/keelway-ux-evidence/after/view-*.png`; brass carries P-10 gates, golden thread, primary CTAs, provenance chips; PASS/verified = starboard; Deny = port red

## KNOWN RISKS & BLOCKERS

- Brass inherited all decorative teal usages — "brass rare" NOT yet achieved; P3 per-view de-decoration is follow-up
- 4-row chrome stack + status-bar `API error: /v1/files/tree (200)` misdisplay remain — P2/P3 scope
- Competitor research (Linear/Conductor/Factory/Cognition CSVs + docs) confirms stack + dark high-density approach is industry-consistent; no architecture change needed

## NEXT RECOMMENDED ACTION

PR → merge → then evaluate P2 (chrome consolidation: 4 rows → ≤2) on the rethemed screenshots.
