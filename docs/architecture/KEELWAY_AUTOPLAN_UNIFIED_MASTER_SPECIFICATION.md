# Keelway — Unified Autoplan Master Specification

**Review Pipeline:** CEO Review (Step 2) ➔ Design Review (Step 3) ➔ Developer Experience & Eng Review (Step 1)  
**Status:** **LOCKED FOR IMPLEMENTATION**  
**Repository:** [`creova-gif/keelway`](https://github.com/creova-gif/keelway)  
**Primary Target:** Global Developer Ecosystem (Americas, EMEA, APAC, Sovereign Grids)  

---

## 1. Executive Synthesis & Architectural Convergence

Through the completed multi-stage review cascade, Keelway's identity and product scope are crystallized:

```
+---------------------------------------------------------------------------------------------------------+
|                                    KEELWAY AUTONOMOUS SOVEREIGN SYSTEM                                     |
+---------------------------------------------------------------------------------------------------------+
|                                                                                                         |
|   +-----------------------+     +-------------------------+     +----------------------------------+    |
|   | 1. High-Density Studio| <-> | 2. Headless Agent Core  | <-> | 3. Open MCP Protocol Gateway     |    |
|   | (Web & Desktop PWA)   |     | (Local CLI / Daemon)    |     | (VS Code / Cursor / JetBrains)   |    |
|   +-----------------------+     +-------------------------+     +----------------------------------+    |
|               |                              |                                    |                     |
|               +------------------------------+------------------------------------+                     |
|                                              |                                                          |
|               v                              v                                    v                     |
|   +-----------------------+     +-------------------------+     +----------------------------------+    |
|   | 4. Self-Healing Loop  |     | 5. Multi-Rail Broker    |     | 6. Air-Gap & Flight Recorder     |    |
|   | (AST Slicer/Worktrees)|     | (M-Pesa/PIX/UPI/L402)   |     | (Zero-Egress Attestation/Replay) |    |
|   +-----------------------+     +-------------------------+     +----------------------------------+    |
|                                                                                                         |
+---------------------------------------------------------------------------------------------------------+
```

---

## 2. Developer Experience (DX) Mode Review

| DX Dimension | Current State | The 10-Star Target | Specification & Implementation Lock |
| :--- | :--- | :--- | :--- |
| **Time-To-Hello-World (TTHW)** | ~3 minutes (clone repo, create virtualenv, pip install) | **< 30 seconds** | Single-line install: `curl -fsSL https://get.keelway.dev \| sh`. Auto-detects local Ollama or downloads a 4-bit quant of Qwen 2.5 Coder. Developer writes `keelway dev` and the studio boots immediately. |
| **Cognitive Friction** | Multiple complex CLI flags (`--air-gapped`, `--style`, etc.) | **Predictive Defaults** | `keelway` defaults to local edge inference ($0.00) and strict air-gapped security automatically. Cloud keys are only consulted if explicitly supplied in `.env`. |
| **Error Recovery** | Stack traces printed to terminal on build/test breaks | **Self-Healing Assist** | Any terminal failure automatically prints: `[⚡] Failure detected in core/api/routes.py:42. Press 'H' or run 'keelway heal' to auto-repair in an isolated worktree.` |
| **Offline Resilience** | Full offline support | **Zero Internet Dependency** | Keelway never polls external telemetry servers; no "Connecting to cloud..." blocking spinner. When internet is disconnected, Keelway runs with 0% latency penalty. |

---

## 3. Principal Engineering & Systems Review

### A. Formal State Machine Verification
Tasks follow an immutable state transition graph enforced by `core/orchestration/state.py`:
- `CREATED ➔ PLANNED ➔ AWAITING_APPROVAL ➔ RUNNING ➔ VERIFYING ➔ COMPLETED`
- `RUNNING / VERIFYING ➔ FAILED ➔ PLANNED` (bounded retry loop with exponential backoff).
- Zero illegal transitions permitted (e.g., cannot jump from `CREATED` directly to `COMPLETED`).

### B. Ephemeral Concurrency & Worktree Isolation
- Multi-agent parallel tasks run in dedicated Git worktrees (`.keelway/worktrees/agent_<id>`).
- Guarantees zero Git index locking conflicts, branch contamination, or uncommitted work loss in the user's primary working tree.
- Automatic cleanup on task completion or failure.

### C. Air-Gapped Zero-Egress Attestation
- Enforced at the socket and adapter level via `core/security/airgap.py`.
- Any attempt by an LLM adapter or tool to connect to external IPs when air-gapped raises `SecurityPolicyViolationError` and emits a SHA-256 signed audit entry.

---

## 4. Master Implementation Checklist & Launch Sequence

- [x] **ADR-001 through ADR-006**: Complete architectural foundation locked.
- [x] **Multi-Model Inference Gateway**: Anthropic, OpenAI, Gemini, and Ollama edge failovers.
- [x] **Air-Gapped Security & DLP**: Zero-egress boundary, secret redaction, prompt injection guards.
- [x] **Deterministic Flight Recorder**: Execution tape recording and branching time-travel player.
- [x] **Closed-Loop AST Self-Healing**: Pytest/Vitest parser, AST code block slicer, isolated worktree trials.
- [x] **Global Multi-Rail Payment Broker**: M-Pesa (East Africa), PIX (Brazil), UPI (India), L402 Lightning, and Offline Prepaid Vouchers.
- [x] **Keelway Studio UI**: Obsidian dark-mode mission control with real-time WebSockets.
- [x] **100% Zero-Dependency Unit Test Suite**: Verified passing cleanly in sandbox environment.
- [ ] **Phase 2 Expansion**: Speculative decoding (0.5B draft + 7B target) & in-browser WebGPU interactive playground for `keelway.dev`.
