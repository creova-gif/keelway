# Keelway v0.9.0-beta Release Notes
**Release Version:** `v0.9.0-beta`  
**Target Release Date:** November 15, 2026  
**Engineering Authority:** Sorvex Labs  
**License:** Apache License, Version 2.0  
**Document Classification:** Public Beta Developer Preview & Product Truth Specification (Section P0-D)  

---

## 1. Executive Summary

Sorvex Labs is proud to announce the developer preview of **Keelway v0.9.0-beta**, the sovereign AI developer environment and autonomous agent engineering studio. 

Keelway is engineered from the ground up for software teams operating under strict regulatory boundaries, proprietary IP requirements, and air-gapped security mandates. Built upon the foundational principle of absolute developer sovereignty, Keelway provides an integrated environment where autonomous coding agents work strictly inside local, OS-level sandboxes powered by open-weight models, with zero external network egress by default.

### Key Highlights of the v0.9.0-beta Release:
* **Unified Dual-Mode Architecture:** IDE Mode and Agent Builder Mode run on the exact same sandboxed runtime engine (`AutonomousAgentLoop`), eliminating secondary execution layers.
* **The Unified 6-Stage Proof Strip UX:** A transparent, non-hyped execution pipeline (`INSPECT` $\rightarrow$ `PLAN` $\rightarrow$ `AUTHORIZE` $\rightarrow$ `EXECUTE` $\rightarrow$ `VERIFY` $\rightarrow$ `SEAL`) providing continuous cryptographic verification.
* **KStack Role Skills Catalog (8 Built-In):** Versioned, hash-pinned agent capabilities (`plan`, `investigate`, `review`, `qa`, `security`, `ship`, `modernize`, `repomap-sync`).
* **AgentBuilder & Starter Templates (6 Templates):** Instant scaffolding for specialized, bounded agents (`test-fixer`, `code-reviewer`, `security-auditor`, `feature-scaffolder`, `doc-writer`, `dependency-modernizer`).
* **KHub Universal Importer & Air-Gap Mirror:** Cryptographically validated, offline skill bundle distribution for enterprise disconnected environments (`keelway hub mirror`).
* **10-Axis System Doctor Diagnostics:** Comprehensive pre-flight system validation via `keelway doctor` across database, workspace, model gateway, air-gap, entitlements, SBOM, HAL, KStack, templates, and sandboxing.
* **Uncompromising Product Truth:** Strict disclosure and unambiguous labeling of software-simulated subsystems, provisional runtime packages, and hardware boundaries.

---

## 2. Core Sovereign Invariants

Keelway enforces three non-negotiable architectural invariants across all execution paths:

### 2.1 Local Open-Weight Inference
Keelway is designed to run entirely on local, sovereign hardware. Local open-weight inference is natively supported via standard API adapters:
* **Supported Backends:** Ollama, vLLM, llama.cpp server, and LM Studio. Keelway uses a model you have installed: the configured one, else the one recommended for your RAM, else any installed chat model.
* **Hardware Acceleration:** Provided by the inference backend (for example Ollama uses Metal on Apple Silicon and CUDA/ROCm on Linux); Keelway does not add its own.
* **Autonomous Reasoning:** ReAct agent loops formulate step plans, inspect codebases, execute tool calls, and evaluate syntax locally without round-tripping code through commercial clouds.

### 2.2 Fail-Closed Zero-Egress Default (`network: none`)
* **Local first:** requests go to the local model at $0.00. Commands the agent runs inside the verified sandbox get no network. Air-gap mode (off by default) drops every cloud request in the model gateway.
* **Cloud only when configured, and never hidden:** a cloud provider is used only if you added its API key. Without air-gap, a non-private request falls back to the cloud when the local model is unreachable or fails, and the response's `routing_reason` says so (`fell back to ...`). Requests marked `private` never leave the machine and fail instead.
* **Explicit Escalation Controls:** Cloud inference routing is supported only when the operator explicitly inputs API credentials, configures strict token/cost ceilings, signs an authorization prompt, and enables the hybrid gateway.

