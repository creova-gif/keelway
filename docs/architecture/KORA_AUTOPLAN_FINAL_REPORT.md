# Kora AI — `/autoplan` Executive Review & Approval Gate

**Pipeline:** `CEO Review` ➔ `Design Review` ➔ `DX Review` ➔ `Eng Review` (Mandatory Sequence)  
**Host Platform:** GitHub (`https://github.com/creova-gif/kora.git`) | **Base Branch:** `main`  
**Decision Principles:** P1 (Completeness) • P2 (Boil Lakes) • P3 (Pragmatic) • P4 (DRY) • P5 (Explicit) • P6 (Action)  
**Review Status:** **ALL 4 PHASES COMPLETE — FINAL APPROVAL GATE READY**  

---

## Phase 1: CEO Review (Strategy & The 10-Star Product)
- **Posture:** Scope Expansion (Finding the 10-star product).
- **Auto-Decisions Applied:**
  - *Positioning:* Not an IDE plugin or VS Code fork. Kora is an **autonomous sovereign agent runtime** with an open MCP bridge to VS Code, Cursor, Neovim, and JetBrains.
  - *Global Footprint:* Complete rejection of North American/US-only payment assumptions. Built native multi-rail broker supporting M-Pesa (East Africa), PIX (Brazil), UPI (India), L402 Lightning (Global satoshi micro-streaming), and offline cryptographic prepaid vouchers.
  - *Defensible Moat:* Zero cloud token spend ($0.00 edge default) + cryptographic zero-egress attestation (defense/banking/healthcare compliant).

---

## Phase 2: Design Review (Teenage Engineering x Linear Aesthetic)
- **Posture:** Opinionated UI elevation across 10 design dimensions.
- **Score:** Elevated from **7.1 / 10** to **10 / 10**.
- **Auto-Decisions Applied:**
  - *Typography:* Tabular figures (`tnum`) enforced across all telemetry counters to prevent number jitter.
  - *Tactile Audio:* Built-in zero-dependency Web Audio API synthetic oscillators for mechanical latch sounds (air-gap switch), dual chimes (self-healing pass), and warm tones (human approval gate).
  - *Interaction Physics:* Micro-scale button depressions (`transform: scale(0.98)`) and sliding spring transitions on ghost diff views.
  - *Information Architecture:* Maintained trunk test navigation while adding an interactive time-travel execution tape scrubber.

---

## Phase 3: Developer Experience (DX) Review
- **Posture:** Radical friction removal and offline resilience.
- **Auto-Decisions Applied:**
  - *Time-To-Hello-World (TTHW):* Target <30 seconds with single-line boot: `curl -fsSL https://get.kora.ai | sh`.
  - *Zero-Config Model Selection:* Automatically detects Apple Silicon GPU / NVIDIA CUDA / CPU and loads optimal 4-bit GGUF quantization tier without manual prompt tuning.
  - *Self-Healing Proactivity:* Terminal failures automatically suggest 1-key AST auto-repair (`kora heal`).
  - *Offline Immunity:* Zero blocking spinners or network timeout warnings when internet drops.

---

## Phase 4: Engineering Review (Systems, Safety & Security)
- **Posture:** Maximum rigor and zero silent failures.
- **Auto-Decisions Applied:**
  - *Formal State Machine:* Immutable transition table (`CREATED ➔ PLANNED ➔ AWAITING_APPROVAL ➔ RUNNING ➔ VERIFYING ➔ COMPLETED`) with zero illegal leaps.
  - *Ephemeral Worktree Isolation:* Parallel agent tasks run in disposable Git worktrees (`.kora/worktrees/agent_<id>`), preventing repo locking or uncommitted work collisions.
  - *Air-Gap Boundary:* Enforced at socket and adapter level with SHA-256 zero-egress audit logging.
  - *Closed-Loop AST Repair:* Error frame parser, Python AST code block locator, and regression verification gate.

---

## Final Approval Gate: Taste Decisions

The 6 principles resolved all mechanical decisions. The following **3 Taste Decisions** are surfaced for your final approval:

### Taste Decision 1: Edge Model Runtime Architecture
- **Option A (Direct GGUF Embedding)**: Kora downloads 4-bit GGUF models directly to `~/.kora/models/` using an embedded llama.cpp runtime (zero external dependencies).
- **Option B (Ollama Daemon Dependency)**: Require users to install and run Ollama on `localhost:11434`.
- **Recommendation (Option A + B Hybrid)**: Auto-detect Ollama if running; if absent, transparently load embedded 4-bit GGUF weights so the user never installs a daemon.

### Taste Decision 2: Remote Field Engineering Channel
- **Option A (Telegram Mini App)**: Rich interactive diff previews, inline approve/reject buttons, and zero SMS cost.
- **Option B (USSD / SMS Direct)**: Works on 2G feature phones without smartphones or data plans (`*920*42#`).
- **Recommendation**: Telegram Mini App as primary, with USSD/SMS fallback for remote agricultural/industrial field deployments.

### Taste Decision 3: Local Team Mesh Transport
- **Option A (mDNS / Zeroconf Local Wi-Fi)**: Zero-config discovery across laptops on the same office Wi-Fi router.
- **Option B (Tailscale / WireGuard P2P Overlay)**: Peer-to-peer compute sharing across remote home offices and cloud nodes.
- **Recommendation**: mDNS by default on local LANs, with one-click Tailscale integration for distributed remote teams.
