# Keelway Architecture & Decision Precedence Register
**Document Version:** 1.0.0  
**Effective Date:** 2026-11-05  
**Authority:** Product Foundation, Dual-Mode PRD, and Master Execution Guidelines  

When historical documents, pitch decks, architectural diagrams, or legacy code conflict, the following precedence rules strictly govern all design, implementation, and public statements:

---

## 1. Product Name and Corporate Identity
* **Precedence Rule:** The official, canonical name of the product is **Keelway by Sorvex Labs**.
* **Precedence Order:** Current PRD & Brand Guidelines > Historical ADRs > Legacy Commit History.
* **Resolution:** All user-facing surfaces (CLI, Studio, documentation, web landing pages, API headers, error messages) MUST display **Keelway**. Internal database table prefixes (`kora_tasks`, `kora_audit_events`) and backward-compatible module aliases are preserved strictly for database migration continuity, not as branding.

---

## 2. Deterministic State Machine (16-member `TaskState` vs Legacy 8 States)
* **Precedence Rule:** The runtime state machine is `TaskState` and `VALID_TRANSITIONS` in `core/orchestration/state.py`. That file is the source of truth; this list mirrors it.
* **State Inventory (16):** `CREATED`, `CONTEXT_LOADING`, `PLANNING`, `PLANNED`, `PLAN_READY`, `AWAITING_APPROVAL`, `RUNNING`, `EXECUTING`, `VERIFYING`, `PAUSED`, `BLOCKED`, `AWAITING_RETRY`, `TIMED_OUT`, `COMPLETED`, `FAILED`, `CANCELLED`. `COMPLETED` and `CANCELLED` are terminal.
* **Resolution:** Any historical document or pitch deck referencing an 8-state model is superseded. State transitions MUST be validated at the runtime boundary; transitions not in `VALID_TRANSITIONS` (such as `PLANNING` directly to `EXECUTING`) raise `InvalidStateTransitionError`. The graph does allow `PLANNED` → `EXECUTING`; approval of individual risky tool calls is enforced by the agent loop's policy and approval gate, not by this graph.

---

## 3. Sovereign Cloud Policy & Zero-Egress Invariant
* **Precedence Rule:** Default mode is strictly `LOCAL_ONLY`. **Silent fallback to cloud LLMs is categorically prohibited.**
* **Precedence Order:** Nov 5 Sovereign Policy Directive > Historical Multi-Provider Cloud Auto-Failover ADRs.
* **Resolution:** If a local model (`qwen3.5:latest` via Ollama or embedded GGUF) is unavailable, the system MUST transition to `BLOCKED` with an explicit diagnostic error. Hybrid cloud routing is only permitted when the developer explicitly supplies credentials, chooses a cloud provider, sets a hard token/cost ceiling, and signs an authorization prompt.

---

## 4. Shared Runtime Invariant (Dual-Mode Parity)
* **Precedence Rule:** **IDE Mode** and **Agent Builder Mode** MUST share the identical core runtime.
* **Architecture:**
  - Both modes execute through `AutonomousAgentLoop` (`core/orchestration/agent_loop.py`).
  - Agent Builder wraps the loop via `core/agents/guard.py` (`loop_from_manifest`) using `ManifestGuard` boundaries.
  - Policy enforcement (`SecurityGateway`), approval token verification, flight tape recording (`FlightTapeRecorder`), and model gateway dispatch are 100% unified.
* **Resolution:** No secondary "Builder Runtime" or separate execution daemon shall ever be created.

---

## 5. Licensing and Intellectual Property
* **Precedence Rule:** The repository is licensed under the **Apache License, Version 2.0** (`LICENSE`).
* **Attribution:** All distributions must preserve the `NOTICE` file attributing Sorvex Labs and contributors.
* **Resolution:** No unvetted third-party copyleft code shall be integrated into core packages. Portable agent bundles (`.agent.json`) are sovereign artifacts owned by the creating developer.

---

## 6. Hardware Security Module & WORM Claims Qualification
* **Precedence Rule:** All Tier-2 HAL capabilities (TPM 2.0 PCR quotes, PIV smartcard authentication, Dual-WORM hardware receipts) are classified as **EXPERIMENTAL / SOFTWARE-SIMULATED** until physically qualified on target enterprise hardware.
* **Resolution:** Public website documentation, sales collateral, and CLI prompts must not market these features as certified or production-qualified hardware attestations.

---

## 7. Dual-Mode Visual Design System & The Proof Strip
* **Precedence Rule:** Keelway Studio and Agent Builder Mode must adhere to the single design token system (`Inter` + `JetBrains Mono`, self-hosted, no font CDN) and render the standard **Proof Strip**:
  $$\text{INSPECT} \longrightarrow \text{PLAN} \longrightarrow \text{AUTHORIZE} \longrightarrow \text{EXECUTE} \longrightarrow \text{VERIFY} \longrightarrow \text{SEAL}$$
* **Resolution:** No decorative AI hype elements, pulsing badges, or unverified claims. Every UI event must reflect verifiable state transitions and flight-tape evidence.
