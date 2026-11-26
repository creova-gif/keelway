# KEEL-ENG-056 — pytest config consolidation (single canonical source)

## Objective

Eliminate the duplicate pytest configuration that caused the
`ignoring pytest config in pyproject.toml` warning on every suite run.

## Finding

The repo carried pytest config in **two** places:

- `pytest.ini` — the effective config (wins precedence): `testpaths`,
  `pythonpath`, `asyncio_mode`, `asyncio_default_fixture_loop_scope`,
  `norecursedirs`, and the scoped starlette-deprecation `filterwarnings`
  suppression (KEEL-REL-063 / D-007)
- `pyproject.toml [tool.pytest.ini_options]` — a **dead subset** ignored
  by pytest on every run (`testpaths`, `python_files`, `asyncio_mode`)

## Shipped

Consolidated into `pyproject.toml` as the single canonical config —
the full `pytest.ini` settings translated to TOML, suppression comment
preserved — and deleted `pytest.ini`. Behavior is identical; the warning
is gone and there is no longer a second config file to drift out of sync.

## Verification

- `pytest --collect-only -q`: 1541 tests collected, no
  `ignoring pytest config` warning (the 5 local collection errors and
  `Unknown config option: asyncio_*` warnings are pre-existing local-env
  artifacts — `pytest_asyncio` isn't installed in this host's anaconda
  env; CI installs it and showed neither)
- `pytest tests/test_website_facts.py -x -q`: 5 passed
- Nothing in `.github/workflows/`, `Makefile`, or `scripts/` references
  `pytest.ini` or `-c pytest`