### 2.3 Fail-Closed OS Sandbox Confinement
Every agent tool execution and subprocess mutation is confined within operating-system-level process sandboxes:
* **macOS Confinement:** Enforced via Apple Seatbelt (`sandbox-exec`) profiles, restricting filesystem writes strictly to the isolated target workspace while masking sensitive user files (`~/.ssh`, `~/.aws`, `~/.gnupg`, environment dotfiles).
* **Linux Confinement:** Enforced via Bubblewrap (`bwrap`), applying unshared network namespaces (`--unshare-net`), isolated tmpfs mounts, read-only system roots, and strict workspace bind mounts.
* **Protection of Git & Configuration:** Agent mutations are forbidden from directly altering `.git/hooks`, `.git/config`, or internal `.keelway` metadata without explicit operator quorum.

---

## 3. Studio Experience & The Unified Proof Strip

Keelway Studio delivers a high-density, responsive developer workspace engineered with a clean, telemetry-free design system (self-hosted `Inter` and `JetBrains Mono` fonts).

```
+-----------+      +--------+      +-------------+      +-----------+      +----------+      +--------+
|  INSPECT  | ---> |  PLAN  | ---> |  AUTHORIZE  | ---> |  EXECUTE  | ---> |  VERIFY  | ---> |  SEAL  |
+-----------+      +--------+      +-------------+      +-----------+      +----------+      +--------+
```

### The 6-Stage Proof Strip UX
Both IDE Mode and Agent Builder Mode render the unified 6-stage Proof Strip directly from the authoritative 16-member runtime state machine (`TaskState`):

1. **`INSPECT` (Context & Air-Gap Inspection):** Audits workspace symbols, AST dependency graphs, local model availability, and verifies zero-egress boundaries before any task action begins.
2. **`PLAN` (Deterministic Planning):** Constructs a bounded, directed execution graph with hard step limits, cost ceilings, and blast-radius estimations based on module depth.
3. **`AUTHORIZE` (Runtime Authorization):** Enforces explicit permission gates. Risky mutations, shell commands, or out-of-scope paths trigger interactive operator approval or multi-human quorum signing.
4. **`EXECUTE` (Tool Execution & Mutation):** Executes authorized tool calls inside the verified OS sandbox. Tracks all file mutations and generates structured diff records.
5. **`VERIFY` (Evidence & Test Verification):** Executes automated test suites in the sandbox, verifying process exit codes, stdout/stderr streams, and regression assertions.
6. **`SEAL` (Cryptographic Flight-Tape Seal):** Appends every execution event to a SHA-256 hash-chained flight tape and records a tamper-evident audit entry. (The enterprise audit log separately exposes a Merkle root and inclusion proofs at `/v1/audit/merkle/root`.)

### Live AST Diff Review & Flight Recorder Replay
* **Diffs:** the Studio shows a line diff of each proposed change before you approve it. The AST index (`core/storage/ast_index.py`) powers symbol search and references; it does not drive the diff view.
* **Flight Tape Replay:** Every execution produces a deterministic flight recording (`.flight.jsonl`). Developers can scrub back through agent thoughts, tool inputs, sandbox outputs, and terminal snapshots to debug unexpected behaviors.

---

## 4. KStack Composable Role Skills (8 Built-In)

Keelway v0.9.0-beta packages the complete **KStack Skills Suite** (`core/kstack/`), governed by a signed, versioned catalog manifest (`core/kstack/manifest.json`, format `kstack_skills_manifest_v1`):

| Skill Name | Role Specialist | Contract Inputs | Contract Outputs | Enforced Permissions |
|---|---|---|---|---|
| `kstack/plan` | **Architect** | `goal`, `repo_context` | `plan_steps`, `files_affected`, `blast_radius` | `draft` |
| `kstack/investigate` | **Debugger** | `error_trace`, `failing_test` | `reproduced`, `root_cause`, `affected_components`, `minimal_repro` | `read`, `execute_restricted` |
| `kstack/review` | **Reviewer** | `diff`, `files` | `verdict`, `findings`, `gate_integrity_pass` | `read` |
| `kstack/qa` | **QA Lead** | `test_command`, `coverage_target` | `tests_passed`, `coverage_pct`, `failures`, `flaky_detected` | `read`, `execute_restricted` |
| `kstack/security` | **Security Lead** | `manifest_path`, `threat_scope` | `threats_identified`, `airgap_compliant`, `sca_risk_level` | `read` |
| `kstack/ship` | **Release Lead** | `target_ref`, `required_gates` | `qualified`, `passed_gates`, `flight_tape_sha256`, `receipt_id` | `read`, `execute_restricted` |
| `kstack/modernize` | **Engineer** | `dependency_name`, `target_version` | `breaking_changes`, `deprecated_apis`, `migration_steps` | `read`, `draft` |
| `kstack/repomap-sync` | **Indexer** | `workspace_path`, `deep_index` | `symbols_indexed`, `graph_nodes_count`, `repomap_sha256` | `read`, `draft` |

