# ADR-006: Autonomous Self-Healing Verification Loop & Global Sovereign Mesh

## Status
Accepted

## Context
Kora AI is designed as a sovereign, air-gappable, globally inclusive developer runtime. As developers deploy autonomous coding agents across diverse operating environments—ranging from high-end Silicon Valley workstations to low-bandwidth African mobile hotspots, defense SCIFs (Sensitive Compartmented Information Facilities), and remote agricultural or industrial IoT nodes—two critical operational gaps emerge:

1. **The Autonomous Repair Gap (Self-Healing Loop):**
   Standard AI agents generate code or run commands, but when a compiler, linter, or test suite fails, they either hallucinate repetitively in context or leave broken repositories. An enterprise-grade developer tool requires a deterministic, closed-loop **Self-Healing Engine**:
   - Automated error capture (stack trace, exit code, failing assertion).
   - Abstract Syntax Tree (AST) fault localization (identifying the exact faulty function or class block).
   - Isolated patch exploration in ephemeral Git worktrees.
   - Multi-stage verification against regression test suites with automatic rollback if patches fail or introduce new failures.

2. **The Global Inclusive Settlement & Connectivity Gap (Beyond North America):**
   Over 70% of software creators and technology users globally live in regions where US-dollar credit cards and Stripe payments fail or are legally restricted due to foreign exchange (FX) limits, currency devaluations, or lack of international banking rails. Furthermore, unreliable cloud connections and intermittent power grids prevent 24/7 cloud API reliance:
   - **Payment Inclusivity:** Direct support for Mobile Money (M-Pesa, MTN MoMo, Orange Money), Instant Bank Transfer protocols (PIX in Brazil, UPI in India), and micro-streaming cryptographic rails (L402 Lightning Network and Ed25519 pre-funded bearer vouchers).
   - **Physical Transport Agnosticism:** Operations must run seamlessly over TCP/IP, LoRa radio mesh, BLE (Bluetooth Low Energy), USSD/SMS triggers, or offline Git bundles via physical flash media (sneakernet).

---

## Architecture & System Design

```
+--------------------------------------------------------------------------------------------------+
|                                    KORA AUTONOMOUS REPAIR ENGINE                                 |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   +-----------------------+     +------------------------+     +-----------------------------+   |
|   | 1. Failure Intercept  | --> | 2. AST Fault Slicer    | --> | 3. Candidate Patch Gen      |   |
|   | (Pytest, Vitest, etc) |     | (Tree-sitter / AST)    |     | (Local LLM / Air-Gapped)    |   |
|   +-----------------------+     +------------------------+     +-----------------------------+   |
|                                                                               |                  |
|                                                                               v                  |
|   +-----------------------+     +------------------------+     +-----------------------------+   |
|   | 6. Upstream Commit /  | <-- | 5. Zero-Regression     | <-- | 4. Isolated Worktree Trial  |   |
|   | Flight Recorder Tape  |     | Verification Gate      |     | (Sandboxed Ephemeral Git)   |   |
|   +-----------------------+     +------------------------+     +-----------------------------+   |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+

+--------------------------------------------------------------------------------------------------+
|                             GLOBAL SOVEREIGN MULTI-RAIL ADAPTER MATRIX                           |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|  [ Latin America ]            [ Africa / Emerging ]         [ Asia-Pacific / India ]             |
|  - PIX Instant QR / Key       - M-Pesa C2B / B2B Daraja     - UPI 2.0 AutoPay / Virtual ID       |
|  - LatAm PSE / Boleto         - MTN / Orange MoMo API       - Rupay Offline                      |
|                                                                                                  |
|  [ Global Decentralized / Crypto ]                         [ Offline Air-Gapped Vouchers ]       |
|  - L402 Lightning Protocol (Sats / HTTP 402)               - Ed25519 Signed Pre-funded Tokens    |
|  - USDC / USDT on Base / Solana                            - Merkle Tree Proof of Burn           |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## Detailed Specifications

### 1. Autonomous Self-Healing Verification Loop
- **Error Parser:** Implements standard diagnostic extraction for:
  - Python: `pytest`, `traceback`, `mypy`, `flake8`, `ruff`.
  - JavaScript / TypeScript: `vitest`, `jest`, `tsc`, `eslint`.
  - Rust: `cargo test`, `rustc`.
  - Go: `go test`.
- **AST Fault Localization:** Identifies the precise file, line range, and enclosing function or class symbol that raised the exception. Avoids passing unnecessary large context files into the LLM context window.
- **Verification Harness:**
  - Generates unified diff candidate patches (`--- a/... +++ b/...`).
  - Spawns an isolated `EphemeralWorktree` to safely apply the patch.
  - Re-executes the exact failing test suite.
  - Verifies that:
    1. The previously failing test now passes.
    2. No previously passing tests have regressed.
    3. No new security vulnerabilities or secrets have been introduced.
  - If verified, commits the patch and writes the patch receipt into the `FlightRecorder`. If failed, deletes the worktree and attempts alternative AST mutations up to a configurable maximum retry limit (default: 3 iterations).

### 2. Multi-Rail Sovereign Payment & Metering
- **Universal Payment Interface (`SovereignPaymentBroker`):**
  - Adapts spend mandates to regional payment rails:
    1. `mpesa`: Dispatches STK Push prompts via Daraja API for sub-Saharan mobile wallets.
    2. `pix`: Generates EMVCo dynamic QR codes and copy-paste codes for Brazilian instant clearing.
    3. `upi`: Dispatches UPI Intent URLs / QR strings for Indian clearing.
    4. `lightning_l402`: Exchanges HTTP 402 Payment Required headers with BOLT11 lightning invoices and HMAC macaroons.
    5. `offline_voucher`: Validates zero-connectivity cryptographic vouchers issued by corporate admins.

### 3. Mesh & Low-Bandwidth Signaling
- **Sneakernet Replication Protocol:** Supports importing and exporting signed Git bundles and agent memory checkpoints (`kora export --bundle`, `kora import --bundle`) over removable storage.
- **USSD / SMS Remote Admin:** Enables engineers in remote field stations to approve patches and inspect agent statuses with standard numeric keypad menus (`*920*42#`).

---

## Consequences
- **Positive:**
  - True autonomous repair: Kora agents can fix failing builds without human intervention.
  - Zero financial exclusion: Developers worldwide can pay for agent computation or run completely free edge models on their own laptops.
  - Air-gapped reliability: Defense, enterprise, and remote field deployments operate with high security and zero telemetry leakage.
- **Negative:**
  - AST parsing across multiple programming languages requires modular parsers.
  - Multi-rail payment verification requires sandbox mock providers for test suites.
