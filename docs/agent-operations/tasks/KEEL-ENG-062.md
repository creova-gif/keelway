# KEEL-ENG-062 — Static typecheck gate (mypy) + 173-error remediation

## Problem
The repo has no static typecheck gate anywhere in CI. Ruff (KEEL-ENG-061)
catches syntax and pyflakes-class defects but not type errors. A baseline
`mypy core/` (followed imports, `strict_optional=false`,
`ignore_missing_imports`) reports **173 errors in 43 files**, including
several latent defect classes ruff cannot see:

- Dead method calls that always hit `except` fallbacks
  (`LocalRuntimeDiscovery.discover_all`, `OpenCoreModelfileCompiler.compile_modelfile`).
- Attribute access on a nonexistent class name
  (`am.ValidationReport` — actual class is `am.Report`).
- Wrong-argument-type calls into platform stores
  (`upsert_record` receiving `Sequence[str]` where `str` is required).
- A variable shadowing two incompatible result types in `cli_harness.py`.

## Scope
- Add `mypy` to `[project.optional-dependencies].dev` (flows into
  `requirements.lock` via the canonical `--extra dev` compile; ENG-058).
- `[tool.mypy]` config: `packages = ["core"]`, `ignore_missing_imports`,
  `strict_optional = false` (first-gate posture; `strict_optional` is a
  follow-on ratchet — it adds ~102 errors of Optional-handling noise).
- Fix all 173 errors — real fixes where they are real defects; precise
  annotations or narrow `# type: ignore` where the idiom is intentional.
- Add a `Type check` step to the test job after `Lint check`.
- Also fix the 2 errors in `tests/` + `cli.py` found under the same flags.

## Acceptance criteria
- `python -m mypy` clean on the configured package set.
- `ruff check .` still clean; full pytest suite green (no behavior changes —
  annotation/assertion-shape fixes only, except where a real bug is found,
  which gets a regression test).
- CI green on both Python legs.
