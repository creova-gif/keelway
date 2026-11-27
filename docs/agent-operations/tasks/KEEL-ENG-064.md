# KEEL-ENG-064 — check_untyped_defs ratchet (mypy gate tightening)

## Problem
After KEEL-ENG-063 the gate checks every typed function body but skips
untyped ones entirely — the `annotation-unchecked` notes flagged
`cli.py`, `routes.py`, `mcp_client.py`, `eval_runner.py` bodies escaping
analysis. Enabling `check_untyped_defs` reported **8 errors, all in
`cli.py`**.

## What shipped
- `pyproject.toml`: `check_untyped_defs = true` under `[tool.mypy]`.
- 8 errors fixed in `cli.py`:
  - `cmd_audit(act)` — `or`-chain could still yield `None`; explicit
    `"export"` fallback added.
  - `store`/`audit_store` rename — `SQLiteAuditStore` assigned to a var
    bound earlier as `EvaluationReceiptStore`.
  - `rec`/`found` rename — `service.get()` returns Optional where
    `service.store()` returns the record.
  - `results`/`hits`/`recs` renames — `search_hybrid` returns scored
    tuples while `search`/`list_by_scope` return bare records.

## Verification
- `python -m mypy` (2.4.1, strict_optional + check_untyped_defs):
  **0 errors / 297 files**
- `ruff check .`: clean; `py_compile cli.py`: clean

## Remaining ratchets (documented, not in scope)
- `disallow_untyped_defs` — requires signatures on every def; the
  untyped-def notes show where the unannotated surface lives.
- `packages` beyond `core` (scripts/, tests/, evals/…).
