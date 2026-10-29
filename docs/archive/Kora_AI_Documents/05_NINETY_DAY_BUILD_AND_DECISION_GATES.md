# Kora AI — 90-Day Build Plan and Decision Gates

## Execution philosophy
**Verify first, then build a narrow reusable system.** Do not use the plan as authorization to change repositories or deploy services. Named owners and budgets are TBD.

## Days 1–14: Evidence and mission gate
- Confirm exact Kora Technologies, Labs, Dev and research repo URLs/permissions.
- Read source, licenses, white papers, CI and release history.
- Reconcile mission and platform taxonomy with actual code.
- Investigate TNet/chacc/africa-stack lineage and ownership.
- Produce audit, risk register, current-vs-target architecture and priority decisions.
- Approve first personal-agent workflow and spending cap.

**Exit:** verified inventory and ownership questions recorded; signed-off architecture scope.

## Days 15–30: Core foundations
- ADRs: model gateway, state store, retrieval, permission model, repo topology.
- Build isolated prototype: auth, FastAPI API, model adapter, read-only source connector.
- Implement evidence citations, session memory and minimal trace logging.
- Create 30–50 evaluation fixtures and malicious-content tests.

**Exit:** demo that answers repository questions with verifiable source paths and no write privileges.

## Days 31–45: Durable work
- Add task state machine, retries, cancellation, budgets and approvals.
- Implement daily engineering brief and Labs research brief.
- Add cost/latency/error dashboards.
- Run privacy/security review.

**Exit:** 2 workflows complete repeatedly and recover from tool errors.

## Days 46–60: Kora Dev connection
- Define Kora Dev ↔ AI Core API/CLI contract.
- Add sandboxed test runner only after threat model and isolation verification.
- Prototype plan → test → review workflow; no autonomous merges.
- Publish SDK contract and compatibility tests.

**Exit:** one source-grounded developer workflow with auditable tool execution.

## Days 61–75: Benchmarks and design partners
- Evaluate models against task quality, latency and cost.
- Test offline/slow network assumptions on controlled fixtures.
- Recruit 5–10 trusted testers if privacy/legal controls are ready.
- Review research-to-product transfer candidates.

**Exit:** measured baseline, documented failures, prioritized improvements.

## Days 76–90: Investment gate
- Resolve P0 security and provenance issues.
- Validate repeated use and value of 3 workflows.
- Review open-source vs commercial boundaries.
- Decide whether to scale AI Core, invest in Kora Dev Desktop or focus on the initial wedge.
- Publish internal 90-day report, ADRs and next-quarter backlog.

**Exit:** evidence-based go/pivot/stop decision.

## Backlog priorities
| Priority | Item | Acceptance evidence |
|---|---|---|
| P0 | Repo discovery and ownership | URLs, commits, licenses, owners |
| P0 | Auth and scoped read-only connector | access tests and logs |
| P0 | Evaluation/security harness | versioned passing tests |
| P1 | Model gateway and retrieval | reproducible quality/cost results |
| P1 | Durable task orchestration | retry/cancel/approval tests |
| P1 | Kora Dev integration | typed contract and sandbox tests |
| P2 | Local/edge models | comparative benchmark |
| P2 | Desktop and multi-agent UX | validated user need |
| P3 | Custom foundation model | only with justified data/economics |

## Operating cadence
Weekly engineering review; biweekly security and evaluation check; monthly Labs research review; day-30/60/90 investment gates. All major decisions recorded as ADRs.

## Budget model
Set a monthly cap for model tokens, cloud resources, data storage and external evaluation. Record cost per successful task, not just cost per token. Do not invent dollar estimates before workload benchmarks.