Every skill defines clear preconditions, operational invariants, and tamper-evident SHA-256 digests verified by `SystemDoctor`.

---

## 5. AgentBuilder & Production Starter Templates

AgentBuilder enables engineers to author, test, and distribute custom autonomous agents via declarative manifests (`AgentSpec v1`). Agents execute within the unified runtime engine constrained by `ManifestGuard` boundaries.

### 6 Built-In Production Templates

Keelway ships with six pre-configured, battle-tested agent templates (`core/agents/builder.py`):

1. **`test-fixer`:**
   * *Role:* Diagnoses test suite failures and drafts minimal, targeted code repairs.
   * *Permissions:* `confirm_mutation` autonomy, sandboxed test execution (`pytest -q`, `python3 -m unittest -q`), write access restricted to `src/**`, `core/**`, `lib/**`. Network: `none`.
   * *Safety Guard:* Strictly prohibited from modifying test assertion files to prevent synthetic passes.
2. **`code-reviewer`:**
   * *Role:* Audits Git diffs for security vulnerabilities, logic defects, and performance bottlenecks.
   * *Permissions:* Read-only inspection (`read_file`, `list_dir`, `search_codebase`). Writes: disabled. Commands: disabled. Network: `none`.
3. **`security-auditor`:**
   * *Role:* Scans codebases and commit history for exposed secrets, unsafe deserialization, path traversals, and unsafe subprocess calls.
   * *Permissions:* Read-only analysis. Writes: disabled. Commands: disabled. Network: `none`.
4. **`feature-scaffolder`:**
   * *Role:* Generates modular, type-annotated domain models, endpoints, and accompanying unit test suites.
   * *Permissions:* `confirm_mutation` autonomy, write access to `src/**`, `tests/**`, `core/**`. Network: `none`.
   * *Verification:* Validates all generated tests pass cleanly before returning.
5. **`doc-writer`:**
   * *Role:* Inspects AST diffs and code symbols to automatically synchronize READMEs, OpenAPI 3.1 schemas, and developer documentation.
   * *Permissions:* `confirm_mutation` autonomy, write access bounded to `docs/**`, `website/**`, `README.md`, `openapi.json`. Network: `none`.
6. **`dependency-modernizer`:**
   * *Role:* Evaluates outdated dependencies in `pyproject.toml` or `package.json`, runs upgrade test matrices in isolation, and refactors deprecated API call sites.
   * *Permissions:* `confirm_mutation` autonomy, command execution restricted to package managers and test runners. Network: `none`.

### Sealed Build Receipts
Compiling an agent via AgentBuilder produces an immutable `AgentBuildReceipt` recording the spec name, semver version, manifest SHA-256 digest, generated file paths, and test execution status.

---

## 6. KHub Universal Importer & Air-Gap Mirror

For enterprise organizations operating disconnected development networks or classified enclaves, Keelway v0.9.0-beta introduces **KHub Air-Gap Mirroring** (`core/khub/sync.py`, `cli.py`):

```bash
# Export all verified skills to an air-gapped archive
keelway hub mirror --out /media/secure-transfer/khub-mirror.tar.gz --archive

# Import and verify mirror bundle in an air-gapped enclave
keelway hub mirror --import-mirror /media/secure-transfer/khub-mirror.tar.gz --dest ~/.keelway/skills
```

### Security Guarantees:
* **Manifest Cryptographic Sealing:** Every mirror bundle includes a canonical `khub-mirror-manifest.json` with SHA-256 member digests.
* **Anti-Tamper & Zip-Slip Protection:** The importer inspects every tar member before extraction; path traversal vectors (`../`, absolute paths) immediately raise `PermissionError` and halt execution.
* **Integrity Validation:** Every imported skill is re-parsed and validated against its declared cryptographic digest prior to installation.
* **NIST SP 800-53 SC-7 Compliance:** Guarantees zero runtime dependency on external internet repositories.

---

## 7. 10-Axis System Doctor Diagnostics

