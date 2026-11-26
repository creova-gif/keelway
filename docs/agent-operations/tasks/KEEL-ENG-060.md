# KEEL-ENG-060 — Linux bubblewrap confinement proof suite

## Objective

Close the residual per-vector coverage gap on the production Linux
sandbox backend. The 13 granular confinement proofs are a named macOS
release contract (`SEATBELT_CONFINEMENT_PROOFS`, `live_seatbelt`,
release_live_gate requires seatbelt — bubblewrap intentionally does not
satisfy it). On Linux, `Sandbox.verify()` covers the core escape
vectors and `test_live_bubblewrap_confinement_under_home_workspace`
covers workspace/protected-path/env/network — but five vectors never
exercised the bubblewrap profile in CI.

## Audit finding

CI skip audit (14 skips/job): 13 = seatbelt-only release proofs
(by design, macOS-bound), 1 = `KEELWAY_GATES_CI_FAST` subset dedup
(by design). Not a bug — but the audit exposed that these vectors
were asserted only under seatbelt:

- subprocess confinement (children stay confined)
- no-shell semantics (`run()` never interprets a shell)
- timeout → whole-process-group kill (grandchild teardown under
  `--unshare-pid --die-with-parent --new-session`)
- output cap + missing-command 127 (exercises the bespoke
  `bwrap: execvp` → 127 mapping at `core/agents/sandbox.py`)
- agent-loop integration (`paused_for_approval` → approve flow,
  `result["sandbox"]`, workspace-sandbox fail-closed fallback)

## Shipped

Six `needs_bubblewrap` proofs in `tests/test_agent_sandbox.py`, in the
existing Linux bubblewrap section — additive coverage, zero change to
the seatbelt release contract (`SEATBELT_CONFINEMENT_PROOFS` and
`test_release_live_inventory` untouched):

- `test_bubblewrap_subprocesses_stay_confined`
- `test_bubblewrap_commands_are_not_run_through_a_shell`
- `test_bubblewrap_timeout_kills_the_whole_process_group`
- `test_bubblewrap_output_is_capped_and_missing_commands_are_reported`
- `test_bubblewrap_loop_runs_allowed_commands_confined_with_a_scrubbed_env`
- `test_bubblewrap_workspace_sandbox_cannot_fall_back_to_a_host_command`

## Verification

- Local (macOS, seatbelt): 36 passed, 8 skipped — new proofs skip
  cleanly off-Linux; seatbelt suite unaffected
- CI (Ubuntu, bubblewrap verified): the 6 proofs execute under the
  real `bwrap` backend — first granular per-vector regression net on
  the production Linux path
