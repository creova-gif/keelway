# Changelog

All notable changes to **Keelway** are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] — 2026-11-15

### Added
- **Zero-Install Homepage Golden-Thread Studio Showcase (`/#studio-showcase`)**: Browser-native interactive studio on the Next.js 15 website converting LangGraph `StateGraph` pipelines into KFlow topological/cyclic graphs, bidirectional Python & `@keelway/sdk` TypeScript code generation with AST line highlighting, Flame Waterfall Flight-Tape scrubbing with `$0.00` cached counterfactual forks, Seatbelt/Bubblewrap Blast-Radius probe radar, and live Prompt Regression gating.
- **Golden-Thread 4-Stage Journey Bar, Bidirectional KFlow ↔ Code Split Studio & Sandbox Blast-Radius Radar (`/app` & `/v1/platform/studio/*`)**:
  - `POST /v1/platform/studio/kflow/sync`, `POST /v1/platform/studio/blast-radius`, `GET /v1/platform/studio/blast-radius`, `POST /v1/platform/studio/prompt-gate`, and `GET /v1/platform/studio/prompt-gate` with static AST line-span mapping (`Lstart–Lend`, zero `eval`/`exec`), `sync_sha256` drift digests, Seatbelt/Bubblewrap confinement receipts (`audit_sha256`), and inline Golden Eval prompt/schema regression gates (`gate_sha256`).
  - Sovereign CLI commands `keelway kflow-sync`, `keelway blast-radius`, and `keelway prompt-gate`, plus 5-method Tri-SDK parity across Python (`core.sdk`), TypeScript (`@keelway/sdk` `v1.1.0`), and Go (`github.com/keelway/keelway-go`).
- **Flight-Tape Time-Travel Debugger, OTel GenAI Wedge & Static AST LangGraph Migrator**:
  - `POST /v1/platform/traces/ingest` (with pre-storage DLP secret redaction), `GET /v1/platform/traces`, `POST /v1/platform/traces/{trace_id}/fork` (reusing `$0` cached upstream steps and computing frontier-to-OpenCore spend deltas), and `POST /v1/platform/traces/{trace_id}/promote-eval`.
  - `POST /v1/platform/migrate/langgraph` performing zero-`eval` static AST analysis to convert LangGraph `StateGraph` + `interrupt()` graphs into bounded KFlow topologies with injected `p10_human_gate` checkpoints, alongside `keelway traces` and `keelway migrate` CLI subcommands.
- **4-K Architecture Completion — KBrain Hybrid Memory Graph & KHub Air-Gapped Skill Mirror**:
  - Scope-governed workspace memory graph (`local_session < project < team < org`) via `POST /v1/platform/kbrain/facts`, `POST /v1/platform/kbrain/search` (BM25 + character 3-gram cosine hybrid recall), and `POST /v1/platform/kbrain/resolve-conflict` with fail-closed DLP secret rejection and P-10 owner/operator conflict resolution.
  - Air-gapped `.tar.gz` mirror export/import (`POST /v1/platform/khub/mirror/export` & `POST /v1/platform/khub/mirror/import`) hardened with symlink, hardlink, and path-traversal `filter="data"` confinement plus Ed25519/SHA-256 verification.
- **Enterprise OIDC/SCIM 2.0 Federation, Dual-Human P-10 Quorum & SIEM/OTLP Observability**:
  - SSRF-guarded `OIDC` federation (`PUT/GET /v1/platform/enterprise/oidc`, `POST /v1/platform/enterprise/oidc/exchange`) with AES-256-GCM encrypted signing keys and RFC 7643/7644 `SCIM 2.0` user provisioning (`POST/GET/PATCH /v1/platform/enterprise/scim/v2/Users`) synced with workspace RBAC. *(Erratum, KEEL-SEC-037: this is a self-issued HS256 shared-secret profile, not external IdP federation; SAML is not implemented. Responses disclose `federation_profile: "self_issued_hs256"`.)*
  - 2-of-2 distinct-signer Dual-Human P-10 Quorum (`POST /v1/platform/enterprise/p10-quorum/approve`, enforcing `RequesterCannotSelfApprove`), DLP-redacted OCSF v1.1 / ArcSight CEF / JSONL SIEM audit export (`GET /v1/platform/enterprise/siem/export`, `product.version="1.1.0"`), OpenTelemetry OTLP JSON & Prometheus metrics (`GET /v1/platform/observability/metrics`), and automated GitHub Release CycloneDX 1.5 SBOM + `SHA256SUMS.txt` attestation workflow (`.github/workflows/release-artifacts.yml`).

### Changed
- **Cross-Manifest `v1.1.0` Release Synchronization**: Synchronized release version `1.1.0` across `pyproject.toml`, `core.main:app`, `cli.py`, `@keelway/sdk`, Next.js website (`website/package.json`, `product-facts.json`, `openapi.json`), Homebrew formula (`Formula/keelway.rb`), SIEM/OTLP resource metadata, and GitHub Release artifacts workflow.

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
- **Formal TLA+ P-10 Gate Specification**: Added `specs/tla/P10HumanGate.tla` modeling separation-of-duty invariants (`RequesterCannotSelfApprove`, `NoUnapprovedMutationCommit`, `TerminalDecisionImmutability`). *(Erratum, KEEL-DOC-034: `specs/tla/` was never committed — no TLA+ specification exists in the repository. The P-10 gate is implemented and tested in code only.)*
- **Calibrated 5-Tier Pricing & BYOM 0% Token Markup**: Validated via MiroFish multi-persona simulation (`POST /v1/platform/pricing/simulate` & `keelway pricing-eval`): Community (`$0`), BYOM Seat (`$15/mo` annual, 0% markup), Pro (`$29/mo` annual), Team (`$49/mo` annual), and Enterprise Custom.
- **Zero-Friction Packaging & Installers**: Standalone Python wheel packaging (`pyproject.toml` `v1.0.0` bundling `core/studio` + `core/dev_app_dist`), Homebrew formula (`Formula/keelway.rb`), and `--dry-run` / `--help` support across `scripts/install.sh` and `website/public/install.sh`.

### Changed
- **Hardened Multi-Stage Container & Compose Stack**: Updated `Dockerfile` (`python:3.12-slim`, UID `10001:10001`, writable `/data` volume, bundling full `cli.py`, `core/`, `keelway/`, `research/`, and `evaluations/`) and `docker-compose.yml` (adding `keelway-platform` on `:7420` alongside `keelway-control-plane` on `:8000`, `keelway-runner`, and `ollama`).
- **GitHub Actions CI & Container Release Gates**:
  - Upgraded `.github/workflows/ci.yml` to run Python `3.11`/`3.12`/`3.14` + Linux Bubblewrap sandbox verification, Next.js 15 website + Unified `/app` Vitest/`axe-core` + TypeScript & Go SDK suites, and isolated wheel + Golden Suite + SBOM verification on every push and PR while keeping macOS Seatbelt + live Ollama verification dedicated to `.github/workflows/release-gate-macos.yml`.
  - Upgraded `.github/workflows/deploy.yml` to verify live container startup, HTTP readiness, diagnostic failure logs, and in-container `keelway eval-suite --category all --json`.
