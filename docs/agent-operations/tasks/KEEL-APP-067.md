# KEEL-APP-067 — Settings Network & Egress deep-dive (Paper 17.5 `2JZ-0`)

## Status
READY_FOR_REVIEW

## Surfaces wired
1. **Air-gap preview disclosure** under posture card — honest consequences: `cloud connectors → refused`, `telemetry → buffered local`, `models → OpenCore only`. Label flips "Preview →" (unlocked) / "Active — enforcing" (locked).
2. **Recent egress decisions** section — rows fed by real `audit.endpoints` (host · purpose · N calls · bytes / "bytes unmeasured"). Empty: "No cloud endpoints recorded — egress ledger is empty." Error path references the telemetry error honestly.
3. **"Open full audit in Record"** ghost action — new `onOpenRecordAudit` prop through `SettingsWorkspace` → `handleSelectPlatformView("security")` (the Record surface).

## Verified
- `tsc --noEmit` clean (fixed `tertiary`→`ghost` variant)
- `vitest run`: 24 files / 120 tests pass incl. axe gates
- `vite build` green; `dev_app_dist` regenerated

## Next
KEEL-APP-068: light-panel details (17.6 `2LS-0`), then P-10/Tasks card (18.1).
