# KEEL-ENG-033 — ADR-0042 Phase 1: Migration-Check Import Census

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / CONSOLIDATION / DEVEX` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-ENG-033-migration-check` |

## Objective
Begin ADR-0042 Phase 1 (deprecation telemetry & diagnostics) without breaking anything: add a read-only import census so the post-beta `core/` → `keelway/` unification can be planned against real usage data.

## Acceptance Criteria
- [x] `core/system/migration_check.py` — AST-based scanner tallying `core.*`, `keelway_core.*`, `keelway.*` imports per module; excludes `.venv`/`__pycache__`/etc.; tolerates unparseable files
- [x] `keelway doctor --migration-check [--path DIR] [--json]` CLI surface
- [x] Live census on repo: 461 files scanned, 323 files import `core.*`
- [x] 4 unit tests pass

## Files Modified
- `core/system/migration_check.py` (new)
- `cli.py` — `--migration-check`/`--path` args + `cmd_migration_check`
- `tests/test_migration_check.py` (new)

## Tests Executed
- `pytest tests/test_migration_check.py -q`: 4 passed
- `python cli.py doctor --migration-check --path .`: real census output verified
- `py_compile cli.py core/system/migration_check.py`: clean

## Known Risks & Blockers
- ADR-0042 Phase 1 also calls for `keelway.*` facade modules mirroring `core.*`, but `keelway/` already owns colliding subpackages (`models/`, `core/`, `sandbox/`, `api/`, `cli/`, `security/`) with different content — naive facades would shadow real modules. Facade generation requires per-subsystem collision analysis and belongs to a dedicated Phase-2-planning task, not this diagnostic step.
- DeprecationWarning emission on `core.*` imports was intentionally not implemented: `core/` is the provisional runtime authority and nearly every module imports it; warning would be noise, not signal.
- `keelway_core/` census confirms isolation (only self-imports + entrypoint references).

## Next Recommended Action
Merge to `main`. Physical consolidation (ADR-0042 Phase 2) remains a separate planned task requiring founder scheduling; continue backlog items (doc-drift sweep, VS Code webview palette).
