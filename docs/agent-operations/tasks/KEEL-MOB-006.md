# KEEL-MOB-006 — Expo SDK 54 → 58 upgrade (RN 0.81.5 → 0.88.1, React 19.3)

- **Status**: READY_FOR_REVIEW
- **Agent**: Devin
- **Date**: 2026-12-13
- **Branch**: `feature/keel-mob-006-expo-sdk-58`

## Objective

Move the mobile app off Expo SDK 54 to SDK 58 as one coherent upgrade,
superseding dependabot PRs #273–275, which each bumped a single `expo-*`
package. Expo packages are version-locked per SDK — merging any of the three
piecemeal would leave the dependency set failing `expo install --check`.
Same sequencing precedent as KEEL-MOB-005 (SDK 51 → 54, PR #219).

## Changes (`mobile/package.json` + both lockfiles)

| Package | Before | After |
|---|---|---|
| expo | ~54.0.38 | ~58.1.0 |
| react-native | 0.81.5 | 0.88.1 |
| react / react-dom | 19.1.0 | 19.3.0 |
| @expo/metro-runtime | ~6.1.2 | ~58.0.17 |
| expo-build-properties | ~1.0.10 | ~58.0.12 |
| expo-haptics | ~15.0.8 | ~58.0.8 |
| expo-linking | ~8.0.12 | ~58.0.17 |
| expo-local-authentication | ~17.0.9 | ~58.0.3 |
| expo-notifications | ~0.32.17 | ~58.1.10 |
| expo-secure-store | ~15.0.8 | ~58.0.3 |
| expo-status-bar | ~3.0.9 | ~58.0.5 |
| expo-system-ui | ~6.0.3 | ~58.0.7 |
| expo-splash-screen | — | ~58.0.15 (new; splash config moved to plugin) |
| @types/react | ~19.1.10 | ~19.3.0 |
| typescript | ~5.9.2 | ~6.0.3 (the version Expo SDK 58 expects) |

All version selections came from `npx expo install expo@~58` followed by
`npx expo install --fix`, not hand-picked. The fixer used bun; both tracked
lockfiles (`bun.lock`, `package-lock.json`) were regenerated and are in sync.

## `app.json` changes

- `splash` top-level key **removed** — no longer allowed by the SDK 58
  config schema (expo-doctor flagged it). Equivalent config moved to the
  `expo-splash-screen` config plugin: `["expo-splash-screen",
  {"backgroundColor": "#0B0F14"}]`.
- `expo-status-bar` added as an explicit config plugin by the installer.
- `expo-splash-screen` added as a config plugin (see above).

## Verification

No device or simulator toolchain exists on this host, so verification is
the bundler/typecheck/test path — same caveat as MOB-005's iOS gap:

- `npx tsc --noEmit` (typescript 6.0.3): clean
- `bun test`: 12 pass / 0 fail (one benign ETIMEDOUT reading the parent
  worktree's tsconfig.json — pre-existing, unrelated)
- `npx expo export --platform web`: clean — 221 modules bundled
- `npx expo export --platform ios`: clean — 624 modules, 1.6 MB Hermes
  bytecode bundle; exercises the real RN module graph (no react-native-web)
- `npx expo-doctor`: 19/20 — only the dual-lockfile notice remains
  (package-lock.json + bun.lock are both tracked by repo convention).
  Fixed during this pass: the `splash` schema violation and a duplicated
  `expo-constants@58.0.16` (stale nested copy under `expo-asset`;
  resolved by clean node_modules reinstall).
- `npm audit`: 9 moderate vulns, 0 high/critical (improvement on the
  pre-upgrade count).

## Supersedes

- Dependabot PR #273 (expo-haptics bump)
- Dependabot PR #274 (expo-linking bump)
- Dependabot PR #275 (expo-notifications bump)

Close all three after this merges — every expo package is already at its
SDK-58-pinned version here.

## Follow-ups

- **Device pass unverified**: no Android emulator or iOS toolchain on this
  host. The MOB-005 device checklist (pairing → Mission Control → receipts
  → on-device proof fold) should be repeated on a real device/dev-client
  build before calling the runtime verified — runbook below.
- Expo Go / dev-client behavior under SDK 58 unverified — dev-client
  remains the recommended path for native determinism.
- Engines note: SDK 58 requires Node ^22.13 or >=24.3 (host: v24.11.1).

## Device Verification Runbook (repeat of MOB-005's pass, SDK-58 deltas)

Prereqs: Android emulator (16KB-page image, e.g. Pixel_8_Pro API 36+) or
physical device; `keelway dev --host 0.0.0.0` running on the LAN;
`keelway mobile pair` for a single-use pairing link.

```bash
cd mobile && bun install
npx expo run:android          # dev-client build (Gradle + NDK toolchain)
# or: npx expo start          # Expo Go path — must be an SDK-58 client
```

- [ ] **Boot + splash**: app cold-starts; splash shows `#0B0F14`
      background (verifies the `expo-splash-screen` plugin migration —
      the top-level `splash` key no longer exists in the SDK 58 schema)
- [ ] **PairScreen** renders V3 grammar; 16KB compatibility dialog still
      absent (RN 0.88 keeps MOB-005's aligned libs)
- [ ] **Real pairing**: paste `?pair=` link → spends code once at
      `POST /v1/auth/pair` → lands on Mission Control (`Hybrid` chip,
      live `Synced`); also probe `keelway://pair?link=<url-encoded>`
      deep link (expo-linking 58)
- [ ] **SecureStore persistence**: kill + relaunch — session survives
      (token stays in OS keychain; no re-pair needed)
- [ ] **Biometric gate**: approve a pending step — Face ID / fingerprint
      prompt fires with the infoPlist usage strings
      (`NSFaceIDUsageDescription`); device-passcode fallback path works
- [ ] **Receipts**: `#1..#n` live from `/v1/phone/receipts`, `sealed`
      chips; receipt detail → on-device proof fold →
      `✓ Signature verifies on device` (pure-JS SHA-256 under Hermes on
      RN 0.88)
- [ ] **Offline behavior**: airplane mode → last known state stays on
      screen, poll backs off to 30 s, recovers on reconnect
- [ ] **iOS pass** (separate host): same checklist via
      `npx expo run:ios` on a physical device or simulator —
      `NSAllowsLocalNetworking` covers LAN http
- [ ] Cleanup: `control-keelway cleanup`; preserve evidence under
      `/tmp/keelway-evidence-mob6/`
