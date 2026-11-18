# ADR-0044: OpenCore Flagship Models Serve via Local Runtime Aliases

- **Status**: Accepted (founder decision, 2026-11-16; task KEEL-PROD-041)
- **Context**: All `keelway-*` registry models were mock-served with
  placeholder weight manifests, blocking honest developer-beta claims.
- **Decision**: Flagship tiers (`core`, `coder`, `reasoning`) declare
  `runtime_alias=True` on their weight manifests. When unspecified, the
  serving engine resolves them to a compatible installed local runtime model
  (Ollama preferred, vLLM second) via `LocalRuntimeDiscovery` bindings,
  disclosing `runtime_model` in `routing_reason`. `keelway-nano:1.5b` is
  alias-incapable and stays simulated. With no compatible runtime installed,
  flagship models fall back to mock and remain `simulated: true`.
- **Consequences**: `/v1/models` and `/v1/opencore/weights` expose
  `runtime_alias`, `resolved_model`, and `artifact_verified` so UI and API
  consumers can distinguish real aliased serving from simulation. GGUF
  manifests remain unverified placeholders; no proprietary-weights claim.
