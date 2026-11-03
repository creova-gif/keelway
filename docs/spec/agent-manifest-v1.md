# Agent Manifest v1 (`keelway.agent/v1`)

A manifest is a JSON file that declares one agent: what it may do, what it may spend, which models it may use
and how isolated it runs. It is data only. Nothing in this spec runs an agent.

Implementation: `core/agents/manifest.py`. Example: `docs/spec/examples/test-fixer.agent.json`.
CLI: `keelway agent validate|sign|verify FILE`.

**Status:** the format, validation, digest and signing exist and are tested. **Run-time enforcement exists for
part of it** (`core/agents/guard.py`, section "Enforcement") and **commands can run in a verified OS sandbox on
macOS** (`core/agents/sandbox.py`, section "Sandbox"). **Not built yet:** registry, API routes, Studio builder,
a Linux sandbox, containers, and enforcement of `budget.max_usd_per_run` and `mcp_servers`.

## Fields

| Field | Type | Rules |
|---|---|---|
| `schema` | string | Must be `keelway.agent/v1` |
| `name` | string | `^[a-z][a-z0-9-]{1,62}$` |
| `version` | string | `MAJOR.MINOR.PATCH` |
| `owner` | string | 1 to 100 chars |
| `description` | string | up to 500 chars, optional |
| `instructions` | string | 1 to 20,000 chars |
| `model.routing` | enum | `local_first` (default), `local_only`, `cloud_only` |
| `model.preferred_provider` | enum | `anthropic`, `openai`, `google`, `local`; must agree with `routing` |
| `tools` | list | at least one of `read_file`, `write_file`, `edit_file`, `run_command`, `list_dir`, `search_codebase`; no repeats |
| `mcp_servers` | list | names of MCP servers the host has configured; no URLs or commands in the manifest |
| `permissions.autonomy` | enum | `confirm_mutation` (default), `confirm_all`, `autonomous` |
| `permissions.read_paths` | list | workspace-relative globs; no `..`, not absolute, never `.keelway`, `.kora` or `.git` |
| `permissions.write_paths` | list | same, and must not match every file |
| `permissions.commands` | list | exact commands; shell operators (`; & \| ` $ < > \` and newlines) are rejected |
| `permissions.network` | enum | `none` (default) or `allowlist` |
| `permissions.network_allow` | list | plain hostnames only, required for `allowlist` |
| `budget.max_usd_per_run` | number | greater than 0, up to 1000 |
| `budget.max_steps` | integer | 1 to 500 |
| `sandbox` | enum | `workspace`, `worktree` (default), `container` |
| `signature` | object | see below; excluded from the digest |

Unknown fields are rejected.

## Cross-field rules

- `write_file` or `edit_file` requires `write_paths`, and `write_paths` requires one of those tools.
- `run_command` requires `commands`, and `commands` requires `run_command`.
- `autonomous` plus `run_command` requires sandbox `worktree` or `container`.
- `network: none` forbids `network_allow`; `allowlist` requires it.
- `local_only` cannot prefer a cloud provider; `cloud_only` cannot prefer `local`.

Warnings (valid but risky): `autonomous` needs the `approve_tier3` permission to run; `read_file` with no
`read_paths`; `run_command` in sandbox `workspace`; cloud model use while `network` is `none` (that field limits
tools, not model calls).

## Digest and signature

`digest = "sha256:" + sha256(canonical JSON)`, where canonical JSON is the manifest without `signature`,
using the `schema` alias, sorted keys, separators `(",", ":")` and no null fields.

`signature` = `{alg: "hmac-sha256", key_id, digest, value, signed_by, signed_at}` with
`value = HMAC-SHA256(key, digest)` and `key_id = first 12 hex of sha256(key)`. The key lives at
`.keelway/agent_signing.key` (created on first sign, mode 0600).

**Limit:** HMAC means only holders of the key can verify. It suits a team sharing a workspace key. For a registry
or third parties, move to Ed25519 (needs the `cryptography` package). Verification results:
`ok`, `not_signed`, `wrong_key`, `content_changed_since_signing`, `bad_signature`.

## Enforcement (`core/agents/guard.py`)

`loop_from_manifest(manifest, task_id, ...)` builds an `AutonomousAgentLoop` that can only do what the manifest
allows. The guard only **narrows**: it can deny a call and never grants one, and it runs before approval rules,
so a standing "Allow always" rule cannot widen a manifest.

| Enforced | How |
|---|---|
| `tools` | Only listed tools are registered; the guard checks again on every call |
| `permissions.read_paths`, `write_paths` | Glob (`*` stays in a folder, `**` crosses folders, `?`) matched on the **real, symlink-resolved** path; `..`, absolute paths, backslashes and NUL are rejected; Keelway state and `.git` are always off limits, including through symlinks. Empty `read_paths` means the whole workspace minus protected paths |
| `search_codebase` | Results are filtered to files the agent may read |
| `permissions.commands` | Exact string match after trimming whitespace |
| `budget.max_steps` | Counted per guard; denied calls do not consume it |
| `permissions.autonomy` | Becomes the loop's approval policy |

Every denial is recorded as a `policy_denied` event with the manifest digest, and a `manifest_bound` event records
the digest when the loop starts. These go to the loop's events and flight tape, **not yet to the hash-chained
audit log** (that is written by API routes).

## Sandbox (`core/agents/sandbox.py`)

`sandbox` decides how `run_command` executes:

| `sandbox` | Behaviour |
|---|---|
| `workspace` | The old path: a shell in your workspace that inherits your environment. **Unconfined.** An `autonomous` agent may not use it with `run_command`. |
| `worktree` | Runs inside an OS sandbox (macOS seatbelt). Refused unless a self-test passes on this machine. |
| `container` | **Not built.** A manifest that enables `run_command` with it is refused. |

(The name `worktree` is historical: today it means "OS-confined process in the workspace", not a separate git
worktree copy. A disposable copy that you merge back is a possible later step.)

What a sandboxed command gets:

- **Scrubbed environment.** Only `PATH`, locale and terminal variables survive. API keys, tokens, `SSH_AUTH_SOCK`
  and cloud credentials are dropped. `HOME` and `TMPDIR` point at a private temp dir; git config is disabled.
- **Writes** only inside the workspace and that temp dir, and never into `.git`, `.keelway` or `.kora`.
- **Reads** the workspace, the Python environment and PATH tools. Other files under `/Users`, `/Volumes` and root's
  home are denied (no `~/.ssh`, no other projects). `.keelway` (the signing key) is unreadable even inside the workspace.
- **No network**, including loopback. There is no per-host allowlist, so `permissions.network: allowlist` with
  `run_command` is refused.
- **No shell** (`shell=False`, arguments split with `shlex`), so `;`, `&&`, `$VAR` and globs are passed literally.
- **Process group** killed on timeout (grandchildren too), output capped at 200 KB, stdin closed.

**Fail closed.** `Sandbox.verify()` really tries to escape in a throwaway workspace (write and read outside, open a
network connection, write to `.git` and `.keelway`, read `.keelway`) and passes only if normal work succeeds and every
escape fails. If it does not pass, or there is no backend, `loop_from_manifest` raises `ManifestNotRunnable`. An
`autonomous` agent may run commands only under this verified sandbox.

**Limits, plainly:**

- macOS only. On Linux and Windows there is no backend, so such agents are **refused**, not run unconfined.
- It is process confinement, not a VM or container. The kernel is shared, and system files outside the denied areas
  stay readable. Apple marks `sandbox-exec` deprecated; it still works and other tools rely on it.
- Tools that need to write elsewhere fail by design. For example Apple's `/usr/bin/git` shim writes a cache outside
  the workspace and errors; use a real git binary or an allowed command that does not need it.
- Commands in the allowed list still do whatever those programs do inside the workspace (for example `pytest`
  runs the project's own code and can modify workspace files other than `.git`/`.keelway`).
- A command that needs a tool under your home that is not on `PATH` will not be readable.

## HTTP API

**Start a run from a manifest:** `POST /v1/agent/run` with an inline `manifest` object (plus the usual `task_id`,
`goal`, `steps`). Needs `execute_agent`.

- The manifest is validated; problems return **422** with `{"detail": {"errors": [...]}}`.
- `permissions.autonomy` becomes the run's policy. A `policy` in the same request must match or is rejected (400).
  `autonomous` still needs `approve_tier3`, so a manifest cannot be used to skip that check.
- A manifest with a `signature` is checked against `.keelway/agent_signing.key` in the workspace; a bad signature
  or a missing key is **400**. Set `require_signed_manifests=true` to reject unsigned manifests too.
- A manifest that cannot run on this machine (`container`, a network allowlist with commands, no verified sandbox)
  is **422** with the reason. Nothing is registered.
- The response adds `manifest` (name, version, digest, signed, steps used, max steps) and `not_enforced`.
  `GET /v1/agent/status/{task_id}` and the run state carry the same `manifest` block.

**Audit.** These go into the hash-chained audit log (and so into the Record):
`agent_run_manifest` for a start (allowed) and for every refusal (denied), and `manifest_denied` for every tool call
the manifest blocked during a run, each naming the manifest digest.

**Dry run:** `POST /v1/agents/validate` with `{"manifest": {...}}` (or the manifest itself) returns `valid`,
`errors`, `warnings`, `digest`, `signature` state, `requires_signature`, `runnable` + `runnable_reason` for this
machine, and `not_enforced`. It starts no agent (it may run the sandbox self-test).

## Next steps (not built)

1. **Registry:** store manifests by `name@version`, record `owner`, add an enable/disable (kill switch) flag, list/get/
   publish routes with RBAC, and show agents on Studio's run board. A run would reference a registered manifest by
   `name@version` instead of sending it inline.
2. **Linux sandbox backend** (bubblewrap), tested on a real Linux machine; containers.
3. **Cost metering** for `max_usd_per_run`.
4. **Builder in Studio:** create from a template, dry-run (use `/v1/agents/validate`), replay from the flight
   recorder, publish.
5. **Ed25519 signatures** and a public "Keelway Verified" registry, last.
