# ADR-001: Kora AI Core Architecture Principles

**Status:** Proposed  
**Date:** 2026-10-28  
**Deciders:** Kora AI team  
**Consulted:** Engineering, Research  

## Context

Kora is moving from AI integration (calling external models/agents) to building reusable AI infrastructure. We need a shared intelligence layer that multiple products (Personal Agent, Kora Dev, future applications) can use while keeping permissions, memory, and user experience isolated.

Key constraints: small team, constrained budget, need for reliability, cost control, security, and portability. The system must support multiple model providers (Anthropic Claude, OpenAI, Google, NVIDIA, open-weight models, local/edge) and leave a clear path for custom or proprietary models later.

## Decision

Adopt a shared AI Core with the following principles:

1. **Model-agnostic gateway** with provider adapters and policy-based routing (capability, cost, latency, privacy, data residency). Supported providers from day one: Anthropic (Claude), OpenAI, Google (Gemini), NVIDIA (NIM / API catalog), and at least one open-weight or local runtime. New providers are added by writing an adapter, not by changing application code.
2. **Hybrid memory and retrieval** — PostgreSQL + pgvector for long-term memory and knowledge, with provenance and temporal validity. Short-term session memory separate.
3. **State-machine orchestration** for tasks (plans, retries, human approvals, recovery). Prefer explicit state over opaque agent loops initially.
4. **Kora Agent Gateway** as the controlled interface to all Kora systems (GitHub, Research, Dev, Observe, Cloud, Connect). Each capability has its own contract, auth scope, audit, and approval policy.
5. **Four permission levels**: read, draft, execute in sandbox, modify external systems.
6. **Evaluation-first**: Maintain a suite of Kora-specific tasks. Run evaluations on material changes to models, prompts, or tools. Compare providers and model sizes on the same tasks.
7. **Secrets and untrusted content**: Secrets only in a secret manager. Treat all external content as untrusted; apply injection defenses at tool boundaries.
8. **Start intermediate, scope small**: FastAPI + PostgreSQL + multi-provider gateway (begin with 2–3 providers) + typed tools. Add complexity only when justified by measured need.
9. **Custom / own models path**: Do not train a general frontier LLM in the first 90 days. Instead, build the data, evaluation, and serving infrastructure that can later support fine-tuning (LoRA/QLoRA), small domain models, or a proprietary model if benchmarks show a clear advantage. Research into African-language or domain-specific adaptation is explicitly in scope.

## Consequences

**Positive:**
- Reusable infrastructure reduces duplication.
- Clear security and audit boundaries.
- Portability across model providers (Claude, OpenAI, Google, NVIDIA, open models, local).
- Measurable reliability via evaluation harness.
- Aligns with Google Cloud (runtime, data, observability) and NVIDIA (inference) while remaining independent of any single vendor.
- Clear research path toward custom models without premature investment.

**Negative / Risks:**
- Initial velocity may be slower than pure single-provider API calls.
- Requires discipline on permissions and evaluations.
- Must actively manage cost via routing and caching.
- Multi-provider increases surface area for API changes.

**Mitigations:** Success measured by three real workflows completed reliably, not by number of integrations. Quarterly review of economics, reliability, and model performance. Prefer adapters over tight coupling.

## Alternatives Considered

- Single-provider lock-in (only Claude, only OpenAI, only NVIDIA, etc.) → rejected; reduces portability and bargaining power.
- Pure MCP / external agent integration only → rejected because it does not create defensible Kora infrastructure.
- Full multi-agent framework from day one → rejected; start with explicit state machine.
- Training a custom frontier model immediately → rejected for the first 90 days; expensive and not necessary to prove the infrastructure thesis. Research path remains open.
- Ignoring open-weight / local models → rejected; important for cost, privacy, offline, and edge use cases.

## Related

- KORA.md
- Future ADRs on memory lifecycle, model routing policies, sandbox design, fine-tuning pipeline.
