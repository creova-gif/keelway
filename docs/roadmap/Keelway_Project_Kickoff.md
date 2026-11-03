# Keelway — Project Kickoff & Starter Documentation

**Planning horizon:** 2026–2031  
**Scope:** Sorvex Labs, Keelway Dev, Keelway, Personal AI Assistant  
**Status:** Project start — foundation phase  
**Date:** October 2026

## Executive Recommendation

Keelway should evolve from integrating AI services into building reusable AI infrastructure and intelligent systems.

- **AI integration**: Application calls a model, MCP server, or external agent.
- **AI engineering**: Control retrieval, memory, orchestration, evaluation, execution, and deployment.
- **AI infrastructure**: Build reusable runtimes, gateways, protocols, SDKs, and operating systems other developers can use.
- **AI research**: Investigate new architectures, efficiency techniques, datasets, benchmarks, and original IP.

**Three connected initiatives:**
1. **Keelway Core** — Shared intelligence infrastructure (model routing, retrieval, memory, evaluations, security, inference, agent execution).
2. **Keelway Dev** — CLI-first developer platform with coding agents, isolated workspaces, Git integration, testing, deployments, and future desktop control plane.
3. **Keelway Personal Agent** — Internal assistant for research, engineering, documentation, decisions, and authorized Keelway operations, built on the same AI Core.

The personal agent is the first demanding internal customer. Keelway Dev is the developer-facing distribution channel.

## Problem Grounding

**Audience:** Keelway engineering and research team (primary); external developers via Keelway Dev (secondary).

**Problem statement:** Agent loops multiply cost, latency, and failure modes. Persistent context is lost or becomes noisy. Tool use is unsafe without scoped permissions, audit, and recovery. Pure API integration does not deliver reliable, economical, portable systems under real infrastructure constraints (latency, cost, connectivity, sovereignty, power).

**Evidence sources:** Internal Keelway metrics (time on repetitive tasks, PR review load, cost per workflow); Stanford AI Index (evaluation and governance gaps); IEA data-centre electricity projections; NIST AI RMF.

**SDG alignment:** SDG 9 (Industry, Innovation and Infrastructure), SDG 8 (Decent Work and Economic Growth). Optional SDG 4 if education-adjacent paths expand.

## Solution Overview

One shared intelligence layer, multiple interfaces, controlled access to Keelway infrastructure.

**Architectural principle:** Share the model gateway, retrieval, policy, telemetry, and execution infrastructure. Keep each application’s permissions, memory, and user experience isolated.

### Recommended Starting Architecture (Intermediate, beginner-sized scope)

| Layer | Responsibility | Suggested Approach |
|-------|----------------|--------------------|
| Interface | Chat, voice, terminal, eventually Desktop | Web chat + CLI initially |
| Model gateway | Select model by capability, price, latency, privacy | Provider adapters + routing policies |
| Short-term memory | Current task, conversation, active context | Session store + compact summaries |
| Long-term memory | Projects, preferences, decisions, outcomes | PostgreSQL + retrieval + structured records |
| Knowledge layer | GitHub, documents, architecture, research | Hybrid search with provenance |
| Orchestration | Plans, task states, retries, approvals | State-machine workflow engine |
| Tool execution | Read repositories, run tests, create documents | Typed tools and sandboxed workers |
| Identity and policy | Who can access or modify what | OAuth/OIDC, scoped tokens, RBAC |
| Observability | Trace agent decisions, errors, costs | OpenTelemetry + evaluation records |

**Recommended stack for first 90 days:** FastAPI (Python), PostgreSQL + pgvector, single hosted model, typed tools, explicit task state machine. Add sophisticated orchestration only when complexity justifies it.

### Model Strategy (multi-provider + path to own models)

The model gateway is provider-agnostic by design. Initial supported providers:

- **Anthropic Claude** — strong reasoning, long context, coding, and tool use. Primary candidate for complex agent workflows.
- **OpenAI** — broad capability, mature tooling, good for general tasks.
- **Google Gemini** — multimodal strength, tight integration if using Google Cloud heavily.
- **NVIDIA NIM / API catalog** — efficient inference, specific models for code, documents, or edge-oriented workloads.
- **Open-weight models** (Llama, Qwen, Mistral, etc.) via local runtime or hosted endpoints — privacy, cost, offline, and customization.
- **Local / edge small models** — for latency-sensitive, private, or intermittent-connectivity scenarios.

**Routing policy** (capability, cost, latency, privacy, data residency) decides which model handles a given request. Applications never call a provider directly.

**Path to custom / own LLM:**
- First 90 days: adopt foundation models; build evaluation harness, data pipelines, and serving infrastructure.
- Medium term: fine-tuning / adapters (LoRA, QLoRA) on open models when prompting + RAG consistently underperform on measured Keelway tasks.
- Longer term: train or continue-train small domain-specific or African-language models only when benchmarks show a clear advantage over adapted open models. Do not attempt a general frontier LLM until there is strong evidence of differentiation and the supporting infrastructure (data, eval, serving, governance) is mature.

### Google Cloud + NVIDIA + other providers (meaningful product features)

