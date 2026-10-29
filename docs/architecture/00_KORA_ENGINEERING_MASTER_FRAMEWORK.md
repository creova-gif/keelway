# Kora Technologies — Engineering, Architecture & DevOps Operating Framework

**Status:** Proposed framework pending source-code audit  
**Scope:** Kora Technologies, Kora Dev and Kora infrastructure modules  
**Date:** 2026-10-10

## Evidence and limitations
The connected GitHub search for `kora in:name user:creova-gif` and the `creova-gif` owner listing returned no accessible repositories in this session. Therefore this is **not a completed source-code audit**. Existing local Kora master research documents, Kora Dev planning files and the four supplied screenshots inform the *requirements and design direction*. The screenshots show GitHub Actions, code/documentation diagrams, API lifecycle flows and Mermaid-style sequence/state visualizations; they are examples, not proof of current Kora implementation.

## Target structure
```text
Kora Technologies
├── Architecture and governance
├── Platform APIs / data / security
├── Docker / CI-CD / infrastructure
├── Observability / incident management
├── Research -> RFC -> ADR -> implementation
└── Kora Dev
    ├── CLI + KORA.md
    ├── agent runtime / sandboxes / evaluations
    ├── GitHub / CI / deployment integration
    └── Desktop command center
```


## 1. 01 Repository Discovery And Evidence

First inspect all available Kora repositories, branches, tags, workflows, release history, dependency manifests, Dockerfiles, infra directories, tests, docs, research and ADRs. Inventory each repository by URL, branch, last commit, languages, owners, build command, test command, deployments, known risks and evidence path. Never pretend inaccessible repos were audited. Classify observations CONFIRMED / INFERRED / PROPOSED / UNVERIFIED. Compare the Kora master research and white papers with actual implementation; make a gap matrix. Do not modify code before producing the audit and obtaining approval for destructive changes.

## 2. 02 Engineering Governance And Stack

Define engineering principles, repo ownership, CODEOWNERS, branch protection, conventional commits, semantic versioning, RFC/ADR process, dependency support policy, issue and PR templates, quality gates, release ownership, and a technology decision matrix. Evaluate Rust vs Go for Kora CLI/daemon; Tauri vs Electron for Desktop; FastAPI vs Go/TypeScript for services; PostgreSQL/SQLite by data domain. Document tradeoffs, benchmarks and exceptions. Use modular monolith when appropriate; split into services only on proven scaling, security, team or deployment boundaries. Evaluate monorepo vs polyrepo with explicit migration cost.

## 3. 03 Architecture And Documentation

Use C4 context/container/component diagrams, Mermaid state machines and sequence diagrams, OpenAPI and AsyncAPI contracts, dependency diagrams, dataflow and threat diagrams. Tie documentation to source paths, tests and versions. Require a source-to-diagram verification checklist. Model state transitions, permissions, errors, retries, idempotency, audit events and compensating actions. Every diagram states whether observed or proposed. Provide module boundary rules, API versioning, compatibility policy, ADR links and deprecation schedule.

## 4. 04 Apis Events Webhooks And Sdks

Specify REST/gRPC/event selection criteria; OpenAPI 3.1, AsyncAPI, request IDs, pagination, rate limits, typed errors, auth scopes, API keys/OAuth/OIDC where appropriate, idempotency keys, timeout budgets, circuit breakers, and consumer-driven contract tests. For webhooks: HMAC signature verification, timestamp/replay protection, retry/backoff, DLQ, ordering expectations, delivery receipts and observability. Generate versioned SDKs only from validated contracts and test Python, TypeScript, Go and other languages according to demand.

## 5. 05 Containers Deployment And Iac

Dockerfile standards: multi-stage builds, pinned base images/digests, minimal runtime images, nonroot users, healthchecks, .dockerignore, SBOM, build attestations, vulnerability scans and multi-arch builds when needed. Compose for local reproducibility. Separate local/dev/staging/prod/ephemeral environments; secrets outside images. Use GitHub Actions with build/test/scan/package/publish/deploy stages and gated promotion. Prefer managed containers for early services; evaluate Kubernetes only if justified. Evaluate OpenTofu/Terraform, environment state, drift detection, approvals, rollback, blue-green/canary, disaster recovery and cost controls.

## 6. 06 Database Data And Recovery

Define PostgreSQL and SQLite usage, schema ownership, migrations, zero-downtime expand/contract migrations, RLS verification, encryption, backup cadence, PITR, restore drills, retention, deletion, data classification, tenancy, data residency, cross-border replication and offline sync/conflict resolution. For Kora Finance require double-entry ledger invariants, reconciliation, immutable audit trail and idempotent financial operations. Define RPO/RTO per product; do not invent SLA guarantees.

