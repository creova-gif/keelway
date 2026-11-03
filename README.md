# Keelway by Sorvex Labs

> **Customer-Managed Local Governance Platform for AI-Powered Software Change**  
> *Production Engineering Implementation — Fully Tested Commercial Release*

---

## 1. Overview & Golden Path

Keelway provides a fail-closed, customer-managed governance envelope around AI coding agents. It ensures that no agent can directly mutate a customer's production repository, bypass policy checks, or deploy code without verified human approval, paired evaluation scoring, and an immutable cryptographic audit trail.

### The Golden Path (PRD-001)
1. **Local Authentication & Context Binding:** Enforces org, project, actor, and least-privilege repository scope.
2. **Signed Policy Bundle Distribution (`keelway.policy.bundle`):** Cryptographically signed corporate policy bundles with anti-rollback monotonic epochs (ADR-061).
3. **Policy Pre-Flight (`POST /v1/policy/decide`):** Deny-by-default tool authorization. Egress network calls and sensitive file targets (`.env`, `credentials`, `id_rsa`) are blocked before invocation.
4. **MCP Tool Governance Bridge (`keelway.mcp.bridge`):** Intercepts all Model Context Protocol tool requests, evaluating action digests and paths fail-closed.
5. **Isolated Workspace:** Uses lightweight, zero-copy shared git clones (`--shared`) to guarantee the host repository is never touched or dirtied.
6. **Model Gateway & Budget Enforcement:** Bounded token ceiling and cost monitoring with hard cancellation stops. Supports local Ollama (`localhost:11434`), local vLLM (`localhost:8000`), OpenAI-compatible providers, and an offline deterministic mock adapter.
7. **Paired Multi-Trial Evaluation Runner (`keelway.evals.suite`):** Automatically scores candidate patches over repeated trials, computing mean, standard deviation, and 95% confidence intervals against baseline quality thresholds.
8. **Two-Human Quorum Approval Gate (ADR-045/ADR-046):** For production changes, mandates independent cryptographic approvals from two distinct authorized humans: **Security Lead** AND **Platform Owner**. Rejects self-quorum (same person holding multiple roles cannot count twice) and automated agent identities.
9. **PR & Staging Promotion:** Generates customer-owned Git pull requests and triggers staging CI webhooks with immutable receipt digests.
10. **Cryptographic Audit Trail:** Append-only hash-chained event recorder (`seq`, `prev_hash`, `payload_digest`, `hash`) backed by SQLite in WAL mode with crash-recovery and full mathematical verification.
11. **GitHub App Webhooks:** Ingests and verifies `X-Hub-Signature-256` signed webhooks to reconcile PR status and CI check runs into the audit trail.
12. **Customer Runner Daemon:** Outbound-only VPC/on-prem agent daemon with time-bound cryptographic enrollment, repo allowlists, and cross-org job isolation.
13. **Security Quarantine & Revocation (`keelway.security.quarantine`):** Revokes compromised credentials and freezes compromised runs with forensic event retention.
14. **Bounded Retries & Idempotency (`keelway.core.retry`):** Bounded exponential retries for idempotent actions; strictly prohibits automatic retries for side-effecting operations to prevent double tool execution.
15. **Sealed Audit Export (FR-09):** Export sealed, portable verification bundles with prompt redaction and digital signatures for compliance audits.

---

## 2. Directory Layout

