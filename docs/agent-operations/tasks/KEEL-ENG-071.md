# KEEL-ENG-071 — mypy `packages` expansion beyond `core`

- **Status**: COMPLETED
- **Agent**: Devin
- **Date**: 2026-11-27
- **Branch**: `chore/mypy-pkg-scope`

## Objective & acceptance

P2 backlog: widen the mypy first-gate `packages` scope past `core`.
Acceptance: `packages` covers the first-party packages, mypy clean on
the widened set, ruff clean, targeted tests green.

## Scope decision

- `packages = ["core", "keelway", "evals"]` — checked files 297 → 346.
- `keelway_core` deliberately excluded: it is the rename-compat shim
  already slated for removal in the P2 backlog; gating it is wasted work.
- `evals` was already clean; `keelway` brought 21 errors.

## Changes

- `keelway/api/routes.py`: 16 handler return types bound to their
  declared `response_model` (`RunManifest`, `List[AuditEvent]`,
  `ExportBundle`, `PolicyDecision`, `PullRequestResult`,
  `DeploymentResult`, `AuditVerifyResponse`, dict shapes).
- `keelway/api/app.py`: middleware `call_next`/`-> Response` (same
  contract as `core/main.py`); `index_dashboard -> str` (returns HTML
  text, rendered by `response_class=HTMLResponse`).
- `keelway/cli/main.py`: `main() -> None`.
- `keelway/git_ci/github.py`: `payload.get("action", "")` — the
  non-`closed` branch called `action.upper()` on a possibly-absent
  field (latent None-deref on malformed webhook payloads).
- `routes.py` ×2: `assert res is not None` after `ok` checks —
  documents the `ok ⟹ result present` tuple contract in
  `promote_to_pr`/`deploy_to_staging`.

## Evidence

- `mypy` (2.4.1): **0 errors, 346 files** (`packages` now core+keelway+evals)
- `ruff check .`: clean
- `pytest` targeted: 57 passed — test_github_webhooks,
  test_end_to_end_workflow, test_policy_engine,
  test_agent_loop_policy_quorum, test_audit_export, test_mcp_bridge,
  test_core_runner_routes, test_quarantine, test_runner_daemon,
  test_approvals, test_policy_bundle, test_audit_store, test_quorum,
  test_audit_chain, test_merkle_audit

## Residual

Remaining unchecked first-party surfaces are intentionally out of gate
scope: `keelway_core` (removal-bound), `tests/`, `scripts/`,
`examples/`, `research/`.
