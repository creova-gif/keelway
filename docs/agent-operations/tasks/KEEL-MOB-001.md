# KEEL-MOB-001 — V3 brand kit on the RN mobile app (Paper p-8-0)

**Status**: READY_FOR_REVIEW
**Branch**: feature/keel-mob-001-v3-mobile-theme
**Paper source**: `Keelway — Brand Kit & Homepage` page `08 - Mobile`, artboards 08.1 + 08.2

## Scope

Paper 08 frames mobile as "the bridge watch, not the engine room": gates,
receipts, task watch on the phone; authoring stays desktop. The Expo app
already implements the doctrine (paired device token, biometric-gated
approve/deny, run watch, air-gap toggle) but was on the pre-V3 palette
(teal #2DD4BF / amber #F5B547 / ink #0B0F14).

This task ports the V3 grammar — palette, gate-card detail block, watch
status chips, mono micro-labels — onto the existing screens. No behavior
change to pairing, biometric confirm, or the API client.

## Changes

- `mobile/src/theme/index.ts`: V3 canonical tokens — canvas #08090A,
  rgba surfaces, brass accent #C9A45C (+accentInk/Wash/Deep), ink/muted/dim
  fg ramp, success #6FAE8E, error #B0564E, info #6F87A3.
- `App.tsx`, `PairScreen`, `LanguagePicker`, `MissionControlScreen`: token
  renames (ink→canvas bg, text→ink fg, teal+amber→accent, danger→error,
  ok→success) and old rgba washes remapped to accentWash.
- `MissionControlScreen` gate card (08.2A): mono micro-eyebrow
  `GATE · <task_id> · NOW`, hairline detail block with `action`/`proof`
  rows, `proof — sealed either way` in accent, footer
  `BIOMETRIC REQUIRED · SEALED AS RECEIPT`.
- Watch rows (08.2B): status chip colors — pending approval → `gated`
  brass, terminal-success statuses → `sealed` green, denied/failed → error
  red, else info.
- `mobile/src/i18n/index.ts`: 8 new strings × 4 locales (en/sw/fr/ar).
- `mobile/tsconfig.json`: `moduleResolution: bundler` + `types: ["bun"]` —
  repairs the typecheck broken by the TS 6.0.3 bump (#149); expo base still
  ships `node` resolution which TS6 rejects.

## Verification

- `npm run typecheck` (tsc 6.0.3): clean — was failing before this change
- `bun test`: 10/10 green
- NOT verified on device/simulator — layout values follow the artboard
  grammar but no runtime screenshot exists. Device QA is the follow-up.

## Follow-ups

- 08.2C receipt screen: on-device merkle proof verify + copy hash —
  needs `/v1/audit/merkle/*` consumption + live-studio verification.
- Device/simulator visual pass (expo run) — no simulator executed here.