- **Google Cloud:** Cloud Run (or GKE) for agent backend and gateway; AlloyDB/PostgreSQL or Firestore for memory and provenance; Cloud Storage for artifacts; BigQuery for cost/latency analytics and evaluation results; IAM + OIDC for identity. Used for durable execution, data, and observability.
- **NVIDIA:** NIM or API catalog models for grounded answers, code understanding, document retrieval, or efficient inference. Keys in secret manager.
- **Anthropic Claude / OpenAI / Google Gemini:** Primary hosted models for reasoning, coding, and general agent tasks via the gateway.
- **Open / local models:** Fallback, privacy-sensitive, or cost-optimized paths.

All providers contribute through the shared gateway. No single vendor is required for the product to function.

## 90-Day Action Plan

**Success criteria:** The assistant reliably completes at least three real recurring workflows and saves measurable time without unauthorized actions.

### Days 1–30: Establish the foundation
- Create Keelway Core architecture and initial ADRs
- Implement FastAPI agent backend and model gateway
- Build private chat interface with authentication
- Connect read-only GitHub and Keelway research sources
- Establish PostgreSQL memory and provenance
- Create first 30–50 evaluation tasks

### Days 31–60: Prove reliable execution
- Implement task state machine and durable jobs
- Build Keelway Agent Gateway with scoped permissions
- Add sandboxed test and code-inspection tools
- Introduce Keelway Dev CLI integration
- Benchmark model quality, latency, and cost
- Pilot three real personal-agent workflows

### Days 61–90: Validate the platform
- Implement agent recovery and approval workflows
- Evaluate small/local models against hosted baselines
- Add observability, security tests, and audit logs
- Prototype Keelway Dev agent orchestration
- Recruit 5–10 developer testers
- Publish research findings and decide next investment gate

## Build vs Adopt

| Component | Decision | Rationale |
|-----------|----------|-----------|
| Foundation models | Adopt | Avoid unnecessary frontier training costs |
| Model gateway | Build | Strategic routing, portability, economics |
| Vector database | Adopt | PostgreSQL/pgvector is sufficient initially |
| Memory architecture | Build | Central to persistent Keelway intelligence |
| Agent orchestration | Build on frameworks | Own Keelway’s policy, state, and evaluation logic |
| Sandboxing | Integrate then extend | Reuse mature isolation mechanisms |
| Evaluation system | Build | Domain-specific reliability becomes an asset |
| Keelway Dev CLI | Build | Flagship developer interface |
| Workflow infrastructure | Adopt/integrate | Use established durable execution where possible |
| Small domain models | Research, then selectively train | Only when benchmarks justify it |

## Security and Privacy

Four permission levels: read, draft, execute in sandbox, modify external systems.

- Keep external content untrusted (web pages, repository comments, documents).
- Apply prompt-injection defenses at the tool boundary.
- Store secrets in a secret manager; never in agent memory or Git.
- Separate personal information from corporate project data.
- Enforce retention rules and maintain an audit trail for tool calls.
- Consistent with NIST AI Risk Management Framework and its generative-AI profile.

## Suggested Repository Structure

```
keelway/
├── core/
│   ├── models/
│   ├── routing/
│   ├── memory/
│   ├── retrieval/
│   ├── orchestration/
│   ├── policy/
│   └── telemetry/
├── agents/
│   ├── personal/
│   ├── engineering/
│   ├── research/
│   └── infrastructure/
├── integrations/
│   ├── github/
│   ├── keelway-dev/
│   ├── keelway-connect/
│   └── keelway-cloud/
├── evaluations/
│   ├── coding/
│   ├── retrieval/
│   ├── reasoning/
│   ├── security/
│   └── cost-latency/
├── research/
│   ├── papers/
│   ├── experiments/
│   ├── benchmarks/
│   ├── datasets/
│   └── findings/
├── docs/
│   ├── architecture/
│   ├── adr/
│   ├── rfc/
│   └── security/
└── KEELWAY.md
```

Reconcile with existing Keelway repositories before creating a new one.

## Five-Year Research Priorities (ranked)

1. Reliable agent execution and evaluation (immediate · very high product potential)
2. Inference efficiency and intelligent model routing (immediate · high infrastructure/IP potential)
3. Persistent memory and evidence-grounded knowledge (immediate · high reuse)
4. Offline and edge intelligence (medium-term · Africa-native differentiation)
5. African-language and domain-specific AI (exploratory · potentially high research value)

Do not prioritize training a general-purpose frontier LLM in the first 90 days.

## Next Immediate Actions

1. Create the repository (or confirm existing) and add this starter structure.
2. Write ADR-001 (AI Core architecture principles).
3. Set up the FastAPI skeleton + PostgreSQL + model adapter.
4. Define the first three target workflows for the Personal Agent.
5. Draft the first 10 evaluation tasks.
6. Document Google Cloud and NVIDIA integration points in the README.

## Documentation Deliverables (target)

- README: audience, problem, SDG, solution, setup/run instructions, Google Cloud + NVIDIA integration, screenshots/demo links, team credits, individual contributions.
- Written summary (≤ 3 pages): research, solution, implementation plan, timeline, resources, risks, testing, next steps.
- Presentation deck (≤ 8 slides) and recorded walkthrough (≤ 5 minutes): user journey, working features, impact, lessons learned. Link both in the README.

---

*This document is the starting point. Update it as ADRs, experiments, and measured results accumulate.*
