# KEEL-ENG-049 — Full-Suite Green + GitHub Actions Minute Optimization

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `ENGINEERING / TESTING / CI` |
| **Agent** | Devin |
| **Branch** | `fix/test-isolation-ci-budget` |
| **Merged** | `912bc25` (2026-11-16) |

## Objective

Restore the full pytest suite to green (7 ordering/drift failures) and reduce
GitHub Actions consumption against the ~2,000 hosted-minutes/month budget
**without removing any quality or security gate** (founder decision:
"Optimize + keep hosted").

## Root causes found & fixed

1. **`test_config_fallback.py` module-identity bug** (root cause of 3 order-
   dependent 401s): the no-pydantic shim deleted `core.config` from
   `sys.modules` and re-imported it, creating a **second `settings` instance**
   with `auth_required=True`. The conftest fixture kept patching the stale
   object while `governance_auth_required()` imported the fresh one → 401s in
   `test_fastapi_rest_endpoints`, `test_tokenless_ack_*`, and
   `test_runner_api_poll_and_ack_lifecycle` — only in full-suite order.
   Fix: restore the **original** module object in `sys.modules`.
2. **`test_airgap_auditor_environment`**: host `GEMINI_API_KEY` correctly
   failed the audit; test now clears cloud credential env vars to assert the
   clean-environment baseline.
3. **Drifted contract tokens** (all intentional product changes, stale tests):
   - `test_phase8`: README is v1.1.0; `P10HumanGate.tla` was never committed
     (KEEL-DOC-034 errata) — now asserted absent.
   - `test_phase9`: `OIDC/SAML` split — KEEL-SEC-037 documents SAML as not yet
     implemented.
   - `test_sdk_v1`: web-console palette updated for KEEL-WEB-028 zinc refresh.
4. **`install.sh` privacy violation**: hardcoded `github.com/creova-gif/kora.git`
   — a **private** repo — in customer-facing files. `test_website_facts`
   correctly flagged the internal-identity leak. Both installers now require
   explicit `KEELWAY_GIT_URL` (no default) and fail closed with guidance
   **before** creating the venv.
5. **`requirements.lock` stale**: upstream `sqlalchemy 2.1.8 → 2.1.9` broke the
   freshness gate. Regenerated with `uv pip compile --upgrade`
   (note: plain `-o` preserves existing pins — `--upgrade` or a fresh path is
   required to pick up new releases).

## CI optimization (all gates preserved)

- Python matrix `3.11/3.12/3.14` → `3.11/3.14` (min+max supported).
- `pip` caching on all Python jobs; npm cache extended to `dev-app` lockfile.
- `verify_engineering_gates.sh`: `KEELWAY_GATES_CI_FAST=1` skips pytest subset
  re-runs duplicated by the full `pytest -v` step; syntax/lock/SDK checks and
  the sandbox/bubblewrap, ruff, and full-suite steps are unchanged.
- Path filters were evaluated and **rejected**: the Python suite is a repo-wide
  drift gate (test_website_facts, phase9, sdk_v1 assert on website/, web-console/,
  install.sh), so directory-based job skipping would silently drop coverage.

## Verification

- `.venv/bin/pytest -q` → **1402 passed, 2 skipped, 0 failed** (281s).
- `KEELWAY_GATES_CI_FAST=1 bash scripts/verify_engineering_gates.sh` → all 8
  steps pass locally (subsets skipped, SDK/dev-app checks run).
- `check_python_lock.sh` → fresh.
- `ruff check` on touched test files → clean; `bash -n` + YAML parse on
  workflow/script → clean.
- `install.sh --dry-run` without source → fails closed with guidance;
  with `KEELWAY_SOURCE_DIR` → resolves plan, zero writes.

## Honest caveats

- GitHub Actions has **not** been observed running the new workflow — local
  verification only. First push will confirm.
- `curl install.sh | sh` still cannot complete for a real customer: no public
  source mirror or PyPI package exists yet (founder decision pending).
- Matrix reduction drops the 3.12 leg; 3.11+3.14 cover min/max.
