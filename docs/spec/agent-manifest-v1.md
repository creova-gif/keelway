# Agent Manifest v1 (`keelway.agent/v1`)

A manifest is a JSON file that declares one agent: what it may do, what it may spend, which models it may use
and how isolated it runs. It is data only. Nothing in this spec runs an agent.

Implementation: `core/agents/manifest.py`. Example: `docs/spec/examples/test-fixer.agent.json`.
CLI: `keelway agent validate|sign|verify FILE`.

**Status:** the format, validation, digest and signing exist and are tested. **Not built yet:** the loop does not
read manifests (nothing enforces the allowlists at run time), and there is no registry, API or Studio builder.
Those are the next steps below.

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

## Next steps (not built)

1. **Enforcement:** build `AutonomousAgentLoop` from a manifest: tool allowlist, path and command scopes mapped
   onto the approval-rule machinery, `budget` as hard stops, `autonomy` to `AutonomyPolicy`, and an audit entry
   naming the manifest digest on every run.
2. **Private team registry:** store manifests by `name@version`, record `owner`, add an enable/disable (kill
   switch) flag, expose list/get/publish routes with RBAC, and show agents on Studio's run board.
3. **Builder in Studio:** create from a template, dry-run in a worktree, replay from the flight recorder, publish.
4. **Ed25519 signatures** and a public "Keelway Verified" registry, last.
