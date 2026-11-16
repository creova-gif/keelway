# KEEL-ENG-036 — `core/config.py` No-Pydantic Fallback `default_factory` Fix

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / DEVEX / MINIMAL-ENV` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-036-config-fallback` |

## Objective
Fix the minimal-environment fallback in `core/config.py` so `Settings()` (and therefore `cli.py doctor`) works when pydantic/pydantic-settings are absent.

## Root Cause
The fallback `Field(default=None, description="")` shim did not accept `default_factory=`, so `Settings.database_url`'s `Field(default_factory=...)` raised `TypeError` at class definition time in environments without pydantic.

## Changes
- `core/config.py`: fallback `Field()` now accepts `default_factory` (evaluates it) and `**kwargs` for other pydantic-only arguments.
- `tests/test_config_fallback.py` (new): import-blocks `pydantic`/`dotenv`, reimports `core.config`, asserts `Settings()` resolves `database_url`, `env`, `port`, `default_local_model`.

## Acceptance Criteria
- [x] `Settings()` instantiates without pydantic installed
- [x] `cli.py doctor --json` runs cleanly in the project venv
- [x] Regression test passes; real pydantic path unaffected

## Tests Executed
- `pytest tests/test_config_fallback.py -q`: 1 passed
- `pytest tests/test_phase9_enterprise_identity_siem_metrics.py tests/test_platform_persistence_and_enterprise.py tests/test_config_fallback.py -q`: 11 passed
- `python cli.py doctor --json`: HEALTHY
- Import-blocked manual verification of fallback path: `database_url` resolves correctly

## Known Risks & Blockers
- None. Fallback remains a convenience shim; production deployments are expected to install locked deps (`requirements.lock`, KEEL-ENG-032).

## Next Recommended Action
Merged to `main`. See KEEL-SEC-037 for the OIDC federation-profile disclosure shipped alongside.
