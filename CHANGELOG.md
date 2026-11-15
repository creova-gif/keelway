# Changelog

All notable changes to **Keelway** are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-11-15

### Added
- **Unified 10-View Sovereign Dev Tool (`/app`)**: Production React 19 + TypeScript + Vite single-page workspace bundled directly into `core/dev_app_dist/` and served from `http://127.0.0.1:7420/app` alongside Keelway Studio (`/studio`). Covers Overview, Coding Workspace (AST symbol index + workspace-confined file editor), Lifecycle Agent Teams, PM Issues, Product PRDs & Feedback, Diataxis Docs, KFlow DAG Automation & KSpaces CRDT Sync, Guided No-Code Blueprint Studio, Security/Vault/MCP/SBOM, and Subscriptions/Golden Evals with automated `axe-core` WCAG 2.2 AA verification.
- **KFlow Deterministic DAG Execution Engine & KSpaces CRDT Sync**:
  - `POST /v1/platform/automation/workflows/execute` & `GET /v1/platform/automation/runs` with Kahn topological sorting, cycle rejection, per-run token budget enforcement, P-10 human-gate pause/resume (`awaiting_p10_approval`), and SHA-256 execution receipts.
  - `POST /v1/platform/kspaces/sync` & `GET /v1/platform/kspaces/state` implementing deterministic Lamport-clock Last-Writer-Wins (LWW) CRDT state synchronization persisted in SQLite WAL.
- **Live CycloneDX 1.5 SBOM Provenance Endpoint**: `GET /v1/platform/security/sbom` generating and cryptographically verifying HMAC-SHA256 supply-chain component manifests via `SBOMGenerator` and `SBOMVerifier`.
- **MCP `2025-06-18` Control Plane & 16-Probe Golden Evaluation Suite**:
  - `GET/POST/DELETE /v1/platform/mcp/servers`, `GET /v1/platform/mcp/tools`, and `POST /v1/platform/mcp/call` with SSRF metadata/loopback/shell-metacharacter blocking and automatic DLP secret redaction.
  - `POST /v1/platform/evals/golden`, `GET /v1/platform/evals/latest`, and `keelway eval-suite --category <all|workspace_ast|governance_p10|security_redteam|routing_pricing> [--json]` executing 16 deterministic subsystem probes with signed SHA-256 receipts.
- **Official Tri-Language `v1.0.0` SDK Parity**:
  - **Python** (`core.sdk.KeelwayClient` & `AsyncKeelwayClient`), **TypeScript** (`@keelway/sdk` `v1.0.0` in `sdk/typescript`), and **Go** (`github.com/keelway/keelway-go` in `sdk/go`) aligned across Inference, Stateful `/v1/responses`, 4D Routing Provenance, OpenCore, Multi-Tenant Governance, GPU Cluster Scheduling, Workspace Runtime, Encrypted Vault, RBAC, Webhooks, SSE Execution Streams, MCP Control Plane, Golden Evals, KFlow DAG Execution, KSpaces CRDT Sync, and CycloneDX SBOM verification.
- **Formal TLA+ P-10 Gate Specification**: Added `specs/tla/P10HumanGate.tla` modeling separation-of-duty invariants (`RequesterCannotSelfApprove`, `NoUnapprovedMutationCommit`, `TerminalDecisionImmutability`).
- **Calibrated 5-Tier Pricing & BYOM 0% Token Markup**: Validated via MiroFish multi-persona simulation (`POST /v1/platform/pricing/simulate` & `keelway pricing-eval`): Community (`$0`), BYOM Seat (`$15/mo` annual, 0% markup), Pro (`$29/mo` annual), Team (`$49/mo` annual), and Enterprise Custom.
- **Zero-Friction Packaging & Installers**: Standalone Python wheel packaging (`pyproject.toml` `v1.0.0` bundling `core/studio` + `core/dev_app_dist`), Homebrew formula (`Formula/keelway.rb`), and `--dry-run` / `--help` support across `scripts/install.sh` and `website/public/install.sh`.

### Changed
- **Hardened Multi-Stage Container & Compose Stack**: Updated `Dockerfile` (`python:3.12-slim`, UID `10001:10001`, writable `/data` volume, bundling full `cli.py`, `core/`, `keelway/`, `research/`, and `evaluations/`) and `docker-compose.yml` (adding `keelway-platform` on `:7420` alongside `keelway-control-plane` on `:8000`, `keelway-runner`, and `ollama`).
- **GitHub Actions CI & Container Release Gates**:
  - Upgraded `.github/workflows/ci.yml` to run Python `3.11`/`3.12`/`3.14` + Linux Bubblewrap sandbox verification, Next.js 15 website + Unified `/app` Vitest/`axe-core` + TypeScript & Go SDK suites, and isolated wheel + Golden Suite + SBOM verification on every push and PR while keeping macOS Seatbelt + live Ollama verification dedicated to `.github/workflows/release-gate-macos.yml`.
  - Upgraded `.github/workflows/deploy.yml` to verify live container startup, HTTP readiness, diagnostic failure logs, and in-container `keelway eval-suite --category all --json`.
