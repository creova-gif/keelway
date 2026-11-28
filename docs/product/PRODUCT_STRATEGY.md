# Keelway — Product Strategy & Strategic Platform Direction

> **Brand**: Keelway  
> **Repository**: `https://github.com/creova-gif/keelway.git`  
> **Deployment**: `https://kora-sable.vercel.app/`  
> **Figma Design System**: `https://www.figma.com/design/Q5w3YHx59r2e1bdsVRpGzy/keelway`

---

## 1. Product Vision: The Sovereign AI Platform

Keelway is built on the realization that enterprises face an unacceptable trade-off between the high reasoning power of closed cloud models and the data sovereignty, privacy, and economic efficiency of open-weight models.

**The Keelway Solution**: A unified, sovereign AI platform where:
1. **Open-Weight and Frontier Closed Models are Co-Equal Citizens**: Developers interact with one consistent API (`/v1/chat/completions`, `/v1/models`) regardless of where the model is executing.
2. **Economic Arbitrage**: Routine code generation, linting, agent loops, and retrieval run locally or in private VPCs on open-weight models (Qwen 2.5, DeepSeek R1, Llama 3.3) at **$0.00 external API cost**, saving up to 85–95% on compute bills.
3. **Guaranteed Sovereign Privacy**: Strict air-gap fail-closed guarantees ensure proprietary codebases, healthcare data, and financial records never leak to third-party model providers.
4. **Verifiable Governance**: Cryptographically sealed flight tapes, Merkle audit trails, and human-in-the-loop approval relays provide enterprise auditability.

---

## 2. Core Target Personas & Use Cases

1. **Enterprise AI Engineering Teams**:
   - Run autonomous multi-agent software engineering workflows in isolated sandboxes.
   - Enforce organizational security rules (e.g. no cloud egress for repo code).
2. **Security & Compliance Officers (CISO/SecOps)**:
   - Complete visibility into agent actions via non-repudiable audit logs.
   - Automated PII and credential redaction before any log persistence.
3. **FinOps & Platform Leaders**:
   - Real-time token economics ledger (`/v1/usage`) showing cloud expenditure vs. quantified local savings.
   - Elimination of surprise cloud AI bills.

---

## 3. Brand Identity & Design System Alignment

All Keelway interfaces (Web Studio, Website, Mobile App) must align strictly with the canonical Figma specification:
- **Design Tokens**:
  - Background: Obsidian Void (`#0a0b0d`)
  - Elevated Surface: Graphite (`#14171c`)
  - Border: Subtle Steel (`#222731`)
  - Primary Accent: Keelway Teal (`#14b8a6`)
  - Status Indicators: Emerald (`#10b981`), Amber (`#f59e0b`), Rose (`#f43f5e`)
- **Typography Stack**:
  - Display & Headings: **Archivo**
  - Body & UI: **Instrument Sans**
  - Code & Monospace: **Martian Mono**
- **Truth in Marketing**:
  - Never advertise unsupported capabilities. All marketing claims on `web-next/` must map directly to passing test evidence in `docs/product-facts.yaml`.
