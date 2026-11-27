# KEEL-ENG-074 — Enterprise UI/UX audit, KDS assessment, token-drift fix

## Status: COMPLETED

## Scope
Evidence-based UI/UX audit of the dev-app against the enterprise directive
checklist; Keelway Design System (KDS) foundation assessment; fix confirmed
findings.

## Deliverable
`docs/audits/UI_UX_AUDIT.md` — baseline, KDS decision, findings register
(UX-001..008), checklist verdicts, competitor matrix, prioritized backlog.

## Code change
`dev-app/src/components/platform/FlightTapeScrubberAndRadar.tsx`,
`BidirectionalKflowStudioPanel.tsx`: 16 superseded teal/zinc literal colors →
maritime v3 token vars (`--accent`, `--fg-*`, `--bg-*`, `--accent-subtle`).
Fixes off-brand diagrams and their light-theme breakage (UX-001).

## KDS decision
Keep Radix + Tailwind + existing 3-layer tokens; reject shadcn/Base UI
migration — the gap is primitive coverage (4 components), not foundation.

## Evidence
- tsc --noEmit clean; vitest 130/130 green.
- axe coverage: 9 files assert toHaveNoViolations; reduced-motion guard and
  focus-visible verified in tokens.css; light+dark themes verified.