## 7. 07 Security Supply Chain And Compliance

Use OWASP ASVS and threat modeling, least privilege, secrets management, OIDC federation for CI, protected environments, CODEOWNERS, SAST/DAST/SCA, Gitleaks, Trivy, SBOM, provenance/signing with Cosign where suitable, dependency pinning, artifact registries, vulnerability SLAs and incident response. Add AI-agent prompt injection defense, tool allowlists, sandbox isolation, scoped filesystem/network/secrets, human approval gates, audit logs, enterprise RBAC and data retention. Country compliance claims require jurisdiction-specific legal review.

## 8. 08 Testing Quality And Observability

Define unit, integration, contract, end-to-end, migration, chaos, performance, load, accessibility, security and offline/network impairment tests. Establish coverage goals by risk rather than arbitrary universal percentage. Use OpenTelemetry traces/metrics/logs, structured logging, correlation IDs, SLOs/SLIs, alert routing, dashboards, incident playbooks, postmortems and error budgets. Record p50/p95/p99, throughput, compute, memory and unit economics with reproducible workloads.

## 9. 09 Kora Dev Integration

Kora Dev remains CLI-first: kora init/doctor/ask/plan/build/test/review/deploy/observe; shared local daemon and agent runtime; KORA.md policy contract; context provenance; isolated Git worktrees/containers; model-provider abstraction; evaluations; secure permissions; Agent/Plugin/Provider SDKs; later Tauri/Electron Desktop chosen through evidence. GitHub Actions becomes a first-class agent tool with explicit permissions, workflow visibility and release provenance. Desktop should visualize architecture, Git, CI pipelines, state machines, task/agent graphs, code diffs, terminal, deployment and telemetry. Kora Infrastructure Registry and low-connectivity, mobile-money and regional-readiness checks remain phased proposals, not shipped features.

## 10. 10 Research To Engineering And Ip

Maintain software / documentation / research as three linked layers. Preserve source evidence, hypothesis, experiment IDs, benchmark method, ADR, RFC, reproduction, original contribution and IP classification. Claims are SOURCE-VERIFIED / PRIMARY EVIDENCE / INTERNAL EXPERIMENT / INTERNAL IMPLEMENTATION CLAIM / SECONDARY SOURCE / MODEL INFERENCE / PROPOSED / UNVERIFIED. Never claim performance or legal novelty without evidence. Link every research-to-engineering handoff to code, tests and acceptance criteria.

## 11. 11 Implementation Roadmap

Phase 0: repo access, evidence inventory, dependency and CI security scan. Phase 1: architecture baseline and stack ADRs. Phase 2: baseline CI, tests, versioning, release policy, Docker and local reproducibility. Phase 3: API contracts, database migration safety, observability, deployment promotion and rollback. Phase 4: Kora Dev CLI integration, KORA.md, agent sandbox/evals. Phase 5: Desktop visualization and provider registry. Each phase must define owner, effort range, dependencies, deliverables, measurable acceptance tests, rollback, risks and status. No automatic destructive changes.

## 12. 12 Agent Execution Master Prompt

Act as Kora Technologies' CTO, principal architect, platform engineer, DevSecOps lead, staff developer-experience engineer, AI systems architect, and research integrity reviewer. FIRST locate and inspect the actual Kora repositories and research artifacts. Report accessible and inaccessible sources. Do not invent repository contents or CI status. Produce a source-grounded current-state audit, proposed target architecture, ranked gap analysis, ADRs, Docker/CI/API/security/observability standards, Kora Dev integration plan and phased backlog. Treat supplied screenshots only as reference patterns, not evidence of Kora implementation. Do not execute migrations, rename repos, change cloud infrastructure, expose secrets, publish packages or deploy without explicit authorization. Every proposed technology must include alternatives and selection criteria. Separate current, target and experimental states. Generate Mermaid/C4 diagrams and source-linked documentation. Provide commands, workflows and code changes only after inspecting project files. Finish with acceptance gates, verification commands, open questions and an evidence register.

## Repository audit inventory template

| Repository | Accessible? | Commit/branch | Stack | CI | Container | Security | Tests | Evidence | Gaps |
|---|---|---|---|---|---|---|---|---|---|
| TBD | Not verified | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Audit required |

## Definition of done

A production-ready engineering standard requires audited repositories, approved ADRs, reproducible builds, protected release pipelines, security scans, verified deployment/rollback, tested database recovery, observable services, source-linked architecture documentation and accountable owners.
