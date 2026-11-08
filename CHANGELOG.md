# Changelog — Keelway

All notable changes to the Keelway sovereign developer environment and agent runtime are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.9.0-beta] - 2026-11-15

### Added
- **Sovereign Local-First Agent Loop:** Unified ReAct autonomous loop (`core/orchestration/agent_loop.py`) powered by local open-weight inference backends (Ollama `qwen3.5:latest`, vLLM, llama.cpp, and LM Studio).
- **Zero-Egress Invariant (`network: none`):** Strict fail-closed network isolation enforcing `LOCAL_ONLY` execution. Transition to `BLOCKED` state on local model failure, prohibiting silent commercial cloud fallback.
- **Fail-Closed OS Sandbox Isolation:** Process confinement via Apple Seatbelt (`sandbox-exec`) on macOS and Bubblewrap (`bwrap`) on Linux (`core/agents/sandbox.py`) with unshared network namespaces (`--unshare-net`) and forbidden access to sensitive user files (`~/.ssh`, `~/.aws`, `.git/hooks`).
- **Unified 6-Stage Proof Strip UX:** Studio interface rendering the deterministic pipeline (`INSPECT` $\rightarrow$ `PLAN` $\rightarrow$ `AUTHORIZE` $\rightarrow$ `EXECUTE` $\rightarrow$ `VERIFY` $\rightarrow$ `SEAL`) across both IDE Mode and Agent Builder Mode.
- **AST Semantic Diff & Flight Tape Replay:** AST symbol indexing and cross-file reference tracking (`core/storage/ast_index.py`) combined with deterministic `.flight.jsonl` flight recordings for time-travel execution replay.
- **KStack Composable Role Skills (8 Built-In):** Versioned, cryptographic manifest (`core/kstack/manifest.json`, format `kstack_skills_manifest_v1`) containing 8 specialist skills:
  - `kstack/plan` (Architect role)
  - `kstack/investigate` (Debugger role)
  - `kstack/review` (Reviewer role)
  - `kstack/qa` (QA Lead role)
  - `kstack/security` (Security Lead role)
  - `kstack/ship` (Release Lead role)
  - `kstack/modernize` (Engineer role)
  - `kstack/repomap-sync` (Indexer role)
- **AgentBuilder & Starter Templates (6 Templates):** Declarative `AgentSpec v1` compilation with `ManifestGuard` containment boundaries and 6 production starter templates:
  - `test-fixer` (Confirm-mutation test diagnosis without assertion tampering)
  - `code-reviewer` (Autonomous read-only AST diff security and bug audit)
  - `security-auditor` (Autonomous secret leakage, deserialization, and path traversal scanner)
  - `feature-scaffolder` (Confirm-mutation domain modeling and endpoint scaffolding)
  - `doc-writer` (Confirm-mutation AST diff doc and OpenAPI synchronization)
  - `dependency-modernizer` (Confirm-mutation semver upgrade and breaking API call refactoring)
- **KHub Air-Gap Mirroring CLI:** Enterprise commands (`keelway hub mirror`) for offline export and import with anti-tamper SHA-256 verification and zip-slip path traversal prevention.
- **10-Axis System Doctor Diagnostics:** Pre-flight diagnostic engine (`keelway doctor` and Studio diagnostic panel) validating Database, Workspace, Model Gateway, Air-Gap, Entitlements, SBOM, HAL, KStack, Templates, and Sandboxing.
- **Enterprise Governance Suite:** Two-human quorum signing (`TwoHumanQuorumService`), persistent SQLite WAL audit store (`keelway_audit.db`), and Merkle tree inclusion proofs.

### Changed
- **Deterministic 16-Member State Machine:** Formalized `TaskState` (`core/orchestration/state.py`) with strict `VALID_TRANSITIONS` table; superseded legacy 8-state and 11-state prototypes per decision precedence.
- **Dual-Mode Parity:** Replaced split runtime prototypes with single unified runtime engine shared across IDE Mode and Agent Builder Mode.
- **Design System Typography:** Standardized Studio typography on self-hosted `Inter` and `JetBrains Mono` without external CDN requests.

### Deprecated / Architectural Disclosures (Product Truth P0-D)
- **Runtime Package Consolidation (ADR-0042):** Designated `core/` as provisional runtime authority for Beta. Formalized 3-phase post-beta unification roadmap into single `keelway` package namespace.
- **Software-Simulated Tier-2 HAL:** Disclosed TPM 2.0 PCR quotes, PIV smartcard authentication, and Dual-WORM hardware receipts (`keelway/hal/`) as experimental software simulations pending physical hardware qualification.
- **Simulated Payment Payloads:** Disclosed multi-rail payment payloads (M-Pesa, PIX, UPI, L402, vouchers in `core/storage/payment_broker.py`) as mock demonstration payloads without active processor integration.
