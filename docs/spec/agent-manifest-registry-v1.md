# Agent Manifest registry v1

The registry is workspace-local control-plane state stored in `.keelway/agent_registry.json`. It is not a
public marketplace or a cloud team registry.

## Identity and immutability

- A manifest is identified by its validated `name@version`.
- Registering the same content again is idempotent.
- Reusing a name and version for different content is rejected. Publish a new semantic version instead.
- The file is owner-readable/writable and atomically replaced. Keelway agents cannot access `.keelway`.

## API

- `POST /v1/agents/manifests` registers `{"manifest": {...}, "enabled": true}`. It requires
  `approve_tier3`, validates the manifest and enforces the server's signature policy.
- `GET /v1/agents/manifests` lists versions and control metadata.
- `GET /v1/agents/manifests/{name}/{version}` returns one manifest and its metadata.
- `PATCH /v1/agents/manifests/{name}/{version}` with `{"enabled": false}` activates the kill switch. It also
  requires `approve_tier3`.
- `POST /v1/agent/run` accepts `{"manifest_ref": {"name": "test-fixer", "version": "0.1.0"}}` instead of an
  inline `manifest`.

Registration and kill-switch changes are written to the audit chain.

## Kill-switch boundary

Disabling a version refuses new runs and subsequent tool steps for runs started by registry reference. It does
not retroactively alter inline-manifest runs, rewrite saved tapes, or terminate a command that was already
executing when the switch changed.
