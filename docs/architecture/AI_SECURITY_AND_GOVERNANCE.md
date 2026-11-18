# Keelway AI Security, Governance & Sovereign Containment

## 1. Security Core Invariants

Keelway implements enterprise-grade security and data containment across all inference paths:

1. **Air-Gap Zero-Egress Invariant:** When `air_gap.enabled == True` or `privacy_level == "private"`, the Model Gateway acts as a fail-closed firewall. Outbound HTTP/gRPC requests to external cloud endpoints are terminated before network socket creation.
2. **Deterministic Prompt Sanitization:** Incoming messages are inspected by `core/security/gateway.py` before model dispatch. Known jailbreak vectors, system role override tokens, and adversarial injection strings are intercepted and rejected.
3. **Automated Secret Redaction:** API keys, AWS tokens, private keys, and high-entropy secret patterns are redacted from prompts and output completions prior to flight recording.
4. **Append-Only Immutable Cost Accounting:** Every inference completion is written to an append-only JSONL cost ledger (`core/models/cost_ledger.py`) with cryptographic hash digests, enabling auditable billing and cloud cost arbitrage tracking.

---

## 2. Threat Model & Mitigations (STRIDE Matrix)

| Threat Category | Specific Attack Vector | Keelway Mitigation Mechanism |
|---|---|---|
| **Spoofing** | Unauthorized API key reuse or identity theft | Principal validation via `current_principal` dependency; HMAC-SHA256 request authentication |
| **Tampering** | Model weight corruption or malicious GGUF injection | Pre-flight SHA-256 weight digest verification; strict GGUF header inspection |
| **Repudiation** | Denying an unapproved agent code mutation | Monotonic Lamport-stamped audit ledger and deterministic flight recorder tapes |
| **Information Disclosure** | Accidental cloud transmission of internal source code | Hard fail-closed privacy boundary invariant; zero cloud egress for `private` requests |
| **Denial of Service** | Infinite generation loops or GPU VRAM starvation | Strict `max_tokens` limits (default 4,096; max 128,000) and request timeout watchdogs |
| **Elevation of Privilege** | Prompt injection extracting system prompt or master key | Pre-dispatch security guardrail inspection and automated secret token suppression |

---

## 3. Cryptographic Transmission and State Sync

For cross-machine team collaboration and multi-node synchronization, Keelway employs:
- **Cipher:** AES-256-CTR with PKCS7 padding.
- **Integrity Tag:** HMAC-SHA256 Encrypt-then-MAC authentication tag.
- **Monotonic Clocks:** Lamport logical timestamps ensuring strict total order across distributed peer journals without NTP clock drift vulnerabilities.
