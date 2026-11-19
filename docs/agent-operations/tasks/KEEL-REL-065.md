# KEEL-REL-065 — CLI Canonicalization (D-005): keelway + keelway-ops, unship reference engine

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / CLI / PACKAGING` |
| **Agent** | Devin |
| **Date** | 2026-11-18 |
| **Branch** | `fix/KEEL-REL-065-cli-canonicalization` |

## Objective
Release-readiness defect **D-005 (P2)**: multiple CLI surfaces with
different rigor. ADR-0042 already designates `cli.py` (`keelway`) as
canonical; the residual problems were (a) `keelway-core` binary vs
`keelway_core` package naming collision, and (b) the
non-enterprise-qualified reference engine (`keelway-ref`) shipping inside
the wheel.

**Owner decision (2026-11-18):** two installed binaries + unship the
reference engine — `keelway` (dev tool) + `keelway-ops` (governance ops);
`keelway-core` retained as a deprecated alias; `keelway_core/` excluded
from the wheel, repo-only.

## Implementation

- `pyproject.toml`: `keelway-ops = "keelway.cli.main:main"` added;
  `keelway-core` kept pointing at the same target (deprecated alias);
  `[tool.setuptools.packages.find] exclude = ["keelway_core*"]`.
- `keelway/cli/main.py`: `prog` derived from `argv[0]` (honest
  `usage: keelway-ops`); invoking as `keelway-core` prints a deprecation
  warning to stderr.
- `README.md`: control-plane row + console-scripts list updated to
  `keelway-ops`; `keelway-core` documented as deprecated alias.
- `Makefile`: help comment updated.
- `docs/DEVELOPER_QUICKSTART.md`: both `keelway-core` references updated
  (also corrected the stale `prog="keelway"` claim).
- `docs/decisions/ADR-0042`: CLI Entrypoint row updated — `keelway-ops`
  canonical ops binary, `keelway-core` deprecated alias, `keelway-ref`
  excluded from wheel.

## What was deliberately NOT renamed

- `keelway-core:7b` — OpenCore model ID (~90% of literal `keelway-core`
  matches); model naming, not the binary.
- `keelway-core-mcp` — MCP server id (test fixtures).
- `keelway-core-adapted` — adapter path example in openapi.json.
- `_LOCAL_MODEL_PREFIXES` / opencore runtime alias family — model detection.
- `telemetry.py service_name="keelway-core"` — OTel service identity
  (unchanged to avoid breaking existing dashboards/traces).
- `keelway/cli/main.py` invoked via `python -m keelway.cli.main` in
  Dockerfile ENTRYPOINT + Makefile — module path unaffected by the rename.

## Tests executed & evidence

- `pytest tests/test_keelway_core_cli.py tests/test_keelway_core_engine.py
  tests/test_phase7_packaging_and_sdk.py tests/test_cli_init_and_banner.py -q`
  → `59 passed in 6.64s`.
- `python -m keelway.cli.main --help` → `usage: keelway-ops` (honest prog).
- Simulated `keelway-core` invocation → `WARNING: 'keelway-core' is
  deprecated; use 'keelway-ops' instead.` + `usage: keelway-core`.
- Wheel build (`python -m build --wheel`): `keelway_core` **0 entries**;
  entry_points = `keelway`, `keelway-ops`, `keelway-core` (alias).
- `python -m keelway_core doctor` (from source) →
  `{"status": "REFERENCE_ONLY", "enterprise_security_qualified": false}` —
  reference engine still runnable repo-only, honestly self-labeled.
- `16-known-defects.csv`: D-005 marked `closed` with evidence.

## Next recommended action
None — defect closed pending merge.
