# KEEL-MOB-005 — Expo SDK 51 → 54 upgrade (RN 0.74.5 → 0.81.5, React 19)

- **Status**: READY_FOR_REVIEW
- **Agent**: Devin
- **Date**: 2026-11-23
- **Branch**: `feature/keel-mob-005-expo-sdk-54`

## Objective

Move the mobile app off Expo SDK 51 (EOL; pinned RN 0.74 whose native libs
are not 16KB-page aligned and whose `@expo/cli` carried the critical `tar`
advisory) to Expo SDK 54 — the SDK matching the installed Expo Go client and
the current React Native toolchain.

## Changes (`mobile/package.json` + both lockfiles)

| Package | Before | After |
|---|---|---|
| expo | ~51.0.0 | ~54.0.38 |
| react-native | 0.74.5 | 0.81.5 |
| react / react-dom | 18.2.0 | 19.1.0 |
| react-native-web | ~0.19.10 | ^0.21.0 |
| @expo/metro-runtime | ~3.2.3 | ~6.1.2 |
| expo-build-properties | ~0.12.5 | ~1.0.10 |
| expo-haptics | ~13.0.1 | ~15.0.8 |
| expo-linking | ~6.3.1 | ~8.0.12 |
| expo-local-authentication | ~14.0.1 | ~17.0.9 |
| expo-notifications | ~0.28.3 | ~0.32.17 |
| expo-secure-store | ~13.0.2 | ~15.0.8 |
| expo-status-bar | ~1.12.1 | ~3.0.9 |
| expo-system-ui | — | ~6.0.9 (new; required by `userInterfaceStyle: dark`) |
| @babel/runtime | — | ^7.29.0 (new; babel-preset-expo helper imports) |
| @types/react | ~18.2.79 | ~19.1.10 |
| typescript | ~6.0.3 | ~5.9.2 (the version Expo SDK 54 actually expects) |

All version selections came from `npx expo install --fix`, not hand-picked.

## Verification — device pass repeated on the new stack

Native dev client rebuilt on the Android emulator (Pixel_8_Pro, 16KB image):
Gradle 8.14.3, compileSdk 36, NDK 27.1.12297006, Kotlin 2.1.20 —
`BUILD SUCCESSFUL in 2m 7s`. Evidence: `/tmp/keelway-evidence-mob2/`.

- [x] PairScreen renders V3 grammar on SDK 54 — **and the 16KB
      compatibility dialog no longer appears** (RN 0.81 ships aligned libs)
- [x] Real `?pair=` pairing → Mission Control (`Hybrid` chip, live `Synced`)
- [x] Receipts `#1–#2` live from `/v1/phone/receipts`, `sealed` chips
- [x] Receipt detail + **on-device proof fold**: `✓ Signature verifies on
      device` — the pure-JS SHA-256 path verified under Hermes on RN 0.81
- [x] Stack cleanup via `control-keelway cleanup`; evidence preserved

## Automated

- `npm run typecheck` (tsc 5.9.3): clean
- `npm test` (bun test): 12 pass / 0 fail
- `npx expo-doctor`: 17/18 — only the dual-lockfile notice remains
  (package-lock.json + bun.lock are both tracked by repo convention)
- `npm audit`: **36 → 15 vulns, 0 critical** (was 1 critical `tar` via
  `@expo/cli`). Remaining highs: `postcss` + `image-size`, bundler-time deps
  of metro/metro-config — dev-machine only, fixed by future Expo releases.

## Incidental fixes required by the upgrade

- `@babel/runtime` added: Metro 500'd resolving
  `interopRequireDefault` without it under the new babel-preset-expo.
- `expo-system-ui` added: SDK 54 requires it for `userInterfaceStyle`.

## Follow-ups

- iOS device pass still untested (no iOS toolchain on this host).
- Expo Go path now *should* work (SDK 54 client installed) — dev-client
  remains the recommended path for native determinism.
