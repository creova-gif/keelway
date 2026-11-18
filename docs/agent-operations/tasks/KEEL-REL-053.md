# KEEL-REL-053 — Simulated-Model Disclosure in UI

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / UI / HONEST-CLAIMS` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-REL-053-simulated-badges` |

## Objective
Release gap: `keelway-*` registry models serve canned mock replies but UI surfaces labeled them "(Local)" / real weights with no simulated disclosure.

## Implementation
- **API**: `/v1/opencore/weights` items now carry `simulated: true` (all canonical manifests are mock-served until KEEL-PROD-041 resolves).
- **Dev-app (Studio)**: `OpenCoreWeightItem.simulated` typed + decoded; fallback fixtures flagged; `SettingsModelsPanel` weight rows render a "Simulated weights — not real model" badge; `AgentsWorkspaceView` model selectors relabeled `(Simulated)` and show a `simulated` SemanticBadge for `keelway-*` selections.
- **Website**: `CatalogModel.simulated` flag added; the four `isOpenCoreSuite` entries (`keelway-core/coder/reasoning/nano`) flagged; `ModelExplorer` renders an amber `SIMULATED` chip alongside `KEELWAY OPENCORE`.

## Evidence
- `pytest tests/test_opencore.py` — 7 pass (new assertion: all manifests `simulated: true`).
- `tsc --noEmit` clean in `website/` and `dev-app/`.
- `vitest run settings-and-app.test.tsx` — 10/10 pass incl. axe-core WCAG check.

## Honest Limits
Backend `simulated` is hardcoded `true` for the canonical catalog — correct today (no real keelway-* weights exist), must flip per-manifest when KEEL-PROD-041 ships real weights. Deeper finding documented: canonical manifests contain placeholder SHA-256 checksums and unpublished `weights.keelway.ai` URIs — part of the PROD-041 decision.

## Next Recommended Action
Website a11y/perf CI; Studio empty/error-state audit; KEEL-PROD-041 weights decision.
