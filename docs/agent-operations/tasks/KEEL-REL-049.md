# KEEL-REL-049 — Clean-Environment Install Verification

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / INSTALL / DEVEX` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-REL-049-install-verify` |

## Objective
Release blocker #1 (RELEASE_READINESS_2026-11-16): prove install→doctor→CLI works on a clean environment; fix dishonest install path.

## Findings & Fixes
- **`pip install keelway` fails** — package not on PyPI (`pip index versions` → no matching distribution). `install.sh` previously defaulted to it → silent broken path. Now fails closed with clear instructions unless `KEELWAY_SOURCE_DIR` or `KEELWAY_PACKAGE` is set.
- **`scripts/verify_install.sh`** (new): fresh venv → editable install → `keelway doctor --json` asserts HEALTHY → `harness agents detect` smoke. Verified live this session.
- **Doc drift fixed**: QUICKSTART claimed install.sh "clones the GitHub repo" — it never did; corrected to actual behavior.

## Evidence
- `./scripts/verify_install.sh` → `[OK] clean install verified` (venv Python 3.11.7, doctor HEALTHY, agents detect OK).
- Manual clean venv at `/tmp/keelway-install-test`: editable install + `keelway doctor --json` → `overall_status: HEALTHY`.

## Known Limits
- Setuptools warns about same-named package dirs during editable install (pre-existing packaging wart; non-blocking).
- `install.sh` curl-from-website path still requires user to set env vars — a git-based default needs a published package or public repo decision (founder).
- Website a11y/perf CI remains open (REL-052 backlog).

## Next Recommended Action
KEEL-REL-050 (`agents setup <host>` one-command hook install) or KEEL-REL-051 (`tape verify`).
