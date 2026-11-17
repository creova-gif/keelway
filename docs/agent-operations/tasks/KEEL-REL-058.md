# KEEL-REL-058 — Release hardening: CI secret gate, installer uninstall/rollback, tested model compatibility matrix

- **TASK ID**: KEEL-REL-058
- **TASK TITLE**: CI gitleaks gate + installer `--uninstall`/`--purge`/`KEELWAY_GIT_REF` + `MODEL_COMPATIBILITY_MATRIX.md`
- **CURRENT STATUS**: COMPLETED
- **LAST AGENT**: Devin
- **DATE**: 2026-11-17
- **BRANCH**: `main`
- **HEAD COMMIT**: (this commit)

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] CI secret-scanning gate (KEEL-SEC-057 follow-on) — gitleaks runs on the tracked tree in every Python matrix job; fails the build on a new committed secret
- [x] Installer uninstall — `--uninstall` removes runtime venv/clone + CLI symlink, preserves `~/.keelway` data; `--purge` opts into data removal; `--purge` without `--uninstall` fails usage-error
- [x] Installer rollback path — `KEELWAY_GIT_REF=<tag-or-branch>` pins the clone (tag/branch names only with `--depth 1`)
- [x] Tested model compatibility matrix (Master Prompt Phase 6) — `docs/architecture/MODEL_COMPATIBILITY_MATRIX.md` marks VERIFIED/IMPL/GATED/NO per cell with evidence

## WORK COMPLETED & FILES MODIFIED

- `.gitleaks.toml` (new): extends default ruleset; secret-value allowlist for obvious synthetic markers (sequential hex, `example`/`test`/`placeholder`/`rotated`/`ephemeral`/`kw_live_`/`sk-live`/`whsec`, `AKIAABC…`, `ghp_` fixture shapes) + path allowlist for generated/vendored trees (`core/studio/assets`, `core/dev_app_dist`, `web-console/dist`, `node_modules`, `tests/test_redact.py` canonical scrubber fixtures)
- `.github/workflows/ci.yml`: `Secret scan (gitleaks)` step after `Lint check` — downloads gitleaks `8.28.0` linux_x64 tarball pinned by sha256 (`a65b5253…840eb`), runs `gitleaks dir --config .gitleaks.toml --redact=90 .` (~3 s)
- `website/public/install.sh`, `website/install.sh`, `scripts/install.sh`: `--uninstall`, `--purge`, `--dry-run` uninstall plans, `KEELWAY_GIT_REF` clone pinning, help text updated; bash installer also emits JSON for uninstall
- `docs/architecture/MODEL_COMPATIBILITY_MATRIX.md` (new): provider×capability, alias×backend, third-party-agent, and cross-cutting tables with evidence links and re-verification commands

## TESTS EXECUTED & EVIDENCE

- `gitleaks dir` on repo: **88 tracked-file findings → 0** after allowlist; 12 remaining hits are untracked local files (`.env`, `website/.env.local`, `.next/` build cache) — never present in a CI checkout
- `gitleaks git` (history): 95 findings, all classified synthetic (test fixtures, demo literals already remediated in KEEL-SEC-057, vendored monaco)
- `scripts/install.sh --uninstall --dry-run` + `--purge` + `--purge`-alone→exit 2 verified
- `sh website/public/install.sh --uninstall` real round-trip: fake venv+symlink removed, data dir preserved — ROUND-TRIP OK
- `sh -n`/`bash -n` syntax checks on all three installers: OK
- `pytest tests/test_phase7_packaging_and_sdk.py tests/test_website_facts.py`: **17 passed**
- `test_website_facts` customer-file bearer/token guard still passes — installers remain clean

## KNOWN RISKS & LIMITS

- Gate scans the *tracked tree* per commit — history findings pre-allowlist are documented above, not retro-baselined
- Allowlist value markers are intentionally obvious; a hypothetical real key containing e.g. `test` or `012345` would be exempt — accepted trade-off, markers are placeholder-shaped
- `KEELWAY_GIT_REF` accepts branch/tag names (not arbitrary SHAs — `--depth 1` limitation); rollback requires a published tag
- `website/install.sh` and `website/public/install.sh` are near-parallel scripts; keep in sync when editing (no sync test exists)
- gitleaks binary version pinned in workflow (`GL_VER` + `GL_SHA256`) — bump together

## NEXT RECOMMENDED ACTION

- Verify the new CI step on the push that lands this commit
- Mark the GitGuardian incident resolved in the dashboard (KEEL-SEC-057)
- Publish a `v*` git tag when a release is cut so `KEELWAY_GIT_REF` rollback has a target
