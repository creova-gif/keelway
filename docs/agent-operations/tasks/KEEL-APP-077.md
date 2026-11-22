# KEEL-APP-077 — Drawers conformance vs Paper 18.5 (`2WD-0`)

- **TASK ID**: KEEL-APP-077
- **STATUS**: READY_FOR_REVIEW
- **BRANCH**: `feature/keel-app-077-drawer-conformance`
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22

## Objective

Wire the two 18.5 drawers to the `2WD-0` artboard grammar — the last two
designed-but-unconformed surfaces in `SCREEN_INVENTORY.md` Phase 4.

## Deltas applied

### Review-changes drawer (`TasksDrawers.tsx` → `ReviewChangesContent`)

| Artboard 18.5 | Before | After |
|---|---|---|
| `N files · agent wrote` quiet right-status | top banner w/ totals | header rule: `N files · agent wrote` + totals `+A −D` |
| flat file rows `path … +N −N view diff` | boxed card per file, diff always inline | `divide-y` rows; per-file `+N −N`; `view diff`/`hide diff` disclosure (collapsed default per artboard); `Ask for changes` kept as ghost |
| footer: `Revert all` quiet-left · `Keep all` brass-right | actions at top; `Keep changes` primary + `Revert all` danger-ghost | footer row: Revert ghost-left, `Keep all` primary-right |
| footnote `keep/revert writes a receipt — reviewed changes are audited, not silent` | absent | added verbatim |

`ai` provenance badge per hunk retained; `kept/reverted` status banner retained.

### Live-execution drawer (`LiveExecutionDrawer.tsx`)

| Artboard 18.5 | Before | After |
|---|---|---|
| flat ledger rows, `mm:ss` leading | filled bordered chips (ochre/ok/danger bg) — same violation class APP-076 fixed in nav | `divide-y` ledger rows, timestamp leading `text-fg-dim`, tag + label text |
| accent only on `awaiting approval` gate row | filled ochre chip | flat row, `text-accent` label emphasis |
| footnote `same tape as Record — drawer is a lens on the ledger, not a second log` | absent | added verbatim under the log |

Deliberately kept: P-10 interactive checkpoint block (pointer-confirm approve/deny +
RBAC tooltip), status badge, run-id/workspace line, re-run control — richer than the
artboard but functional, not decorative.

## Verification

- `npm run typecheck` — clean
- `npm run test` — 24 files / 126 tests passed (updated one label assertion
  `Keep changes` → `Keep all`)
- `npm run build` — `core/dev_app_dist` regenerated
- Artboard evidence: `get_screenshot` on `2WD-0` (token hash `3cc7b891`, unchanged)

## Residual

None on drawers. The artboard's right-anchored chrome/dim is shell-owned
(`DevAppShell` review pane) and already conforms.
