# Keelway — Feature Map

User-facing features of the Keelway Unified 10-View Sovereign Platform (`/app`, `/v1/*`, `cli.py`), indexed for end-to-end verification. Each file covers what the feature does, every way a user reaches it, how to drive it with `control-keelway`, and what observable UI + CLI + SQLite WAL end state proves it works.

- [Live SSE Execution & P-10 Human Approval Gate](live-execution-p10.md) — streaming agent/workflow runs, pausing at `Held · P-10 Human Gate`, RBAC & self-approval enforcement, human approval/denial, and SQLite WAL run receipts.
- [Encrypted Secret Vault & SSRF-Guarded Webhooks](secret-vault-and-webhooks.md) — `AES-256-GCM` secret storage, masking, rotation, revocation, CLI vault parity, and HMAC-SHA256 webhook registration.
- [Calibrated Pricing & MiroFish Market Simulator](pricing-mirofish-simulator.md) — seat/BYOM spend quota simulator, 5-persona MiroFish pricing check in Operations, and `cli.py pricing-eval` parity.
- [Multi-Workspace Switching, RBAC & No-Code Blueprint](workspace-switching-and-nocode-blueprint.md) — creating/switching isolated workspaces, toggling Builder vs Guided Non-Coder persona, and compiling cross-view blueprints.
- [MCP Tool Control Plane & 16-Probe Golden Evaluation Suite](mcp-and-golden-evals.md) — SSRF/shell-guarded MCP server registry, live JSON-RPC tool tester with secret redaction, and 16-probe Golden Benchmark & Red-Team scorecard.
