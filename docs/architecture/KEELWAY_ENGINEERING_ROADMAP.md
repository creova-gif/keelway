# Keelway Engineering Roadmap: Sovereign Hybrid AI Platform

## Phase 0: Foundation & Repository Unification (COMPLETED)
- **Status:** Complete & Verified
- **Milestones:**
  - Audited legacy codebase; resolved Kora vs Keelway naming and package structure.
  - Established unified Python test suite (Pytest 9.2, Python 3.14).
  - Implemented initial local adapter, flight recorder, and security guardrail inspection.

## Phase 1: Hybrid Inference & Model Agnosticism MVP (COMPLETED)
- **Status:** Complete & Verified
- **Milestones:**
  - **Centralized Model Registry (`core/models/registry.py`):** Pre-seeded catalog with 5 open-weight models (Qwen 2.5 Coder, Llama 3.3, Mistral Nemo, DeepSeek R1) and 4 proprietary models (GPT-4o, Claude 3.5 Sonnet, Gemini 2.5 Flash).
  - **Unified Provider Abstraction (`core/models/provider.py`):** Standardized interfaces for non-streaming completions, SSE chunk streaming, token metrics, and typed error hierarchies.
  - **Open-Weight Adapter (`core/models/adapters/open_weight.py`):** Native Ollama & OpenAI-compatible local runtimes (vLLM, llama.cpp) with zero-cost local execution.
  - **Closed Proprietary Adapter (`core/models/adapters/openai_provider.py`):** OpenAI Chat Completions API integration with exact per-token pricing attribution.
  - **Deterministic Hybrid Gateway (`core/models/gateway.py`):** Policy routing, cost arbitrage, fail-closed privacy containment, and append-only cost recording.
  - **Unified AI API Routes (`core/api/routes.py`):** `GET /v1/models`, `POST /v1/chat/completions` (JSON & SSE streaming), `GET /v1/usage`.
  - **Hybrid AI Benchmark Engine (`core/eval/hybrid_benchmark.py`):** 7-dimension evaluation harness with offline CI mock execution.
  - **Developer Console (`web-console/index.html`):** Interactive model catalog and prompt runner with live flight telemetry.

## Phase 2: Multi-Provider Expansion & Self-Hosted vLLM Clusters (Q3 2026)
- **Target Milestones:**
  - Native Anthropic Claude 3.5 Sonnet adapter with prompt caching and tool-calling support.
  - Native Google Gemini 2.5 Flash / Pro adapter with massive multimodal context window.
  - Terraform / Helm charts for autoscaling vLLM clusters on private Kubernetes (NVIDIA A100/H100).
  - Dynamic GPU health checks and automated model weight cold-start provisioning.

## Phase 3: Fine-Tuning & Sovereign Domain Adaptation (Q4 2026)
- **Target Milestones:**
  - LoRA / QLoRA automated fine-tuning pipeline for enterprise codebases.
  - Domain-specific adapters for African legal, financial, and multilingual engineering tasks (Swahili, Hausa, Yoruba, Amharic).
  - Model quantization pipeline emitting optimized GGUF (Q4_K_M / Q8_0) binaries.

## Phase 4: Autonomous Multi-Model Agent Orchestration (Q1 2027)
- **Target Milestones:**
  - Heterogeneous agent teams: fast open-weight models for linting/unit tests; frontier models for high-level architecture design.
  - Speculative decoding: local 1.5B model generates speculative drafts verified in parallel by a 70B model.
  - Monotonic flight recording with cryptographic proof-of-execution receipts.

## Phase 5: Global Enterprise Sovereign Cloud & Edge Appliances (Q2 2027+)
- **Target Milestones:**
  - Turnkey Keelway Hardware Appliance (rack-mountable 1U/2U server preloaded with open-weight models and air-gapped security firmware).
  - Distributed mesh consensus across multi-region enterprise nodes.
  - Automated regulatory compliance reporting (POPIA, GDPR, HIPAA, SOC 2 Type II).
