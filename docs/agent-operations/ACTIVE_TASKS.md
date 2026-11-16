# Keelway — Active Task Registry

> **Purpose**: Centralized, version-controlled index of all engineering tasks across all AI agents and human contributors.  
> **Source of Truth**: Individual task documents reside in `docs/agent-operations/tasks/<TASK_ID>.md`.

---

## 1. Task State Overview

| Task ID | Title | Category | Current Status | Assigned Agent | Last Updated | Branch |
|---|---|---|---|---|---|---|
| **KEEL-HYBRID-001** | Unified Hybrid Model Gateway & Inference API | `MODELS / API` | `VERIFIED_COMPLETE` | Google Antigravity | 2026-11-11 | `main` |
| **KEEL-ENG-001** | Universal Multi-Agent System & CI Quality Gates | `ARCH / CI` | `VERIFIED_COMPLETE` | Google Antigravity | 2026-11-11 | `main` |
| **KEEL-SEC-002** | Linux Command Sandbox Bubblewrap CI Hardening | `SECURITY` | `VERIFIED_COMPLETE` | Google Antigravity (Sandbox & CI Lead) | 2026-11-13 | `main` |
| **KEEL-STUDIO-003** | Manifest Inspection Panel in Web Developer Studio | `UI / STUDIO` | `VERIFIED_COMPLETE` | Google Antigravity (Studio Lead) | 2026-11-13 | `main` |
| **KEEL-GOV-004** | Persistent SQLite WAL Multi-Tenant Governance & Audit Store | `SECURITY / GOV` | `VERIFIED_COMPLETE` | Google Antigravity (Governance Lead) | 2026-11-13 | `main` |
| **KEEL-SDK-005** | Official TypeScript SDK (`@keelway/sdk`) & Website Drift Gate | `SDK / DX` | `VERIFIED_COMPLETE` | Google Antigravity (SDK Lead) | 2026-11-13 | `main` |
| **KEEL-WEB-006** | Next.js 15 Flagship Website Redesign & 4 Competitive Upgrades | `WEBSITE / UX` | `VERIFIED_COMPLETE` | Google Antigravity | 2026-11-13 | `main` |
| **KEEL-PLATFORM-010** | Unified 10-View AI-Native Agent Platform, Marketplace Security, 5-Stream BYOM & Sovereign CLI TUI | `PLATFORM / FULLSTACK` | `VERIFIED_COMPLETE` | Google Antigravity (4-Agent Parallel Wave) | 2026-11-14 | `main` |
| **KEEL-MANIFEST-007** | Phase 2: Ed25519 Manifest Signing, SQLite WAL Platform Store, Enterprise Governance, Python/TS SDK Parity & `/marketplace` | `SECURITY / PLATFORM` | `VERIFIED_COMPLETE` | Google Antigravity (4-Agent Parallel Wave) | 2026-11-14 | `main` |
| **KEEL-CLUSTER-008** | Distributed Multi-Node GPU Cluster Scheduler, PostgreSQL `FOR UPDATE` Governance Adapter & Model Lifecycle Registry | `CLUSTER / GOV` | `VERIFIED_COMPLETE` | Google Antigravity (4-Agent Parallel Wave) | 2026-11-14 | `main` |
| **KEEL-SDK-009** | Official Zero-Dependency Go SDK (`keelway-go`), Marketplace Commercial Settlement Ledger & Cross-SDK Cluster Parity | `SDK / MARKETPLACE` | `VERIFIED_COMPLETE` | Google Antigravity (4-Agent Parallel Wave) | 2026-11-14 | `main` |
| **KEEL-DEVAPP-011** | Phase 4: 10-View Local Dev Tool (`:7420/app`) Full Persistence & Website `/playground` Cleanup | `DEV-APP / WEBSITE` | `VERIFIED_COMPLETE` | Google Antigravity (4-Agent Parallel Wave) | 2026-11-14 | `main` |
| **KEEL-RUNTIME-012** | Phase 5: Live SSE Agent/DAG Execution, AES-256-GCM Secret Vault, Multi-Workspace RBAC, Signed Webhooks & Tri-SDK Parity | `PLATFORM / SECURITY / SDK` | `VERIFIED_COMPLETE` | Google Antigravity (4-Agent Parallel Wave) | 2026-11-14 | `main` |
| **KEEL-PRICING-013** | Phase 6: Calibrated 5-Tier Pricing Ladder, MiroFish 5-Persona Market & Unit-Economics Swarm Simulator, Sovereign CLI Runtime & Operations Quota UI | `PRICING / EVAL / CLI / UI` | `VERIFIED_COMPLETE` | Google Antigravity (4-Agent Parallel Wave) | 2026-11-14 | `main` |
| **KEEL-SHIP-014** | Phase 7: Commercial Ship Readiness — MCP Control Plane, 16-Probe Golden & Red-Team Suite, Wheel/Homebrew Packaging & Tri-SDK Parity | `MCP / EVAL / PACKAGING / SDK / UI` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-15 | `main` |
| **KEEL-GA-015** | Phase 8: v1.0.0 General Availability — KFlow Topological DAG Engine, KSpaces CRDT Sync, CycloneDX 1.5 SBOM, Container/CI Release Hardening & Tri-SDK Parity | `DAG / CRDT / SBOM / CI / GA` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-15 | `main` (`v1.0.0`) |
| **KEEL-ENT-016** | Phase 9: Enterprise OIDC/SCIM 2.0 Federation, Dual-Human P-10 Quorum, SIEM Audit Streaming, OpenTelemetry/Prometheus Metrics & GitHub Release Automation | `ENTERPRISE / SIEM / OTLP / SDK / UI` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-15 | `main` |
| **KEEL-KBRAIN-017** | Phase 10: 4-K Sovereign Architecture Completion — KBrain Hybrid BM25/3-Gram Memory Graph, KHub Air-Gapped Skill Mirror, Tarfile Hardening & Tri-SDK Parity | `KBRAIN / KHUB / SECURITY / SDK / UI` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-15 | `main` |
| **KEEL-DEVX-018** | Phase 11: Flight-Tape Time-Travel Debugger, OTel GenAI Trace Wedge, 1-Click Trace-to-Eval Promotion & LangGraph Static AST Migrator | `DEVX / OTEL / REPLAY / AST / SDK / UI` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-15 | `main` |
| **KEEL-STUDIO-019** | Phase 12: Golden-Thread 4-Stage Journey Bar, Bidirectional KFlow ↔ Code Split Studio, Interactive Flight-Tape Waterfall Scrubber, Sandbox Blast-Radius Radar & Prompt Regression Gate | `STUDIO / AST / SANDBOX / SDK / UX` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-15 | `main` |
| **KEEL-LAUNCH-020** | Phase 13: Zero-Install Homepage Golden-Thread Studio Showcase (`/#studio-showcase`) & Official Signed `v1.1.0` GitHub Release | `WEBSITE / STUDIO / RELEASE / GA` | `VERIFIED_COMPLETE` | Google Antigravity (2-Agent Parallel Wave) | 2026-11-15 | `main` (`v1.1.0`) |
| **KEEL-DEBUG-021** | Phase 14: Live Step-Through Debugger Breakpoints & Official VS Code / Cursor Extension Bridge | `DEBUGGER / IDE-BRIDGE / SDK / UI` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-15 | `main` |
| **KEEL-KFLOW-022** | Phase 15: Bounded Cyclic & Conditional KFlow Sub-Graphs + Pre-Run Cost/Privacy Autopilot | `KFLOW / CYCLIC / AUTOPILOT / SDK / UI` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-15 | `main` |
| **KEEL-HEAL-023** | Phase 16: Typed Structured-Output & Content-Block Normalizer + Autonomous Self-Healing Failure Root-Causer | `SCHEMA / HEALING / EVAL / SDK / UI` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-15 | `main` |
| **KEEL-SAFETY-024** | Phase 17: Tier 3 `:7420/app` Dev-Tool Moats (Formal Safety Verifier + Federated Edge Mesh) & Minimalist YC Website Curation | `SAFETY / MESH / SDK / UI / WEBSITE` | `VERIFIED_COMPLETE` | Google Antigravity (4-Agent Parallel Wave) | 2026-11-15 | `main` |
| **KEEL-HARNESS-025** | Phase 18: Universal Coding-Agent Co-Harness (`Claude Code`/`Cursor`/`Codex` PreToolUse Gate + Single-Use P-10 Tickets) & Parallel Worktree CI Gate | `HARNESS / CIGATE / SDK / VSCODE / UI` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-16 | `main` |
| **KEEL-DISTILL-026** | Phase 19: Semantic Prompt Cache, Shadow Dual-Run Router & Frontier-to-OpenCore QLoRA Distillation Flywheel | `CACHE / DISTILL / SDK / VSCODE / UI` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-16 | `main` |
| **KEEL-LOCK-027** | Phase 20: Cryptographic MCP & Skill Lockfile (`keelway.lock`), Tool-Poisoning / Rug-Pull Firewall & Conformance Benchmark | `SUPPLY-CHAIN / LOCK / BENCH / SDK / UI` | `VERIFIED_COMPLETE` | Google Antigravity (3-Agent Parallel Wave) | 2026-11-16 | `main` |
| **KEEL-WEB-028** | Brand/UI Refresh: Monochrome Zinc Palette, Shared BrandMark & PWA/SEO Surfaces | `WEBSITE / UX / DEV-APP` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `feature/KEEL-WEB-028-brand-refresh` |
| **KEEL-WEB-029** | Post-Merge Brand Polish: BrandMark ARIA, web-console Token Drift, fault-Token Migration & Dead-Code Sweep | `WEBSITE / UX / DEV-APP / A11Y` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-WEB-029-brand-polish` |
| **KEEL-SEC-030** | Managed First-Party Manifest Signing Key (env/key-file resolution, fail-closed, dev gate) | `SECURITY / SUPPLY-CHAIN / MARKETPLACE` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-SEC-030-managed-signing-key` |
| **KEEL-SEC-031** | Payment Broker Env Secret Wiring (`KEELWAY_PAYMENT_BROKER_SECRET`, fail-closed preserved) | `SECURITY / BILLING / FAIL-CLOSED` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-SEC-031-payment-secret` |
| **KEEL-ENG-032** | Python Dependency Lockfile (`requirements.lock` + freshness gate in engineering gates) | `ENGINEERING / SUPPLY-CHAIN / DEVEX` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-ENG-032-python-lockfile` |
| **KEEL-ENG-033** | ADR-0042 Phase 1: `keelway doctor --migration-check` Import Census | `ENGINEERING / CONSOLIDATION / DEVEX` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-ENG-033-migration-check` |
| **KEEL-DOC-034** | Documentation Drift Sweep: v1.1.0 Version Sync, TLA+ Claim Errata, Flight-Recorder Path Corrections | `DOCUMENTATION / DRIFT / PRODUCT-TRUTH` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-DOC-034-drift-sweep` |
| **KEEL-WEB-035** | VS Code Extension Webview Palette Migration (slate/blue → zinc + teal CTA) | `WEBSITE / UX / EXTENSION / BRAND` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-WEB-035-vscode-palette` |
| **KEEL-ENG-036** | `core/config.py` No-Pydantic Fallback `default_factory` Fix | `ENGINEERING / DEVEX / MINIMAL-ENV` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-ENG-036-config-fallback` |
| **KEEL-SEC-037** | OIDC Federation Profile Disclosure (`self_issued_hs256`) & SAML Claim Correction | `SECURITY / PRODUCT-TRUTH / ENTERPRISE-IDENTITY` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-SEC-037-oidc-profile` |
| **KEEL-ENG-038** | Simulated OpenCore Response Disclosure (`simulated` flag, mock-backend routing_reason) | `ENGINEERING / PRODUCT-TRUTH / INFERENCE` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-ENG-038-simulated-disclosure` |
| **KEEL-ENG-039** | `/v1/models` Installed + Simulated Flags (registry-vs-reality disclosure) | `ENGINEERING / PRODUCT-TRUTH / MODELS` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-ENG-039-model-flags` |
| **KEEL-ENG-040** | Ollama Thinking-Model Handling (`think` flag + `message.thinking` fallback) | `ENGINEERING / INFERENCE / LOCAL-MODELS` | `VERIFIED_COMPLETE` | Devin | 2026-11-16 | `fix/KEEL-ENG-040-thinking-models` |

---

## 2. Completed Milestones

- **KEEL-HYBRID-001 & v1 Hybrid Control Plane**: 6-layer OpenCore (`Ollama`/`vLLM` + SHA-256 weight manifests + African-language QLoRA recipes) + Commercial Frontier (`Gemini`, `OpenAI`, `Anthropic`) gateway, stateful `/v1/responses`, 4D routing provenance (`/v1/routing/explain`), speculative decoding, MiroFish swarm harness, Python SDK v1, and 6-tab Web Console.
- **KEEL-ENG-001**: Canonical `AGENTS.md`, Claude/Antigravity/Devin adapters, unified engineering standards, quality gates, and cross-agent handoff protocol established.
- **KEEL-SEC-002**: Hardened Linux `BubblewrapBackend` mount-tree ordering for Ubuntu 24.04 (`/home/runner` masked tmpfs `--dir` creation, `--clearenv`, control-char validation, `Sandbox.diagnose()` AppArmor/userns sysctl reporting) and fail-closed Linux CI escape-probe enforcement (`36 passed` on macOS + live `bwrap` suite on `ubuntu-latest`).
- **KEEL-STUDIO-003**: Added `GET /v1/studio/manifests` and `POST /v1/studio/manifests/inspect` (non-mutating HMAC-SHA256 verification & security warnings) plus the air-gap CSP-compliant **Manifests** master-detail inspector and live JSON validator in Keelway Studio (`:7420`).
- **KEEL-GOV-004**: Shipped `SQLiteGovernanceStore` (`PRAGMA journal_mode=WAL`) backing `TenantGovernanceController` so `TenantPolicy`, salted-SHA256 `kw_live_*` keys, USD spend totals, and the Genesis-anchored SHA-256 governance audit chain survive restarts and detect out-of-band SQLite row tampering (`GET /v1/governance/persistence`).
- **KEEL-SDK-005**: Shipped zero-dependency TypeScript/JS SDK (`sdk/typescript` — `@keelway/sdk` v1.0.0) with chunk-boundary-safe SSE streaming and full typed error parity (`7/7` Node test suites), plus synchronized `product-facts.json` and `tests/test_website_facts.py`.
- **KEEL-WEB-006**: Built the 7-route Next.js 15 + React 19 + Tailwind + Radix + Framer Motion website (`website/`) with Global `Cmd+K` instant search across `226` targets (`186` OpenAPI 3.1 endpoints), 60fps Studio & Apple Metal runtime captures, empirical TTFT/Cost scatter plots, and a rate-limited live `/api/sandbox/routing-explain` network playground.
- **KEEL-PLATFORM-010 & KEEL-MANIFEST-007**: Shipped the 10-View Unified Sovereign Platform (`IDE`, `Agents`, `Project Manager`, `Product`, `Automation`, `Marketplace`, `Security`, `Documentation`, `Operations`, `No-Code Builder`), 5-stream subscription + BYOM governance, Ed25519 manifest signing (`sorvex-labs-ed25519-v1`), `SQLitePlatformStore` WAL persistence, Enterprise retention/compliance (`SOC2`/`HIPAA`/`ISO27001`/`GDPR`), 20-method Python & TypeScript SDK parity (`client.platform`), Dev App live `/v1/platform/*` hydration, and dedicated `/marketplace` + `/playground` website routes.
- **KEEL-CLUSTER-008 & KEEL-SDK-009**: Shipped the Distributed Multi-Node GPU Cluster Scheduler (`vllm`/`ray_serve`/`ollama_metal`), PostgreSQL 16+ `SELECT ... FOR UPDATE` Governance Adapter, Model Lifecycle Canary/Stable Registry, Marketplace Commercial Settlement Ledger (`85/15`, `80/20`, `0/100` integer-cent splits + SHA-256 receipts), Official Zero-Dependency Go Client SDK (`sdk/go` — `keelway-go`), Python/TS `client.cluster` parity, CLI `keelway cluster`, Dev App Operations Cluster & Settlement UI, and customer-clean Website Quickstart & Docs sync (`219` OpenAPI 3.1 endpoints).
- **KEEL-SHIP-014, KEEL-GA-015 (`v1.0.0`), KEEL-ENT-016, KEEL-KBRAIN-017 & KEEL-DEVX-018**: Completed the 4-K Sovereign Architecture (**KFlow**, **KSpaces**, **KBrain**, **KHub**), Enterprise OIDC/SCIM 2.0 + 2-of-2 P-10 Quorum + SIEM/OTLP Metrics, MCP (`2025-06-18`) + 16-probe Golden/Red-Team Evals, and the Flight-Tape Time-Travel Debugger + OTel GenAI Trace Wedge + 1-Click Trace-to-Eval Promotion + `keelway migrate` Static AST Importer across CLI, Python/TS/Go SDKs, and `268` OpenAPI 3.1 endpoints (`19` verified product features).

---

## 3. Next Candidate Backlog Tasks

All v1.0 Unified Platform, Cluster Control Plane, Marketplace Settlement, and Tri-Language SDK (`Python`, `TypeScript`, `Go`) backlog items are `VERIFIED_COMPLETE`.