```
keelway/
├── Dockerfile                   # Hardened multi-stage non-root container image (UID 10001)
├── docker-compose.yml           # Local control plane & Ollama orchestration
├── pyproject.toml               # Package definition and test runners
├── .github/workflows/ci.yml     # Automated CI verification workflow
├── keelway/
│   ├── core/
│   │   ├── models.py            # Pydantic schemas (RunManifest, AuditEvent, etc.)
│   │   ├── database.py          # Relational multi-tenant metadata storage (orgs, projects, envs)
│   │   ├── retry.py             # Bounded retries and idempotency handler
│   │   └── runner.py            # GovernedRunCoordinator runtime supervisor
│   ├── audit/
│   │   ├── recorder.py          # Tamper-evident hash-chained event log & verifier
│   │   ├── store.py             # Crash-resilient SQLite WAL store with monotonic checks
│   │   └── export.py            # Cryptographic audit export bundle & prompt redactor
│   ├── policy/
│   │   ├── engine.py            # Deny-by-default policy engine & decision signers
│   │   └── bundle.py            # Central signed policy bundles & anti-rollback epochs
│   ├── sandbox/
│   │   └── workspace.py         # Isolated git workspace & bounded command runner
│   ├── mcp/
│   │   └── bridge.py            # MCP JSON-RPC tool interception and policy governance
│   ├── models/
│   │   └── gateway.py           # Model gateway (Ollama, vLLM, OpenAI, Mock) & token ceilings
│   ├── evals/
│   │   ├── engine.py            # Paired evaluation runner against golden fixtures
│   │   └── suite.py             # Multi-trial statistical evaluator (mean, std dev, 95% CI)
│   ├── approvals/
│   │   ├── service.py           # Single-human approval service & patch hash binding
│   │   └── quorum.py            # Two-Human Quorum approval engine (ADR-045, ADR-046)
│   ├── git_ci/
│   │   ├── service.py           # Governed PR creation & staging CI notifications
│   │   └── github.py            # GitHub App webhook signature verification & event parsing
│   ├── runner/
│   │   └── daemon.py            # Customer VPC/on-prem outbound runner daemon
│   ├── security/
│   │   └── quarantine.py        # Credential revocation, run freezing & forensic retention
│   ├── hal/
│   │   ├── worm.py              # Dual independent WORM storage receipts & publication cert validator (ADR-076)
│   │   ├── tpm.py               # TPM 2.0 quote verifier, measured boot event-log replay & monotonic NV counters (ADR-062/064)
│   │   ├── piv.py               # PIV smartcard verifier & strict 72-hour CRL staleness cap (ADR-051/053)
│   │   └── recovery.py          # Customer 2-of-3 offline root recovery verifier & DENY_OLD transition (ADR-082/083)
│   ├── api/

│   │   ├── routes.py            # FastAPI endpoints matching API contracts, webhooks & hardware status
│   │   └── app.py               # Main application & operator web dashboard
│   └── cli/
│       └── main.py              # Local operator CLI (`keelway run`, `keelway serve`, etc.)
└── tests/
    ├── test_approvals.py        # Single-human gate, no self-approval, mutation rejection
    ├── test_audit_chain.py      # SHA-256 hash chaining & tamper detection
    ├── test_audit_export.py     # Export bundle sealing, redaction & signature
    ├── test_audit_store.py      # SQLite WAL persistence & crash recovery
    ├── test_end_to_end_workflow.py # Full golden path, REST API, and hardware status endpoints
    ├── test_eval_gating.py      # Evaluation score thresholds and blocking
    ├── test_github_webhooks.py  # GitHub App webhook HMAC verification & CI reconciliation
    ├── test_mcp_bridge.py       # MCP tool interception, denial & execution
    ├── test_metadata_db.py      # Multi-tenant relational persistence & isolation
    ├── test_model_gateway.py    # Model routing, capabilities, and token budget cutoff
    ├── test_multi_trial_eval.py # Multi-trial statistics & confidence interval gating
    ├── test_policy_bundle.py    # Signed policy bundles & monotonic anti-rollback
    ├── test_policy_engine.py    # Deny-by-default rules and signature verification
    ├── test_production_quorum_run.py # Full production run with ADR-045 two-human quorum
    ├── test_quarantine.py       # Credential revocation & run freezing
    ├── test_quorum.py           # Two-human quorum, self-quorum block & bot rejection
    ├── test_retry.py            # Bounded idempotent retries & no double tool execution
    ├── test_runner_daemon.py    # Customer runner enrollment, allowlists & cross-org blocking
    ├── test_tier2_worm.py       # Tier 2 Dual-WORM independent receipt verification & emulator rejection
    ├── test_tier2_tpm.py        # Tier 2 TPM 2.0 quote verification, event-log replay & anti-replay nonces
    ├── test_tier2_piv.py        # Tier 2 PIV hardware key verification & strict 72-hour CRL staleness rejection
    └── test_tier2_recovery.py   # Tier 2 2-of-3 offline root recovery, role separation & DENY_OLD cutover
```

---

## 3. Running Keelway

### Running the Full Test Suite (79 Tests)
```bash
PYTHONPATH=keelway pytest keelway/tests -v
```
All 79 automated tests across Tier 0 (Core MVP), Tier 1 (Production Foundations), and Tier 2 (Hardware Abstraction Layer & Conformance Verifiers) run and pass without external network dependencies.



### Starting the Web Dashboard & Local Control Plane
```bash
PYTHONPATH=keelway python -m keelway.cli.main serve --host 127.0.0.1 --port 8000
```
Open your browser to `http://127.0.0.1:8000` to access the interactive operator dashboard, launch runs, review diffs, grant single or two-human approvals, and verify audit chains.

### Running a Governed Change via CLI
```bash
# 1. Scaffold a demo repository
PYTHONPATH=keelway python -m keelway.cli.main init-demo --dir examples/demo_service

# 2. Launch governed change against the demo repository
PYTHONPATH=keelway python -m keelway.cli.main run --repo examples/demo_service --task "Add telemetry healthcheck"
```

### Running an Outbound Customer Runner Daemon
```bash
PYTHONPATH=keelway python -m keelway.cli.main runner --runner-id node-01 --org org_sorvex_demo --server http://127.0.0.1:8000
```


### Verifying and Exporting Audit Logs
```bash
# Verify integrity of a run
PYTHONPATH=keelway python -m keelway.cli.main verify --run-id <RUN_ID>

# Export sealed audit bundle for compliance
PYTHONPATH=keelway python -m keelway.cli.main export --run-id <RUN_ID> --out audit_bundle.json
```

### Running via Docker Compose
```bash
cd keelway && docker compose up -d
```

---

## 4. Security Invariants Enforced

