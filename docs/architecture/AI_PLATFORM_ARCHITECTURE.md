# Keelway AI Platform Architecture

## 1. Architectural Overview

The Keelway Intelligence Engine is structured across six distinct, loosely coupled layers providing end-to-end model agnosticism, deterministic routing, and sovereign governance.

```
+-------------------------------------------------------------------------+
| Layer 1: Experience & Product Interfaces                                |
|  - Keelway Web Console & Hybrid Playground                              |
|  - Developer Dashboard & Telemetry Visualizer                           |
|  - Headless CLI & Python SDK Client                                     |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| Layer 2: Unified AI API Gateway                                         |
|  - GET  /v1/models (Catalog Discovery across Open-Weight & Closed)       |
|  - POST /v1/chat/completions (OpenAI-compatible Non-Streaming & SSE)    |
|  - POST /v1/completions (Legacy Keelway backward compatibility)          |
|  - GET  /v1/usage (Sovereign Cost Ledger & Economics Telemetry)         |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| Layer 3: Model Provider Abstraction Layer                               |
|  - BaseModelProvider Interface (complete, stream_complete, health)      |
|  - Typed Error Normalization (Auth, RateLimit, Timeout, ContextOverflow)|
|  - Normalized Payloads (ChatCompletionRequest, StreamChunk, Usage)      |
+-------------------------------------------------------------------------+
              |                                            |
              v                                            v
+------------------------------+             +----------------------------+
| Open-Weight Adapter          |             | Closed Commercial Adapter  |
| - Ollama Native HTTP         |             | - OpenAI REST / SSE Client |
| - vLLM / OpenAI-Compat Engine|             | - Anthropic / Gemini Ready |
| - $0.00 External Cloud Cost  |             | - Exact Dollar Metering    |
+------------------------------+             +----------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| Layer 4: Centralized Model Registry                                     |
|  - Metadata Store (Category, Family, Deployment, Context, Capabilities) |
|  - Aliasing & Family Resolution                                         |
|  - License & Hardware Constraint Verification                           |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| Layer 5: Model Routing & Orchestration Engine                           |
|  - Deterministic Policy Router (Capability, Budget, Latency)            |
|  - Privacy Containment Invariant (Strict zero-egress for 'private')     |
|  - Air-Gap Fail-Closed Firewall                                         |
|  - Explainable Routing Decision Audit Trails                            |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
| Layer 6: Platform Security, Governance & Flight Recording               |
|  - RBAC & API Key Authentication                                        |
|  - Secret Token Redaction & Jailbreak Injection Inspection              |
|  - Sovereign Cost Ledger & Quantified Savings Accounting               |
|  - Monotonic Audit Trail & Flight Recording                             |
+-------------------------------------------------------------------------+
```

---

## 2. Layer Specifications

### Layer 1: Experience and Product Interfaces
- **Web Console (`/console`, `/web-console`):** Browser-based playground for interactive testing, live SSE streaming, and instant visualization of flight telemetry (latency, token counts, dollar costs, and routing justifications).
- **Studio Web UI (`/studio`):** Visual engineering dashboard for durable agent loops, task management, and approvals.

### Layer 2: Unified AI API
- Exposes standardized, OpenAI-compatible HTTP endpoints ensuring plug-and-play compatibility with external tools, agent frameworks, and developer workflows.
- Implements comprehensive request validation, CORS, rate-limiting, and error transformation.

### Layer 3: Model Provider Abstraction
- Defines `BaseModelProvider` abstract base class.
- Normalizes all provider anomalies into unified data structures (`ChatCompletionRequest`, `ChatCompletionResponse`, `StreamChunk`).
- Traps network faults, HTTP error codes, and provider downtime into typed exceptions (`ProviderAuthenticationError`, `ProviderRateLimitError`, `ContextLengthExceededError`, `ProviderTimeoutError`).

### Layer 4: Centralized Model Registry
- Thread-safe repository (`core/models/registry.py`) maintaining active inventories of open-weight models (Qwen 2.5 Coder, Llama 3.3, Mistral Nemo, DeepSeek R1) and proprietary models (GPT-4o, Claude 3.5 Sonnet, Gemini 2.5 Flash).
- Enforces accurate context length limits, hardware requirements, and licensing constraints.

### Layer 5: Model Routing and Orchestration Engine
- Evaluates incoming request parameters (`required_capabilities`, `max_cost_usd`, `max_latency_ms`, `privacy_level`).
- Enforces local-first cost arbitrage: routes to local open-weight runtimes by default; escalates to cloud providers only when necessary.
- **Privacy Invariant:** If `privacy_level == "private"`, cloud providers are permanently removed from candidate orders. If an unauthorized cloud model is explicitly requested, routing aborts and fails closed.

### Layer 6: Platform Security and Governance
- Inspects input prompts for prompt injection attacks and malicious payload signatures.
- Sanitizes PII and secret patterns before any processing.
- Logs every inference event into an append-only JSONL cost ledger for immutable accounting.
