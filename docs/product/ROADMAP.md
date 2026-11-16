# Keelway — Strategic Product & Platform Roadmap

> **Lifecycle**: Active Multi-Phase Release Plan  
> **Horizon**: Q4 2026 – Q2 2027

---

## 1. Roadmap Milestones

```
[ Phase 1: Foundational Hybrid AI Fabric ] (Current - Production Ready)
  ├── Unified Model Registry (Open-weight & proprietary)
  ├── Universal Chat Completions API (/v1/chat/completions, SSE streaming)
  ├── Open-Weight Adapters (Ollama, vLLM, TGI) & Cloud Adapters (OpenAI, Claude, Gemini)
  ├── Deterministic Routing & Privacy Fail-Closed Invariant
  └── Sovereign Cost Ledger & Real-Time Economic Arbitrage (/v1/usage)

[ Phase 2: Autonomous Agent Studio & Enterprise Governance ] (Beta)
  ├── Agent Manifest Engine v1 (Capability boundaries, tool permissions)
  ├── Command Sandbox (macOS Seatbelt, Linux Bubblewrap)
  ├── Merkle Flight Recorder & Automated Credential Redaction
  ├── Web Developer Studio & Real-time Event Streaming (/v1/studio)
  └── Mobile Approval App (Biometric authorization, Telegram/WhatsApp relays)

[ Phase 3: Distributed Mesh & Original AI Research ] (Active Research & Expansion)
  ├── KFlow Durable Task DAG Orchestration Engine
  ├── KHub Air-Gapped Package & Model Mirror
  ├── KSpaces Transactional Multi-Agent Workspace Coordination
  ├── Sovereign LoRA Adaptation Pipeline (Domain-specific code fine-tuning)
  └── Speculative Decoding & Edge Inference Optimization
```

---

## 2. Phase 1 Detailed Deliverables & Status

| Capability | Module / Route | Status | Test Proof |
|---|---|---|---|
| **Model Registry** | `core/models/registry.py` | Complete | `tests/test_hybrid_model_registry.py` (4/4 passed) |
| **Open-Weight Adapter** | `core/models/adapters/open_weight.py` | Complete | `tests/test_hybrid_adapters.py` |
| **OpenAI Adapter** | `core/models/adapters/openai_provider.py` | Complete | `tests/test_hybrid_adapters.py` |
| **Model Gateway** | `core/models/gateway.py` | Complete | `tests/test_hybrid_routing_and_api.py` |
| **OpenAI-Compatible API** | `POST /v1/chat/completions` | Complete | `tests/test_hybrid_routing_and_api.py` |
| **Model Catalog Route** | `GET /v1/models` | Complete | `tests/test_hybrid_routing_and_api.py` |
| **Usage & Cost Ledger** | `GET /v1/usage` | Complete | `tests/test_hybrid_routing_and_api.py` |
| **Privacy Fail-Closed** | `core/models/gateway.py` | Complete | `tests/test_hybrid_routing_and_api.py` |

---

## 3. Future Research & Extension Boundaries

- **Original Foundation Model Training**: Strictly gated. No pre-training foundation models from scratch without explicit executive scope and compute budget authorization.
- **LoRA Adaptation Track**: Focused on domain-specific fine-tuning of 7B–14B open-weight coding models using verified flight tapes (`docs/research/AI_RESEARCH_ROADMAP.md`).
