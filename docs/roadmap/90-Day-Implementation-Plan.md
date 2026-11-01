# Keelway — 90-Day Implementation Plan

**Goal:** Working Personal Keelway agent built on a reusable AI Core, with limited Keelway Dev integration and measured reliability.

**Success metric:** Reliably completes at least three real recurring workflows and saves measurable time without unauthorized actions.

## Phase 1: Days 1–30 — Foundation

| # | Deliverable | Owner | Done criteria |
|---|-------------|-------|---------------|
| 1 | Keelway Core architecture doc + ADR-001 | Lead | ADR accepted |
| 2 | FastAPI backend skeleton + multi-provider model gateway (Claude + at least one other) | Backend | Health endpoint + simple completion works across two providers |
| 3 | Private chat interface with authentication | Full-stack | Authenticated user can chat |
| 4 | Read-only GitHub connector | Backend | Can list/read repos and files with citations |
| 5 | PostgreSQL memory + basic provenance | Backend | Can store and retrieve session + long-term records |
| 6 | First 30 evaluation tasks defined | Research | Tasks in `evaluations/` with expected outputs |

## Phase 2: Days 31–60 — Reliable Execution

| # | Deliverable | Owner | Done criteria |
|---|-------------|-------|---------------|
| 7 | Task state machine + durable jobs | Backend | Tasks survive restarts; retries work |
| 8 | Keelway Agent Gateway with scoped permissions | Backend | Gateway enforces scopes; audit log exists |
| 9 | Sandboxed test and code-inspection tools | Backend | Can run tests in isolation |
| 10 | Keelway Dev CLI integration (minimal) | Dev | CLI can trigger a simple agent task |
| 11 | Model quality / latency / cost benchmarks | Research | Spreadsheet or dashboard of results |
| 12 | Pilot three real personal-agent workflows | Product | Workflows run end-to-end with human approval where needed |

## Phase 3: Days 61–90 — Validate Platform

| # | Deliverable | Owner | Done criteria |
|---|-------------|-------|---------------|
| 13 | Agent recovery and approval workflows | Backend | Failed tasks can be resumed or escalated |
| 14 | Small/local model evaluation vs hosted | Research | Comparison report |
| 15 | Observability, security tests, audit logs | Platform | Traces + audit trail visible |
| 16 | Prototype Keelway Dev agent orchestration | Dev | One multi-step Dev workflow works |
| 17 | Recruit 5–10 developer testers | Product | Feedback collected |
| 18 | Research findings + next investment gate | Lead | Decision document published |

## Risks and Mitigations

- **Scope creep** → Stick to three workflows as the success bar.
- **Unsafe tool use** → Four permission levels; injection defenses at tool boundary; no auto-modify without explicit authorization.
- **Cost overrun** → Router + caching + per-task cost tracking from Phase 1.
- **Integration delays** → Start with read-only GitHub; expand only after gateway is solid.

## Resources

- Engineering capacity (Python/TypeScript)
- Cloud AI services + GitHub
- Google Cloud services (Cloud Run, Postgres/AlloyDB, Storage, BigQuery, IAM)
- NVIDIA API / NIM access
- Small research budget only after evaluation evidence

## Weekly Cadence (suggested)

- Monday: Plan and review open ADRs
- Wednesday: Demo progress on one workflow
- Friday: Evaluation run + cost review
