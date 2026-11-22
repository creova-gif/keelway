# KEEL-MOB-003 — Offline read-only + biometric deny gate (Paper 08.1)

**Status**: READY_FOR_REVIEW
**Branch**: feature/keel-mob-003-offline-contract
**Paper source**: `Keelway — Brand Kit & Homepage` page 08, artboard 08.1
("What belongs on the phone")

## Scope

Two contract clauses on the RN bridge watch that were displayed but not
enforced in `MissionControlScreen.tsx`:

- **"offline = read-only — cached receipts stay readable; actions
  queue-never, they refuse"** — the screen already rendered
  `Offline — showing last known state` when a refresh failed, but every
  mutation surface still accepted taps. Offline, the approve/deny buttons
  and the Air-Gap switch fired a network call that failed *after* the
  biometric prompt — a refusal at the wrong layer.
- **"every approve/deny/kill-switch needs Face ID"** — `decide()` only ran
  `confirmLocally` for approvals; denials sealed a receipt with no local
  proof of person, which contradicts the gate grammar and is a swipe-risk.

## Changes

- `mobile/src/screens/MissionControlScreen.tsx`
  - `decide()`: early `if (!online)` refusal (`setNotice(t.offline)`,
    returns before the biometric prompt — no prompt for an action that
    cannot run).
  - `decide()`: `confirmLocally` now runs for both directions, with a
    direction-correct prompt (`t.authPrompt` / new `t.denyPrompt`).
  - `toggleAirGap()`: `!online` added to the early-return guard and to
    the switch's `disabled` + `accessibilityState.disabled`.
  - Approve/Deny `TouchableOpacity`s: `disabled` extended with `|| !online`.
- `mobile/src/i18n/index.ts`: `denyPrompt` in all four locales
  (en/sw/fr/ar) so the biometric sheet names the actual decision.

Deliberately unchanged: `verifyOnDevice` and `shareReceipt` stay enabled
offline — receipt reads, local SHA-256 proof folding, and native share
are all local operations, and 08.1 says cached receipts stay readable.

## Verification

- `npx tsc --noEmit` — clean (exit 0).
- `bun test` — 12/12 pass (`mobile api service`, `sha256 + merkle`).
- RN has no screen-level test harness; the refusal logic is a pure
  state guard reviewed against the Paper clause and the existing
  `!online` banner.

## Follow-ups

- 08.2A–C native screens exist in Paper; `MissionControlScreen` covers
  gate+watch+receipt in one scroll. A per-screen split is optional and
  not spec'd.
