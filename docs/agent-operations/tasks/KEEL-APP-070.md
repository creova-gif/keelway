# KEEL-APP-070 — Palette P-10 rank fix + Phase-4 live verify pass

## Status
READY_FOR_REVIEW — code delta verified on live isolated stack.

## Delta
`CommandPalette.tsx` mixed mode: when a `needs_approval` task survives the filter, the
Tasks group renders **before** Commands — pending human gates rank first per Paper `18.3`
("P-10 actions rank first, always"). No pending gate → Commands keep default first position.
Palette still never executes approvals; the entry navigates to the gate only.

## Live verification (verify-keelway, isolated stack :59565)
- Onboarding step 1: 3 sovereign-default cards + `unmeasured`/`Offline (setting)` honesty markers
- Onboarding step 2: `/v1/system/doctor` live checks vs isolated DB (SC-7 5/5, honest `NO_TRUSTED_KEY` + `bubblewrap_available=false` warnings)
- Settings → Permissions: `12 manifests` quiet count, immutable P-10 region
- Settings → Models: `127.0.0.1 · loopback only`, `· measured`, `5 local weights`, `Simulated weights` markers
- Settings → Network: `Egress measured`, air-gap Preview disclosure (`refused`/`buffered`/`OpenCore only`), `Recent egress decisions`, `Open full audit in Record` → Security view ✓
- Palette fix: `group "Tasks"` first, first option = needs-approval gate, selected by default
- Evidence: `/tmp/keelway-evidence-phase4/` (11 PNG + ARIA snapshots)

## Tests
- `npx vitest run`: 24 files, 120/120 (incl. new first-option ordering assertion + axe gates)
- `tsc --noEmit` clean; `npm run build` green; `core/dev_app_dist` regenerated