| Invariant | Specification Reference | Implementation Status |
|:---|:---|:---|
| **Zero Unapproved Mutations** | PRD-001, ADR-002 | **ENFORCED** (Shared workspace clone, diff must be approved before PR) |
| **Two-Human Quorum (Prod)** | ADR-045, ADR-046 | **ENFORCED** (Requires Security Lead AND Platform Owner; no single person counts twice) |
| **No Agent Self-Approval** | PRD-001 FR-07, ADR-046 | **ENFORCED** (Rejects any automated identity, bot, or agent) |
| **MCP Tool Interception** | PRD-001 TB2/TB3 | **ENFORCED** (Intercepts external MCP tools, checking arguments & paths fail-closed) |
| **Monotonic Anti-Rollback** | ADR-061 | **ENFORCED** (Policy bundle loader rejects any version `< highest_accepted_epoch`) |
| **Signed Policy Bundles** | PRD-001, ADR-061 | **ENFORCED** (HMAC-SHA256 signature verification over canonical bundle JSON) |
| **Tenant DB Partitioning** | 04_API_AND_DATA_CONTRACTS | **ENFORCED** (SQLite WAL metadata database scoped strictly by `org_id`) |
| **Tamper-Evident Audit Chain** | PRD-001 FR-05, FR-09 | **ENFORCED** (Sequential block hash verification detects any altered or dropped events) |
| **Durable Audit Store** | PRD-001 FR-05, ADR-003 | **ENFORCED** (SQLite WAL store with crash recovery and chain discontinuity checks) |
| **Sealed Audit Bundle Export** | PRD-001 FR-09 | **ENFORCED** (Portable compliance export with root hash seal and prompt redaction) |
| **Outbound Customer Runner** | PRD-001 v2, ADR-004 | **ENFORCED** (Outbound-only agent daemon with repo allowlists and cross-org blocking) |
| **Credential Revocation** | PRD-001 Edge Cases, ADR-060 | **ENFORCED** (Quarantine service fences compromised tokens and freezes active runs) |
| **No Double Tool Execution** | PRD-001 Edge Cases | **ENFORCED** (Idempotency handler prohibits retries on side-effecting operations) |
| **Multi-Trial Eval Gating** | PRD-001 Section 76 | **ENFORCED** (Statistical confidence interval checks eliminate eval nondeterminism) |
| **Budget Hard Stop** | PRD-001 FR-10 | **ENFORCED** (`BudgetExceededError` terminates run on ceiling breach) |

---

## 5. Scope Boundaries & Tier 2 Hardware Integration Strategy

- **P0 MVP (100% Implemented & Passing):** Core governed workflow, policy pre-flight, sandboxed workspace, model gateway, eval engine, human approval gate, PR/staging notifications, hash-chained audit logging, REST API, CLI, and interactive web dashboard.
- **P1 Production Foundations (100% Implemented & Passing):** Persistent SQLite WAL audit store with monotonic crash recovery, GitHub App HMAC webhook reconciliation, local Ollama/vLLM adapters, customer runner daemon with cross-org isolation, exportable compliance bundles, two-human quorum (ADR-045/ADR-046), signed policy bundles with anti-rollback epochs (ADR-061), MCP tool interception bridge, credential quarantine service, idempotent retry engine, and containerization manifests (Dockerfile + docker-compose.yml + ci.yml).
- **Tier 2 Enterprise Hardware Integration (HAL Implemented & Conformance Tested):**
  Rather than falsely simulating physical hardware and marking it as certified, Keelway implements an authentic **Hardware Abstraction Layer (HAL)** in `keelway.hal.*` alongside strict negative oracle test suites:
  1. **Dual Independent WORM Storage (`keelway.hal.worm`):** Enforces dual signed durable receipts from independent storage failure domains before authorizing publication certificates. Strictly rejects unqualified software emulators when production hardware is required (`ERR_WORM_UNQUALIFIED_EMULATOR_PROHIBITED_IN_PROD`).
  2. **TPM 2.0 Quote Verifier & Measured Boot Replay (`keelway.hal.tpm`):** Implements normative PCR event-log replay (`PCR_extend(PCR_n, event_digest) = SHA256(PCR_n || event_digest)`), golden boot profile matching, single-use anti-replay nonce consumption, and monotonic NV counter rollback prevention.
  3. **PIV Smartcard PKI Verifier & 72-Hour CRL Engine (`keelway.hal.piv`):** Verifies hardware-held smartcard credentials (prohibiting software private keys per ADR-051) and enforces a strict, fail-closed 72-hour maximum CRL staleness ceiling (`ERR_CRL_STALE_EXCEEDS_72_HOURS` per ADR-053).
  4. **Customer 2-of-3 Offline Root Recovery Protocol (`keelway.hal.recovery`):** Implements ADR-082 and ADR-083 for emergency controller root key replacement. Mandates two distinct hardware-held signatures from three enrolled custodians, guarantees role separation (Security Lead + Platform Owner), prevents epoch rollback, and enforces `DENY_OLD` before `ENABLE_NEW` transition execution.
  5. **Hardware Status Observability (`GET /v1/system/hardware-status`):** Exposes live qualification metadata so operators and compliance auditors can distinguish certified physical appliances from staging emulators.

