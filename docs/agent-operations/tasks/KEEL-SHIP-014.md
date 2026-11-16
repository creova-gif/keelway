# KEEL-SHIP-014 — Phase 7: Commercial Ship Readiness — MCP Control Plane, 16-Probe Golden & Red-Team Suite, Wheel/Homebrew Packaging & Tri-SDK Parity

- **Status**: `VERIFIED_COMPLETE`
- **Assigned Agent**: Google Antigravity (3-Agent Parallel Wave: `7A+7B`, `7C`, `7D` + Cold `verify-keelway` E2E Proof)
- **Date**: 2026-11-15
- **Branch**: `main`

## Summary

Completed commercial ship readiness across Keelway's Model Context Protocol (`2025-06-18`) server & tool control plane, 16-probe zero-egress Golden Benchmark & Adversarial Red-Team Suite, standalone Python wheel / Homebrew / zero-friction installer distribution, 7-method Tri-SDK (`Python`, `TypeScript`, `Go`) parity, and Local Dev Tool (`:7420/app`) `Agents` & `Security` UI panels, proved cold end-to-end via `control-keelway` (`verify-keelway`).

## Key Deliverables

1. **Model Context Protocol (`2025-06-18`) Server & Tool Control Plane (`core/platform/mcp_registry.py`, `core/api/platform_mcp_routes.py`)**:
   - SQLite WAL-backed `PlatformMcpRegistry` (`platform_mcp_servers`) exposing built-in `keelway-core-mcp` (`5` real workspace/governance/vault tools: `workspace.list_files`, `workspace.search_symbols`, `workspace.git_status`, `governance.check_airgap`, `vault.list_metadata`) alongside workspace-scoped `sse` and `stdio` MCP servers.
   - Enforces cloud-metadata/private-IP SSRF blocking (`validate_webhook_url`), `stdio` shell-metacharacter & `..` traversal rejection, `redact_sensitive_text` DLP output scrubbing (`sk-*`, `AKIA*`, `kw_live_*`, `Bearer ...`), SHA-256 call receipts, and 5-role RBAC header-ceiling narrowing (`GET/POST/DELETE /v1/platform/mcp/servers`, `GET /v1/platform/mcp/tools`, `POST /v1/platform/mcp/call`).
   - Enriched `LiveExecutionStreamer.start_run` (`core/platform/execution_stream.py`) with optional `workspace_root` file-count context.
2. **16-Probe Golden Evaluation & Adversarial Red-Team Suite (`core/eval/golden_suite.py`, `core/cli_mcp_eval.py`)**:
   - Executes 16 real deterministic subsystem probes (`< 100ms`, zero network egress) across `workspace_ast` (`ws-traversal-block`, `ws-tree-scan`, `ws-ast-symbols`, `ws-atomic-write-read`), `governance_p10` (`gov-p10-lateral-escalation`, `gov-p10-self-approval`, `gov-p10-spoofed-agent`, `gov-wal-tamper-detect`), `security_redteam` (`sec-ssrf-imds`, `sec-marketplace-injection`, `sec-vault-gcm-tamper`, `sec-secret-redaction`), and `routing_pricing` (`rt-private-fail-closed`, `rt-byom-consumer-block`, `rt-mirofish-calibrated`, `rt-settlement-split`), persisted in SQLite WAL (`platform_eval_runs`) via `POST /v1/platform/evals/golden` and `GET /v1/platform/evals/latest`.
   - Added Sovereign CLI commands `python cli.py mcp <servers|tools|call> --json` and `python cli.py eval-suite --category <all|...> --json`.
3. **Wheel Packaging Fix, Zero-Friction Installer & Tri-SDK Parity (`pyproject.toml`, `scripts/install.sh`, `Formula/keelway.rb`, `core/sdk/`, `sdk/typescript/`, `sdk/go/`)**:
   - Bumped `pyproject.toml` to `1.0.0` and added `dev_app_dist/*.html`, `dev_app_dist/assets/*`, and `dev_app_dist/assets/**/*` to `[tool.setuptools.package-data]` so standalone wheel installs serve `:7420/app` out of the box.
   - Added `scripts/install.sh` (`--help`, `--dry-run`, `--prefix`, `--venv`, `--json`, deterministic exit codes `0/2/3/4`) and `Formula/keelway.rb`.
   - Added all 7 MCP & Golden Eval methods across Python (`core.sdk`), zero-dependency TypeScript (`@keelway/sdk`), and zero-dependency Go (`keelway-go`).
4. **Local Dev Tool (`:7420/app`) Live MCP Inspector & Golden Eval Scorecard (`dev-app/src/components/platform/`)**:
   - Mounted `McpInspectorPanel.tsx` in `AgentsWorkspaceView` and `GoldenEvalScorecardPanel.tsx` in `SecurityWorkspaceView` (`0` `axe-core` WCAG 2.2 AA violations), rebuilt `core/dev_app_dist/*`, exported `244`-path OpenAPI 3.1 schema, and verified cold end-to-end with `verify-keelway`.
