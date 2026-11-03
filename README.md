<div align="center">

# ⚡ Keelway by Sorvex Labs
### Sovereign Local-First AI Agent Runtime & Enterprise Governance Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![CI](https://github.com/creova-gif/kora/actions/workflows/ci.yml/badge.svg)](https://github.com/creova-gif/kora/actions/workflows/ci.yml)
[![Security Invariants](https://img.shields.io/badge/security-12%20Fail--Closed%20Invariants-orange.svg)](docs/SECURITY_INVARIANTS_AND_AUDIT_REPORT.md)
[![Hardware Attestation](https://img.shields.io/badge/hardware-Tier%202%20HAL%20(WORM%2FTPM%2FPIV)-purple.svg)](keelway/hal/)
[![Automated Tests](https://img.shields.io/badge/tests-79%20passed%20(100%25)-brightgreen.svg)](tests/)

*Built for zero vendor lock-in, fail-closed security invariants, immutable hash-chained audit trails, and hardware-attested trust.*

---

</div>

## 📌 Executive Summary

Modern AI agent frameworks suffer from systemic security and governance flaws:
1. **Unconstrained Execution**: Direct host mutation rights without air-gapped sandboxing or workspace boundaries.
2. **Opaque Approvals & Loop Runaways**: Automated self-approvals, infinite recursive tool loops, and unchecked budget drains.
3. **Malleable Audit Records**: Plain-text logs that can be rewritten or deleted after a security incident.

**Keelway** is a hardened, production-ready sovereign agent runtime and enterprise governance platform implementing the cumulative **Keelway v71 Architecture Specification**:
- **Zero-Copy Sandbox:** Lightweight `--shared` clones isolate code generation completely from host repositories.
- **Deny-by-Default Policy Engine:** Pre-flight checks deny sensitive files (`.env`, `credentials`, `id_rsa`) and unknown tools before execution.
- **Mandatory Two-Human Quorum (ADR-045/046):** Production changes require two distinct cryptographic approvals: **Security Lead** AND **Platform Owner** (self-quorum is strictly prohibited).
- **Cryptographic Audit Trail (FR-05/09):** Tamper-evident hash-chained event logger backed by SQLite in WAL mode with sealed compliance export bundles.
- **Tier 2 Hardware Attestation (ADR-051..083):** Real protocol wire schemas and conformance verifiers for Dual-WORM durable storage, TPM 2.0 quote/PCR replay, PIV smartcards with strict 72-hour CRL caps, and customer 2-of-3 offline root recovery.

---

## 🏛️ System Architecture

```text
                               ┌──────────────────────────────────────────────┐
                               │       Client Interfaces & Access Layers       │
                               │   CLI Tool  •  Web Dashboard  •  REST API    │
                               │           (http://127.0.0.1:8000)            │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │     Policy Pre-Flight & MCP Tool Bridge      │
                               │   • Deny-by-default tool authorization       │
                               │   • Egress blocking & sensitive file guard   │
                               │   • Signed Policy Bundles (anti-rollback)    │
                               └──────────────────────┬───────────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
        ┌─────────────────────────────┐                               ┌─────────────────────────────┐
        │     Isolated Workspace      │                               │   Paired Multi-Trial Eval   │
        │  • git clone --shared       │                               │   • Candidate scoring       │
        │  • Detached base commit     │                               │   • Mean, Std Dev, 95% CI   │
        └──────────────┬──────────────┘                               └──────────────┬──────────────┘
                       │                                                             │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │          Human Review Approval Gate          │
                               │   • Single human review (internal / dev)     │
                               │   • Mandatory Two-Human Quorum (production)  │
                               │   • Patch hash binding (mutation invalidates)│
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │        Append-Only Audit & Export (FR-09)    │
                               │   • SHA-256 hash chaining (seq:hash:prev)    │
                               │   • SQLite WAL crash-resilient storage       │
                               │   • Sealed compliance bundle with redaction  │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │      Tier 2 Hardware Attestation (HAL)       │
                               │   • Dual-WORM independent receipts (ADR-076) │
                               │   • TPM 2.0 Quote Verifier & PCR replay      │
                               │   • PIV smartcard strict 72h CRL cap         │
                               │   • 2-of-3 offline root recovery (ADR-082)   │
                               └──────────────────────────────────────────────┘
```

---

## ⚡ Fast Quickstart

### 1. Environment Setup
```bash
git clone https://github.com/creova-gif/kora.git
cd keelway
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Run All Automated Tests (79 Tests)
```bash
make test
# Or with pytest directly:
PYTHONPATH=. pytest tests -v
```

### 3. One-Click Interactive Developer Demo
Demonstrates the full 9-phase governed workflow and simulates an attacker trying to tamper with SQLite audit records:
```bash
make demo
```

### 4. Start Local Control Plane & Operator Dashboard
```bash
make serve
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## 💻 CLI Commands Reference

Keelway provides two unified CLI interfaces:
1. `keelway` (`cli.py`): Developer REPL, MCP server, diagnostics, workflows, memory, datasets.
2. `keelway-core` (`keelway.cli.main`): Governed run lifecycle, approval gates, verification, export, customer runner daemon.

### Developer Commands (`keelway`)
- `keelway doctor`: Verifies local environment, dependencies, and model connectivity.
- `keelway chat [--provider local|openai]`: Interactive stateful REPL with thinking token display.
- `keelway mcp --workspace <PATH>`: Serves read-only workspace tools over MCP stdio to Cursor, Claude Code, and Zed.
- `keelway brief --title "<TITLE>"`: Generates an evidence-grounded pull request brief.
- `keelway memory ingest <DOC> --scope <SCOPE>`: Scoped hybrid vector + lexical document search.
- `keelway dataset export`: Exports fine-tuning datasets from verified traces.

### Enterprise Governance Commands (`keelway-core`)
- `keelway-core init-demo --dir examples/demo_service`: Scaffolds sample Git repo.
- `keelway-core run --repo <PATH> --task "<TASK>" [--classification internal|production]`: Launches governed run.
- `keelway-core status --run-id <RUN_ID>`: Displays run metadata, token consumption, and audit events.
- `keelway-core verify --run-id <RUN_ID>`: Verifies mathematical integrity of the cryptographic audit chain.
- `keelway-core export --run-id <RUN_ID> --out bundle.json`: Exports sealed compliance bundle.
- `keelway-core runner --runner-id node-01 --org org_sorvex_demo`: Starts outbound customer runner daemon.

---

## 🔒 Security Invariants & Compliance

| # | Security Invariant | Specification Reference | Code Enforcement Module | Conformance Test Suite |
|:---|:---|:---|:---|:---|
| **1** | **Zero Unapproved Repository Mutations** | PRD-001 FR-02, ADR-002 | `keelway.sandbox.workspace` | `test_end_to_end_workflow.py` |
| **2** | **Deny-by-Default Policy Pre-Flight** | PRD-001 TB2/TB3 | `keelway.policy.engine` | `test_policy_engine.py` |
| **3** | **Anti-Rollback Monotonic Policy Epochs** | ADR-061 | `keelway.policy.bundle` | `test_policy_bundle.py` |
| **4** | **No Agent Self-Approval** | PRD-001 FR-07, ADR-046 | `keelway.approvals.service` | `test_approvals.py` |
| **5** | **Two-Human Quorum for Production** | ADR-045, ADR-046 | `keelway.approvals.quorum` | `test_quorum.py`, `test_production_quorum_run.py` |
| **6** | **Tamper-Evident Hash-Chained Audit Trail** | PRD-001 FR-05 | `keelway.audit.recorder` | `test_audit_chain.py` |
| **7** | **Crash-Resilient SQLite WAL Storage** | ADR-003 | `keelway.audit.store` | `test_audit_store.py` |
| **8** | **Sealed Compliance Export with Redaction** | PRD-001 FR-09 | `keelway.audit.export` | `test_audit_export.py` |
| **9** | **Outbound-Only Cross-Org Runner Isolation** | PRD-001 Sec 94-108, ADR-004 | `keelway.runner.daemon` | `test_runner_daemon.py` |
| **10** | **Quarantine & Credential Fencing** | PRD-001 Edge Cases, ADR-060 | `keelway.security.quarantine` | `test_quarantine.py` |
| **11** | **No Double Tool Execution** | PRD-001 Edge Cases | `keelway.core.retry` | `test_retry.py` |
| **12** | **Hard Token Ceilings & Budget Caps** | PRD-001 FR-10 | `keelway.models.gateway` | `test_model_gateway.py` |

---

## 📂 Project Organization

```text
keelway/
├── bin/keelway                            # Executable CLI launcher
├── cli.py                                 # Central developer CLI dispatcher
├── Dockerfile                             # Hardened multi-stage non-root container (UID 10001)
├── docker-compose.yml                     # Multi-container orchestration (Control Plane, Runner, Ollama)
├── Makefile                               # Developer workflow tasks
├── pyproject.toml                         # Unified packaging & test configuration
├── core/                                  # Core AI runtime, models, orchestration & studio
│   ├── agents/                            # Manifests, runtime guard, and macOS command sandbox
│   ├── api/                               # REST API, studio, approval relays (Telegram/WhatsApp)
│   ├── models/                            # Gateway & adapters (Local, Anthropic, OpenAI, Gemini)
│   ├── orchestration/                     # Agent loop, flight recorder, MCP, worktrees
│   ├── security/                          # Firewall, redaction, approval rules, air-gap
│   ├── storage/                           # Database, memory, workspace fs, ledger
│   └── studio/                            # Web IDE & Mission Control studio
├── keelway/                               # Enterprise Core Governance Platform (v71)
│   ├── hal/                               # Tier 2 Hardware Abstraction Layer
│   │   ├── worm.py                        # Dual-WORM independent receipt validator (ADR-076)
│   │   ├── tpm.py                         # TPM 2.0 quote verifier & PCR event-log replay (ADR-062/064)
│   │   ├── piv.py                         # PIV smartcard verifier & 72h CRL cap (ADR-051/053)
│   │   └── recovery.py                    # 2-of-3 offline root recovery verifier (ADR-082/083)
│   ├── core/                              # State machines, metadata DB, retry idempotency
│   ├── audit/                             # Hash-chained recorder, SQLite WAL store, sealed exporter
│   ├── policy/                            # Deny-by-default engine & signed policy bundles
│   ├── approvals/                         # Two-human quorum (ADR-045) & single human review
│   ├── evals/                             # Paired multi-trial statistical evaluation suite
│   ├── runner/                            # Customer VPC outbound runner daemon
│   └── api/                               # FastAPI control plane & hardware status routes
├── mobile/                                # Runnable React Native Expo mobile app (biometric approvals)
├── website/                               # Static landing page for Keelway by Sorvex Labs
├── docs/                                  # Specifications, ADRs, and developer quickstart guides
├── examples/                              # Sample demo service & interactive walkthrough scripts
└── tests/                                 # Full automated test suite (79 verified tests)
```
