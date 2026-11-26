# KEEL-ENG-061 — Ruff lint widening (minimal → full pyflakes + bugbear)

## Objective

The ruff gate ran a minimal ruleset (`E9, F63, F7, F82` — syntax errors
plus a few pyflakes subsets). Widen to full pyflakes (`F`) + bugbear
(`B`) to catch real defect classes: unused names, f-string mistakes,
redefinitions, mutable/silent-truncation bugs, unchained exceptions.

## Shipped

`pyproject.toml`:

```toml
[tool.ruff.lint]
select = ["E9", "F", "B"]

[tool.ruff.lint.flake8-bugbear]
extend-immutable-calls = [
    "fastapi.Depends",
    "fastapi.Body",
    "core.security.auth.require",
]
```

`extend-immutable-calls` suppresses the 586 idiomatic false positives
(`Depends(...)`/`Body(...)`/`require(...)` in FastAPI signatures are
evaluated once at route registration — the intended call-in-default).

## Fixes (194 files, +319/-584)

| Rule | Count | Fix |
|---|---|---|
| F401 unused-import | 392 | autofix; verified no `__init__` re-exports or side-effect imports removed (stdlib-only bare imports; 4 try-block probe names dropped where the same import line still probes the module) |
| B904 raise-in-except | 123 | AST codemod appending `from <bound-exc>`; bare excepts bound `as exc` + chained — explicit `__cause__` everywhere, zero `from None` suppressions |
| F841 unused-variable | 17 | dead bindings removed; side-effect calls kept bare (`subprocess.run`, `record_fact`, `create_organization`, etc.); dead venv-detection loop, `frontmatter` dict, latency instrumentation, `current_key` removed outright |
| F541 f-string-no-placeholder | 20 | autofix (vestigial `f` prefix) |
| F811 redefinition | 4 | autofix (test_p2p_mesh conditional imports) |
| B905 zip-no-strict | 9 | per-site: `strict=True` where equal length is the contract (AST dicts, validated vectors, validator outputs); `strict=False` where truncation is required (`vault.py` AES-CTR partial final block, `_count_prefix_matches`) |
| B009 getattr-constant | 8 | autofix → attribute access |
| B007 unused-loop-var | 2 | `_`-prefix rename |

## Verification

- `ruff check .` → clean (was 576 violations at config enable)
- `pytest tests/` → 1554 passed, 9 skipped; only failures are the two
  pre-existing environmental ones also failing on clean `main`
  (`test_early_access_node_security_suite` — Node 24 vs CI's 22;
  `test_clean_disconnection_and_reconnection_without_leaks` —
  local httpx/starlette vs locked CI versions)
