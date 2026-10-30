# ADR-002: Air-Gapped Sovereign Execution, Stylistic De-Slopping, and Offline-First Economics

**Status:** Approved  
**Date:** 2026-10-30  
**Deciders:** Kora Core Engineering & Research Team  
**Consulted:** Y Combinator Winter RFS ("AI for the Air-Gapped Economy", "LLMs That Write Well")

---

## 1. Context & Problem Statement

Current frontier AI frameworks are architecturally centralized, fragile, and geographically discriminatory:
1. **The Air-Gapped & Sovereignty Void:** Critical industries (defense, banks, hospitals, energy grids) and sovereign nations cannot send classified or regulated data across borders to US cloud APIs. When external networks are severed, conventional agents collapse.
2. **The "RLHF Slop" Collapse:** Aggressive reinforcement learning for coding and math benchmarks has flattened LLM writing into robotic, sycophantic corporate fluff ("delve", "testament", formulaic bullet points) stripped of authentic human voice, brevity, and cultural nuance.
3. **The Global Payment & FX Trap:** Emerging-market builders and businesses (across Africa, Latin America, Southeast Asia) face strict foreign exchange limits, USD credit card bans, high cloud latencies, and unaffordable recurring token bills.

---

## 2. Decision & Architectural Pillars

Kora AI establishes three sovereign runtime capabilities:

### Pillar I: Strict Air-Gapped Zero-Egress Mode (`--air-gapped`)
* **Socket & Transport Lockout:** When enabled, the runtime enforces loopback binding (`127.0.0.1`), shuts down external DNS, and drops all outbound network calls at the adapter and firewall layer.
* **100% Offline Tooling:** Evaluates tasks exclusively using on-device models (`qwen3.5:latest`, local quantized checkpoints) and local SQLite/JSON storage.
* **Cryptographic Air-Gap Attestation:** Every completed offline task generates an air-gap verification hash proving no network egress occurred during execution.

### Pillar II: Stylistic Voice & "De-Slopping" Engine
* **Negative Constraint & Anti-Slop Filter:** Post-processors and system prompts strip AI cliches (*"delve", "in conclusion", "beacon", "testament", "crucial to remember"*), marketing filler, and robotic hedging.
* **Persona & Voice Calibration:** Supports distinct stylistic profiles:
  - `executive`: Terse, high-information density, zero fluff, direct recommendations.
  - `human-engineer`: Pragmatic, self-critical, direct technical tone with realistic trade-offs.
  - `localized`: Grounded in regional context without sterile corporate Americanisms.
* **Escape Hatch Protocol:** Explicitly permits the model to output *"Insufficient evidence to determine X"* rather than hallucinating or stalling.

### Pillar III: Sovereign Token Budget & Local Economic Ledger
* **Offline-First Cost Accounting:** Local SQLite ledger tracks exact inference tokens and compute time per user/task without relying on Stripe or external webhooks.
* **Prepaid Regional Vouchers:** Enables token quota allocation via cryptographic offline voucher keys—unlocking AI agent usage for regions without USD credit cards.

---

## 3. Consequences

### Positive
- Enables deployment inside classified environments (DoD IL4/IL5, banking, healthcare HIPAA/SOC2).
- Zero dollar inference cost ($0.00) makes AI accessible to developers in emerging markets without foreign exchange barriers.
- Generates high-signal, compelling, authentic technical and narrative prose that humans respect reading.

### Trade-Offs & Mitigations
- Local edge models require sufficient local RAM (Apple Silicon unified memory or 16GB+ RAM). *Mitigation:* Support 4-bit and 8-bit quantized models and fast fallback routing.
- Air-gapped environments cannot query live external web endpoints. *Mitigation:* Hybrid RAG memory indexes local files, ADRs, and internal repos directly.
