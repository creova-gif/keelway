# KEEL-ENG-054 — `tests/__init__.py`: make `tests` a regular package

## Objective
Whole-directory `pytest tests/` could fail with `ModuleNotFoundError: No module
named 'tests.package_a_profile'` because `tests/` was a PEP 420 namespace package
while `conftest.py` and three test modules already import `from tests.*`.
Any site-packages `tests` regular package shadows the namespace dir.

## Change
- `tests/__init__.py`: empty package marker. `tests` is now a regular package;
  `from tests.package_a_profile` resolves deterministically and can no longer be
  shadowed by an installed `tests` distribution.

## Safety checks performed
- No `import tests`/`from tests` in `core/` or `cli.py` (production untouched).
- No top-level sibling imports (`import test_x`, `from conftest`) that would break
  under package-mode collection.
- `tests/fixtures/` holds non-test helpers only — no basename collisions.

## Evidence
- `pytest tests/ --collect-only -q` → `1554 tests collected` (was: collection
  crash in shadowed environments).
- Full run: `pytest tests/ -q` → `1552 passed, 2 skipped` (sessionfinish
  `from tests.package_a_profile` hook exercised and clean).
- Targeted: `test_unified_platform.py` + `test_release_live_inventory.py` → `28 passed`.
