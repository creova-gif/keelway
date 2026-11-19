# KEEL-APP-043 — Dev App P3: files/tree Decoder Fix, Honest Error Labels, Card-in-Card Flattening

- **TASK ID**: KEEL-APP-043
- **TASK TITLE**: `/app` P3 de-noising — fix files/tree decode contract mismatch, honest API error labels, flatten nested cards
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-19
- **BRANCH**: `feature/keel-app-043-denoise-and-decoder-fix`
- **BASE**: `main`

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] Root-caused `API error: /v1/files/tree (200)`: server returns `{root, name, tree: <single root node>}`; `decodeFilesTree` only accepted `raw.tree` as an array → decode error → 200 rendered in red as an API failure
- [x] `decodeFilesTree` now decodes a single-node `tree` object: directory root → returns `children` (matches flat top-level `WorkspaceFileNode[]` shape of `getFallbackFilesTree`); file → `[node]`
- [x] Status-bar error label now encodes error kind: `(404)`/`(500)` for HTTP errors, `(decode)` or `(network)` otherwise — a bare `(200)` can never render as an error again
- [x] Targeted test added: `fetchFilesTree` against the real live-server envelope (`{root, name, tree: {...}}`) in `tokens-and-badges.test.tsx`
- [x] Card-in-card flattened (brand: surface tint, not stacked outlines): Automation DAG nodes, execution-trace log, GPU cluster nodes; Security evaluator checkbox block + control list rows — inner `border` dropped, `bg-canvas` recess kept
- [x] Chip audit: `SemanticBadge` kinds already drive all visible status chips; remaining `rounded-xs border` hits are form controls/list rows/data chips (paths, counts) — no fake-status chips found; no mass rewrite warranted

## FILES MODIFIED

- `dev-app/src/lib/apiDecoders.ts`: `decodeFilesTree` single-root-node branch
- `dev-app/src/components/shell/StatusBarEgress.tsx`: error label shows kind for non-HTTP errors
- `dev-app/src/components/platform/AutomationAndOpsViews.tsx`: 3 inner cards → recessed `bg-canvas` (no border)
- `dev-app/src/components/platform/SecurityWorkspaceView.tsx`: 2 inner blocks → recessed `bg-canvas` (no border)
- `dev-app/src/__tests__/tokens-and-badges.test.tsx`: live-envelope `fetchFilesTree` case
- `core/dev_app_dist/`: rebuilt via `npm run build` (tsc clean)

## TESTS EXECUTED & EVIDENCE

- `npx vitest run` in `dev-app`: **111 passed (23 files)** incl. new envelope case + axe accessibility gate
- `npm run build` (tsc --noEmit && vite build): clean
- verify-keelway isolated stack (port 53823): `/tmp/keelway-evidence-p2/p3-*.png` — IDE status bar shows NO error (previously `API error: /v1/files/tree (200)`); Files view honestly reports empty workspace; real `404` on `files/content` renders as `(404)`; Automation DAG nodes + Security evaluator flattened

## KNOWN RISKS & BLOCKERS

- Note: P3 work initially built on the stale P1 branch `cae8754` (parallel-agent branch churn); changes were carried onto `main` (post-#98) and dist rebuilt — first p3 screenshot showing old chrome was a stale-bundle artifact, resolved
- Narrow-width verification relies on `flex-wrap` (no viewport resize in control script); mobile companion path untouched
- Decorative-chip *volume* inside views (many SemanticBadges per card) is a per-view IA question — deferred to future per-view passes, not a token/structure fix

## NEXT RECOMMENDED ACTION

PR → merge. Remaining audit items: per-view information density passes; task/agent sidebar as primary surface (Conductor signal); `llms.txt`/agent-readable docs surface.
