# KEEL-REL-064 — Isolated Docker Runner Backend (D-004)

| Field | Value |
|---|---|
| **Status** | `IN_PROGRESS` |
| **Category** | `RELEASE / RUNNER / ISOLATION` |
| **Agent** | Devin |
| **Date** | 2026-11-18 |
| **Branch** | `feature/KEEL-REL-064-docker-runner-backend` |

## Objective
Release-readiness defect **D-004 (P2)**: no Docker/isolated Runner
implementing the create/exec/snapshot contract from the baseline. The
existing `core/runner/spool.py` is a durable queue, `keelway/runner/daemon.py`
is an outbound enrollment daemon, and `core/agents/sandbox.py` confines
single commands — none provide an isolated *environment lifecycle*.

## Acceptance criteria
1. A real backend implements `create/exec/snapshot/restore` (+ `destroy`,
   `list_environments`) over Docker — no mocks for the live path.
2. Confinement parity with `core/agents/sandbox.py` invariants:
   `--network none`, workspace-only bind mount at `/work`, scrubbed env
   (minimal PATH/HOME/TMPDIR + explicit `env_allow` pass-through), argv
   without a shell, in-container `timeout -s KILL`, capped output.
3. Fail-closed: `DockerRunnerBackend.available()` probes the daemon via
   `docker info`; `create()` raises `EnvironmentUnavailable` when it
   cannot provide verified isolation — never falls back to host shell.
4. Honest snapshot boundary: `docker commit` captures the container layer
   only; `EnvSnapshot.workspace_captured` is always `False` and documented
   (workspace rollback stays with `/v1/checkpoints`).
5. Injection safety: `env_id`/`image`/`label` validated against a strict
   name regex; traversal and shell metacharacters rejected.
6. Honest API surface: `GET /v1/runner/environment/status` reports
   `available` + `diagnostic` rather than pretending.
7. Positive + negative tests, including a live-daemon journey marked
   `live_docker` that skips honestly when the daemon is absent.

## Implementation

- **`core/runner/environments.py`** (new, ~390 lines): `DockerRunnerBackend`
  (zero-dep subprocess over `docker` CLI), `RunnerEnvironment`,
  `EnvExecResult`, `EnvSnapshot`, `EnvironmentUnavailable`,
  `runner_environment_backend()` fail-closed selector.
  - `create()`: `docker create --network none --workdir /work -v ws:/work
    -e <scrubbed env> --entrypoint sleep <image> infinity` + `docker start`.
  - `exec()`: `docker exec <env> timeout -s KILL <n> <argv>`; rc 124/137 →
    `timed_out`; client wait = timeout + 10s buffer so a wedged exec still
    reports `timed_out` instead of hanging.
  - `snapshot()`: `docker diff` change listing + `docker commit` →
    `keelway-env-snap-<id>:<label>-<rand>`; `workspace_captured=False`.
  - `restore()`: re-reads the `/work` mount via `docker inspect`, then
    `rm -f` + `create` from the snapshot image + `start`, preserving
    `env_id` (docker cannot mutate a running container's layer in place).
  - `destroy()`: `docker rm -f` + optional `docker rmi` of the env's
    snapshot images.
- **`core/runner/__init__.py`**: exports the new public classes.
- **`core/api/routes.py`**: `GET /v1/runner/environment/status` →
  `{available, backend, contract, diagnostic}` (auth-gated via
  `current_principal`).
- **`tests/conftest.py`**: `live_docker` marker registered.
- **`tests/test_runner_environments.py`** (new, 12 tests):
  - unit: argv contract (`--network none`, workdir, mount, entrypoint),
    timeout wrapper, 124/137 → timed_out, name-validation injection
    rejection, snapshot diff+commit, restore rm→create→start sequence,
    selector fails closed, daemon-down refusal;
  - route: honest status payload + unavailable-honest payload;
  - `@needs_docker` live journey (real daemon): create → exec writes to
    `/tmp` layer + `/work` mount → env scrub verified → snapshot → mutate
    both layers → restore → `/tmp` rolled back, `/work` NOT (documented
    boundary, asserted live) → timeout kill → list → destroy cleans up.

## Tests executed & evidence
- `pytest tests/test_runner_environments.py -q`: `12 passed in 3.14s`
  (live docker journey: real daemon 29.6.2, image `alpine:latest`).
- `pytest tests/test_runner_spool.py tests/test_core_runner_routes.py
  tests/test_runner_daemon.py -q`: `12 passed in 1.71s` (no regression).
- `ruff check core/runner/environments.py tests/test_runner_environments.py`:
  clean.
- Manual route probe: `GET /v1/runner/environment/status` →
  `{'available': True, 'backend': 'docker', 'contract':
  'create/exec/snapshot/restore', 'diagnostic': 'ok'}`; 401 without token.
- `16-known-defects.csv`: D-004 marked `closed` with evidence.

## Security review
- No secrets pass into containers: env is built from `_MINIMAL_ENV` plus
  caller-approved `env_allow` keys only (host env is never inherited
  wholesale).
- `--network none` default; `network` is a `create()` parameter for
  future allow-listed profiles.
- `env_id`, `image`, snapshot `label`, and `image_ref` are validated with
  `_NAME_RE` (alnum start, `[a-zA-Z0-9_.\-/:@]*`, `..` rejected) before
  they reach argv — `shell=False` throughout.
- Output capped (`max_output`, default 200KB); `to_dict()` tail-caps
  stdout/stderr at 10KB for evidence payloads.
- Daemon-down / binary-absent → `EnvironmentUnavailable`, matching the
  sandbox.py rule: callers must refuse, not degrade.

## Known limitations (documented, honest)
- `docker commit` does not capture bind-mounted `/work` — workspace
  rollback is `/v1/checkpoints`' job; `workspace_captured=False` in every
  snapshot payload.
- The backend does not pull images implicitly; a missing image surfaces
  as an honest `docker create` error.
- `available()` result is cached (`reset_probe_cache()` for tests) —
  honest at process start; daemon loss mid-run surfaces via
  `EnvironmentError` on the next operation.

## Next recommended action
None — defect closed pending merge of this branch.
