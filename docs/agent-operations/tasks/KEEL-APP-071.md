# KEEL-APP-071 — About & updates section (Paper `19.4`, `35L-0`)

## Status
READY_FOR_REVIEW

## Delta
`SettingsGeneralPanel` gains an "About & updates" section per the 19.4 artboard's
"About dialog is a trust surface" contract — version, channel, signature/SBOM/runtime
state as **live reads**, never claimed:

- `Keelway` → real `v{package.json version}` + honest `dev channel` (not "stable")
- `Update channel` → `none configured — dev app` (no fabricated update row; the
  artboard footer ships verbatim: "Unverified updates are refused — no 'trust anyway' path")
- `Runtime` → `FastAPI + SQLite WAL · tape chain {verified · N entries | broken at seq | checking… | unavailable}` via `/v1/audit/verify`
- `SBOM` → `{format} · {N} components` via `/v1/sbom`

Injected `verifyChainFn`/`fetchSbomFn` props preserve the testability pattern.
First-run auth cards from the same artboard deferred: `verifyScopedKey` exists but a
pairing modal needs a designed first-run entry point — separate increment.

## Tests
- 24 files, 120/120 vitest (new assertions: dev channel, honest update row, live chain + SBOM)
- `tsc --noEmit` clean; build green; `core/dev_app_dist` regenerated
