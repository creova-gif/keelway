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

---

## 3. Next Candidate Backlog Tasks

1. **KEEL-CLUSTER-008**: Distributed Multi-Node vLLM / Ray GPU Cluster Scheduler & PostgreSQL Row-Locked Governance Adapter.
2. **KEEL-SDK-009**: Official Go Client SDK (`keelway-go`) with Streaming SSE & Typed Governance Errors.
