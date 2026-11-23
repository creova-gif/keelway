# KEEL-MOB-004 — RN 0.74.5 alignment + Android device verification pass

- **Status**: READY_FOR_REVIEW
- **Agent**: Devin
- **Date**: 2026-11-23
- **Branch**: `feature/keel-mob-004-device-verify`
- **Paper ref**: page 08 (mobile doctrine — pair, watch, receipts, disconnect)

## Objective

Close the last capability-bound item from the Paper 08 rollout: run the real
React Native mobile app on a device-class target against a live isolated
Keelway stack, exercising the full journey — pair → Mission Control →
receipts → on-device Merkle proof fold → disconnect.

## Changes

- `mobile/package.json`: `react-native` `0.74.1` → `0.74.5` — the Expo SDK 51
  expected version. This was a real runtime defect: the installed Expo Go
  client rendered the bundle and then died in its host (`UIManager` not
  initialized; version-check listed `react-native@0.74.1` mismatched against
  the expected `0.74.5`).
- `mobile/package.json` scripts: `expo start --android|ios` →
  `expo run:android|ios`. Expo Go provably cannot run this project on current
  Android (SDK 51 project vs SDK 54 client; even the matching 2.31.2 client
  crashes in its own host kernel on Android 16), so the honest dev path is a
  native dev client.
- `mobile/package-lock.json`: regenerated for the RN bump.
- `mobile/.gitignore`: ignore `android/` + `ios/` — `expo run:*` prebuild
  output (442MB generated tree) must never be committed; the project stays
  managed.

## Verification — live device pass (Android emulator, Pixel_8_Pro AVD)

Isolated verify-keelway stack on `127.0.0.1:50685`, own HOME/SQLite WAL;
native dev client built with JDK 21 / Gradle 8.8 / SDK 34 (BUILD SUCCESSFUL).
Evidence: `/tmp/keelway-evidence-mob/` (21 screenshots + logcat).

- [x] PairScreen renders V3 grammar on-device (canvas, brass mark/CTA,
      language picker EN/SW/FR/AR, `by Sorvex Labs`, honest setup copy)
- [x] Honest failure: expired pairing code → red "expired or already used"
      error, no fabricated success
- [x] Real pairing via `?pair=` link → Mission Control with `Hybrid` chip,
      live `Synced` timestamp
- [x] Receipts section lists live tape entries `#1–#5` with `sealed` chips
      (`/v1/phone/receipts` over `10.0.2.2` host loopback)
- [x] Receipt detail: exec / actor (`phone: android phone`) / proof sha256 /
      chain prev / sealed timestamp
- [x] **On-device proof fold**: "Verify proof on device" →
      `✓ Signature verifies on device` — the device fetched
      `/v1/audit/merkle/proof/5` and folded SHA-256 locally
- [x] Disconnect → returns to PairScreen (client-side session clear; server
      token remains valid — honest, no fake revoke)
- [x] Second-surface: read-only SQLite confirms `keelway_audit_events` seq 5 =
      `phone_paired` / actor `phone: android phone`; `keelway_api_tokens` row
      `phone` role, 30-day expiry, `revoked_at` NULL
- [x] Stack cleanup via `control-keelway cleanup`; evidence preserved

## Automated

- `npm run typecheck` (tsc): clean
- `npm test` (bun test): 12 pass / 0 fail

## Known issues / follow-ups

- `npm audit`: 36 vulns (1 critical: `tar@6.2.1` via `@expo/cli` — build-time
  extraction only, not shipped in the bundle; fix requires an Expo SDK
  upgrade). Not `audit fix --force`d — tracked for the SDK 5x upgrade lane.
- TypeScript `6.0.3` vs Expo SDK 51's expected `~5.3.3` (warning only;
  `moduleResolution: bundler` already keeps tsc green).
- RN 0.74 native libs are not 16KB-page-size aligned → Android shows a
  one-time compatibility notice on 16KB system images; app runs correctly.
  Resolves with the Expo SDK / RN upgrade lane.
- iOS device pass remains untested (no iOS toolchain on this host).
