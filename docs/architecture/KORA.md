# KORA.md

Living document for Kora AI Core principles, conventions, and current decisions.

## Core Principles

1. Shared intelligence layer, isolated permissions and memory.
2. Evaluation-first development.
3. Explicit state machines before opaque multi-agent loops.
4. Four permission levels: read → draft → sandbox → modify.
5. Secrets never in memory or Git.
6. External content is untrusted.
7. Model routing by capability, cost, latency, and privacy.
8. Provenance and temporal validity on all long-term knowledge.

## Model Strategy

- Multi-provider gateway (Claude, OpenAI, Google Gemini, NVIDIA, open-weight, local/edge).
- Routing by capability, cost, latency, privacy, residency.
- First 90 days: adopt foundation models; build eval + data + serving infrastructure.
- Later: fine-tuning / adapters, then small domain or African-language models only when benchmarks justify it.
- Own general frontier LLM is out of scope until infrastructure and evidence are mature.

## Current Stack (90-day target)

- Backend: FastAPI (Python)
- Database: PostgreSQL + pgvector
- Orchestration: Explicit task state machine
- Models: Multi-provider gateway (Claude, OpenAI, Google, NVIDIA, open-weight, local)
- Cloud: Google Cloud (Cloud Run, AlloyDB/Cloud SQL, Cloud Storage, BigQuery, IAM) + any other needed
- Auth: OIDC / scoped tokens
- Observability: OpenTelemetry

## Active Initiatives

- Kora AI Core (foundation)
- Kora Personal Agent (first customer)
- Kora Dev (distribution channel, limited integration first)

## Key ADRs

- ADR-001: AI Core Architecture Principles

## Success Metric (first 90 days)

Reliably complete at least three real recurring workflows with measurable time savings and zero unauthorized actions.
