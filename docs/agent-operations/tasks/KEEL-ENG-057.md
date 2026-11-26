# KEEL-ENG-057 — CI warning-flood suppression: pydantic UnsupportedFieldAttributeWarning (alias)

## Objective

Remove the ~837-line `UnsupportedFieldAttributeWarning` flood from every
CI test job's warnings summary so real warnings stay visible.

## Finding

CI resolves `pip install -e ".[dev]"` against **unpinned** `pyproject.toml`
ranges, landing on `pydantic 2.14.4 + fastapi 0.165.0` (not the older pins
in `requirements.lock` — the lock is not load-bearing in the test jobs;
secondary finding, flagged below).

pydantic >=2.12 added `UnsupportedFieldAttributeWarning`
(pydantic/pydantic#12028): it fires when a `Field(alias=...)` lands in a
non-field context — e.g. attached to a union member. FastAPI's dependency
machinery synthesizes `FieldInfo(alias=<param name>)` for every param
(`fastapi/dependencies/utils.py` `create_model_field` call at ~line 594);
for union-typed route params the FieldInfo is applied in a context
pydantic classifies as non-field, so each unique param name warns once.
~50 distinct alias values (`req`, `payload`, `query`, `tenant_id`,
`workspace_id`, `vllm_url`, `ollama_url`, ...) × pytest's per-location
dedup => ~837 summary lines across ~20 test files.

The warning documents an alias that was **already a no-op** — FastAPI
never relied on it taking effect in that position, and upstream FastAPI
itself suppresses the identical warning inside its own TypeAdapter
rebuild path (`fastapi/_compat/v2.py` `ModelField.__post_init__` wraps
the adapter build in `catch_warnings` + ignore when pydantic >=2.12).
This is upstream noise, not a Keelway defect: the repo has zero
`Annotated`/`TypeAdapter`/`create_model`/`validate_call` usage, and the
only in-repo `Field(alias=...)` calls are legitimate field-context uses
(`core/agents/manifest.py`, `core/agents/spec.py`, two `Query(alias=...)`
params).

## Shipped

One scoped `filterwarnings` entry in
`pyproject.toml [tool.pytest.ini_options]`:

```toml
"ignore:The 'alias' attribute:pydantic.warnings.UnsupportedFieldAttributeWarning",
```

Scoped on the `alias` attribute message only — any *other* `Field()`
misuse in a non-field context (defaults, constraints, etc.) still warns,
so the suppression cannot mask a genuine Keelway-side misuse.

## Why not a code change

There is no Keelway call site to fix: the FieldInfo/union combination is
created inside `fastapi.dependencies.utils` for synthetic body/query
param models. Restructuring every union-typed param across ~20 route
modules to dodge an upstream-benign warning would add diff surface with
zero behavior change; the suppression mirrors upstream's own treatment.

## Flagged, not fixed (follow-up candidate)

- **CI/lock drift**: `.github/workflows/ci.yml` installs
  `pip install -e ".[dev]"` (floating `>=` ranges) while
  `requirements.lock` pins a different resolution (e.g. fastapi
  0.163.1/pydantic 2.14.3). CI therefore tests a different dependency
  set than the lock describes. Options: install test jobs from the lock,
  or accept floating and delete/purpose-narrow the lock. Separate task.

## Verification

- `pytest tests/test_opencore_runtime.py -q`: 13 passed, config loads,
  filter spec resolves (`pydantic.warnings.UnsupportedFieldAttributeWarning`
  importable)
- Expected CI delta: warnings summary drops ~837 lines/jobs; zero test
  behavior change (warnings were informational only)