Before initializing agent loops or running enterprise tasks, developers can validate system readiness using `keelway doctor` (or the Studio Pre-Flight Doctor panel).

The diagnostic engine evaluates 10 independent system dimensions:

```
[1/10]  Database Connectivity & WAL Engine ............. [OK] SQLite WAL mode active
[2/10]  Workspace Isolation & Git Context .............. [OK] Clean tree, branch resolved
[3/10]  Model Gateway & Local Provider ................. [OK] Local adapter reachable (installed model)
[4/10]  Air-Gap Zero-Egress Attestation ................ [OK] NIST SP 800-53 SC-7 compliant
[5/10]  Enterprise Entitlements & License .............. [OK] Signature verified
[6/10]  Software Bill of Materials (SBOM) .............. [OK] CycloneDX / SPDX generated
[7/10]  Tier-2 Hardware Security HAL ................... [WARN] Software-simulated (Demo mode)
[8/10]  KStack Skills Catalog (8 Skills) ............... [OK] Manifest SHA-256 verified
[9/10]  Agent Builder Templates (6 Templates) .......... [OK] Manifest schemas valid
[10/10] OS Sandbox Backend Confinement ................. [OK] Apple Seatbelt / Linux bwrap verified
```

If any critical boundary fails (e.g. sandbox verification failure or missing skill manifest), the doctor reports a `DEGRADED` status and outputs remediation commands.

---

## 8. Product Truth & Experimental Disclosures (Section P0-D)

In strict accordance with Sorvex Labs Product Truth guidelines, Keelway v0.9.0-beta provides explicit disclosures regarding experimental, simulated, and provisional components:

> [!IMPORTANT]
> **Developer Labs Multi-Rail Payment Payloads:**
> All payment rails in `core/storage/payment_broker.py` (M-Pesa, PIX, UPI, L402, and promotional vouchers) and associated Studio checkout dialogs are **mock demonstration payloads**. Keelway does not currently integrate active payment processors, credit card gateways, or banking webhooks. These interfaces exist purely to model localized edge billing workflows.

> [!WARNING]
> **Tier-2 Hardware Security Layer (HAL):**
> Hardware capabilities defined under `keelway/hal/`—including TPM 2.0 PCR attestation quotes, PIV smartcard cryptographic authentication, and Dual-WORM immutable logging—are **experimental, software-simulated prototypes**. They are not certified on physical HSM hardware for this beta release.

> [!NOTE]
> **Runtime Package Consolidation (ADR-0042):**
> Keelway currently maintains three packages: `core/` (~23.5k LOC, the primary live runtime), `keelway/` (~4.7k LOC, enterprise governance and quorum signing), and `keelway_core/` (reference workflow engine). Per ADR-0042, `core/` is designated as the **provisional runtime authority** for the Beta release. A planned 3-phase convergence will unify all modules into a single `keelway` namespace post-beta without breaking API compatibility.

> [!NOTE]
> **Desktop Mode Implementation:**
> Executing `keelway desktop` launches a dedicated Chromium instance in application window mode (`--app=<url>`). There is no bundled Electron or Tauri binary included in this distribution.

---

## 9. Quickstart Guide

### 9.1 Installation
Clone the repository and install the development environment using Python 3.11+:

```bash
git clone https://github.com/creova-gif/keelway.git
cd kora
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 9.2 Running System Diagnostics
```bash
keelway doctor
```

### 9.3 Launching the Studio
```bash
# Launch Web Studio on http://127.0.0.1:7420
keelway dev

# Launch in dedicated desktop app window
keelway desktop
```

### 9.4 Scaffolding an Autonomous Agent
```bash
# List available starter templates
keelway agent template list

# Scaffold an agent using the test-fixer template
keelway agent build --template test-fixer --name my-repo-fixer
```

---

## 10. Verification & Test Evidence

The Keelway engineering test suite verifies all critical paths:
* **Test Suite:** Comprehensive unit and integration test coverage across orchestration, state machines, sandbox confinement, and cryptographic receipts.
* **Linter & Type Checking:** Ruff linter clean.
* **Deterministic Verification:** State transitions strictly adhere to the 16-member `TaskState` finite state machine (`core/orchestration/state.py`).

For questions, issue reports, or enterprise air-gap evaluations, please consult `docs/DEVELOPER_QUICKSTART.md` or contact the Sorvex Labs engineering team.
