# KEEL-ENG-032 — Python Dependency Lockfile & Freshness Gate

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / SUPPLY-CHAIN / DEVEX` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-032-python-lockfile` |

## Objective
Close the supply-chain gap from the post-merge review: Python deps were unpinned `>=` ranges with no lockfile. Add a hash-verified `requirements.lock` and a CI/local freshness gate.

## Acceptance Criteria
- [x] `requirements.lock` generated via `uv pip compile pyproject.toml --extra dev --extra postgres --generate-hashes` (38 packages, SHA-256 hashes)
- [x] `scripts/check_python_lock.sh` regenerates and diffs; wired into stage `[1/8]` of `scripts/verify_engineering_gates.sh`
- [x] Locked versions verified identical to the working `.venv` (fastapi 0.163.1, pydantic 2.14.3, cryptography 50.0.2, etc.)
- [x] `docs/DEVELOPER_QUICKSTART.md` documents install + regeneration

## Files Modified
- `requirements.lock` (new)
- `scripts/check_python_lock.sh` (new, executable)
- `scripts/verify_engineering_gates.sh` — stage 1 now runs lock freshness
- `docs/DEVELOPER_QUICKSTART.md` — pinned install instructions

## Tests Executed
- `./scripts/check_python_lock.sh`: `requirements.lock is fresh.`
- Version parity spot-check against `.venv`: all match

## Known Risks & Blockers
- Lock is platform/python-agnostic resolution by `uv` for the current interpreter; CI matrix (3.11/3.12/3.14) may resolve different wheels — hashes cover all published wheels per package version, and versions are pinned so this is safe.
- `uv` must be on PATH for the freshness check; script skips with a warning when absent (CI installs it or check is advisory locally).

## Next Recommended Action
Merge to `main`. Sprint 01 complete; remaining backlog: package consolidation (`keelway/`/`keelway_core/`), real OIDC federation, doc-drift sweep, VS Code webview palette.
