# Kora Dev Studio — Product Requirements Document (PRD) & UX Architecture

**Product:** Kora Dev Studio  
**Target:** Local Web & Desktop AI Engineering Environment  
**Theme:** Sovereign, Air-Gapped, High-Density Mission Control  
**Port:** `http://localhost:7420` (`kora dev`)  
**Design Standard:** Linear-grade minimalism + Bloomberg terminal information density + Apple HIG craftsmanship

---

## 1. Product Vision

Kora Dev Studio is an AI developer workspace designed for software engineers, research scientists, and regulated enterprise teams who refuse to trade data sovereignty for AI capability.

While Devin hides behind an asynchronous cloud wall, and Cursor is chained to standard VS Code chrome, **Kora Dev Studio** delivers:
1. **Local-First Air-Gap Mission Control:** Instant toggle between Hybrid Multi-Cloud and 100% Zero-Egress Air-Gapped mode.
2. **Deterministic State & Proof Visualization:** Live step-by-step visibility into the agent's internal state machine (`CREATED` -> `PLANNING` -> `VERIFYING` -> `COMPLETED`) with cryptographically verified evidence.
3. **Ghost Diff & Sandbox Streaming:** Interactive multi-file side-by-side diffing with instantaneous approval/rejection per hunk.
4. **Zero-Token Dollar Ledger & AP2 Mandates:** Live token consumption tracking displaying $0.00 edge savings and cryptographic spend boundaries.

---

## 2. Layout & Information Architecture

The UI is built as a single-page responsive application served directly from the local FastAPI runtime without cloud dependencies:

```text
+----------------------------------------------------------------------------------------------------+
|  ⚡ KORA DEV STUDIO   |  Repo: creova-gif/kora  |  Provider: Qwen 3.5 (Local)  |  [🔒 AIR-GAPPED: ACTIVE] |
+-----------------------+-----------------------------------------------+----------------------------+
|  LEFT SIDEBAR         |  CENTER WORKSPACE (Tabs: Diff, Terminal, Code)|  RIGHT AGENT COPILOT PANEL  |
|                       |                                               |                            |
|  [>] Project Tree     |  +-----------------------------------------+  |  State: EXECUTING (Tier 2) |
|  [>] Tasks & Traces   |  | Tab: Multi-File Diff View                |  |  Tokens: 1,420 (Cost: $0)  |
|  [>] Scoped Memory    |  | --- a/core/gateway.py                   |  |  Voice: Human Engineer     |
|  [>] Security DLP     |  | +++ b/core/gateway.py                   |  |                            |
|  [>] AP2 Mandates     |  | @@ -80,6 +80,12 @@                      |  |  [Live Evidence Cited]     |
|                       |  | +   # Air-Gap Enforcement               |  |  - ADR-002 #L24-L35        |
|                       |  +-----------------------------------------+  |  - PR #42 Specs            |
|                       |  | Tab: Ephemeral Sandbox Terminal         |  |                            |
|                       |  | $ pytest tests/test_airgap.py           |  |  [Prompt & Instructions]   |
|                       |  | 36 passed in 0.37s [OK]                 |  |  "Add WebSocket stream"    |
|                       |  +-----------------------------------------+  |                            |
|                       |                                               |  [ Approve ] [ Reject ]    |
+-----------------------+-----------------------------------------------+----------------------------+
|  FOOTER STATUS BAR: DB: CONNECTED (SQLite) | Sockets: Active (1) | Egress: 0 Bytes | Version: 2.1.0-alpha  |
+----------------------------------------------------------------------------------------------------+
```

---

## 3. Design Tokens & Visual Hierarchy

* **Color Palette:**
  * Background Base: `#090D16` (Deep Midnight Obsidian)
  * Surface Card: `#111827` (Charcoal Slate with subtle `rgba(255, 255, 255, 0.05)` borders)
  * Primary Accent: `#3B82F6` (Electric Cobalt)
  * Air-Gap Sovereign Green: `#10B981` (Emerald Shield)
  * Critical Warning / Gate: `#F59E0B` (Amber Gate)
  * Destructive / Alert: `#EF4444` (Crimson Block)
* **Typography:**
  * UI Text: Inter / SF Pro (`-apple-system`, sans-serif)
  * Code & Terminal: JetBrains Mono / Fira Code (`monospace`) with syntax highlighting
* **Animations:**
  * Zero jarring layout shifts. Smooth 150ms ease-out transitions for cards and state badge pulses.

---

## 4. Real-Time Streaming Architecture

* **WebSockets Endpoint:** `ws://localhost:7420/v1/ws/studio`
  * Emits event packets:
    * `agent_state_changed`: `{ task_id, previous_state, new_state, timestamp }`
    * `thought_token`: `{ task_id, token_chunk }`
    * `diff_generated`: `{ file_path, additions, deletions, patch_text }`
    * `terminal_output`: `{ stdout, stderr, exit_code }`
    * `dlp_alert`: `{ finding, redacted_placeholder }`
