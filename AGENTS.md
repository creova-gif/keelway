# KEELWAY — UNIVERSAL ENGINEERING CONTRACT

> **Authoritative Specification & Operating Contract for All AI Agents**  
> Applicable to: Google Antigravity, Claude Code, Devin, Cursor, Codex, and gstack.  
> Target Repository: `https://github.com/creova-gif/kora.git` | Deployment: `https://kora-sable.vercel.app/`

---

## 1. MISSION & ARCHITECTURAL FOUNDATION

**Keelway** is an enterprise-grade sovereign AI platform providing:
1. **Unified AI Model Gateway**: First-class support for both open-weight models (Qwen 2.5, Llama 3.3, DeepSeek R1/V3 via local Ollama or private vLLM/TGI clusters) and proprietary frontier models (Claude 3.5/3.7, GPT-4o, Gemini 1.5/2.0).
2. **Deterministic Governance & Privacy Fail-Closed**: Strict air-gap and privacy controls ensuring zero unauthorized cloud egress for sensitive tenant payloads.
3. **Reproducible Agentic Orchestration**: Hash-chained Merkle flight recorder tapes, cryptographic execution receipts, and sandboxed tool runners.
4. **Economic Observability**: Real-time cost ledger tracking exact tokens, compute expenditure, and quantified savings of open-weight over cloud models.

---

## 2. FUNDAMENTAL PRINCIPLE: REPOSITORY IS PERSISTENT MEMORY

1. **No Proprietary Memory Dependency**: Chat histories, private agent memories, and session contexts are ephemeral. The Git repository is the sole persistent source of truth.
2. **Operate from Verified State**: Agents must inspect real code and Git state (`git status`, `git diff`, test outputs) rather than assuming past conversations were accurate.
3. **No Hallucinated Progress**: Never claim a test passed, a file was modified, or an API functions without executing verification commands and inspecting output.
4. **Single Source of Truth**: All architecture decisions, active tasks, and handoffs reside in version-controlled Markdown files under `docs/`.

---

## 3. UNIVERSAL TASK EXECUTION PROTOCOL (Stages A–F)

Every agent—regardless of platform—must execute work through these six stages:

```
[ Stage A: Orient ]  --> Read AGENTS.md, docs, inspect git status & HEAD
        |
[ Stage B: Plan ]    --> Define problem, acceptance criteria, affected files
        |
[ Stage C: Implement]--> Smallest coherent diff, follow existing patterns
        |
[ Stage D: Verify ]  --> Run automated test suites, typecheck, lint, build
        |
[ Stage E: Review ]  --> Self-audit security, regressions, fail-closed boundaries
        |
[ Stage F: Deliver ] --> Produce structured handoff, update docs/agent-operations/
```

### Stage A — Orient
- Read `AGENTS.md` and relevant docs in `docs/architecture/` and `docs/engineering/`.
- Inspect `docs/agent-operations/ACTIVE_TASKS.md` for task context.
- Run `git status`, `git branch`, and check recent commits.
- Identify discrepancies between documentation and implementation.

### Stage B — Plan
- Translate requirements into explicit, falsifiable **Acceptance Criteria**.
- Enumerate affected components and verify no unintended blast radius.
- Identify security constraints (PII redaction, air-gap, permission levels).
- Document non-trivial architectural decisions in `docs/decisions/` (ADR format).

### Stage C — Implement
- Implement the smallest coherent change.
- Follow existing codebase idioms (Python 3.11+, Pydantic v2, FastAPI, async httpx).
- Never introduce unnecessary abstraction layers or duplicate utilities.
- Preserve backward compatibility unless an architectural exception is approved.

### Stage D — Verify
- Execute the test suite using the project environment:
  ```bash
  # Run targeted unit & integration tests
  pytest tests/test_<feature>.py -v
  ```
- Verify both positive path, edge cases, and negative/failure paths.
- Never use a mock test to claim a live external service is operating.

### Stage E — Review
- Audit against Keelway Security Invariants (see Section 6).
- Verify zero hardcoded credentials, secret leaks, or unredacted tape records.
- Check error disclosures: never leak internal stack traces to public HTTP endpoints.

### Stage F — Deliver
- Update task state in `docs/agent-operations/tasks/<TASK_ID>.md`.
- Update index in `docs/agent-operations/ACTIVE_TASKS.md`.
- Output a structured cross-agent handoff summary matching the Keelway schema.

---

## 4. CROSS-AGENT HANDOFF SPECIFICATION

When concluding a turn or pausing work, the agent **must** format the handoff using this schema:

```markdown
### TASK HANDOFF RECORD
- **TASK ID**: KEEL-<CATEGORY>-<NUMBER>
- **TASK TITLE**: <Clear title>
- **CURRENT STATUS**: [IN_PROGRESS | BLOCKED | READY_FOR_REVIEW | COMPLETED]
- **LAST AGENT**: [Antigravity | Claude Code | Devin | Cursor | gstack]
- **DATE**: YYYY-MM-DD
- **BRANCH**: <branch-name>
- **HEAD COMMIT**: <7-char commit SHA or current git status state>

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Criterion 1 (Status & proof)
- [ ] Criterion 2 (Remaining)

#### WORK COMPLETED & FILES MODIFIED
- `<path/to/file>`: <Description of modifications>

#### TESTS EXECUTED & EVIDENCE
- `<command>`: `<exact result count, e.g. 16 passed in 0.38s>`

#### KNOWN RISKS & BLOCKERS
- <Disclosed limitations, blockers, or missing credentials>

#### NEXT RECOMMENDED ACTION
- <The exact next atomic step the next agent must take>
```

---

## 5. SAFE MULTI-AGENT GIT WORKFLOW

- **One Task per Branch**: Never work directly on `main` for multi-step tasks.
  - Features: `feature/<task-id>-<short-description>`
  - Fixes: `fix/<task-id>-<short-description>`
  - Refactors: `refactor/<task-id>-<short-description>`
- **Isolated Worktrees**: When parallel agents operate on the same machine, use `git worktree add ../keelway-worktrees/<task-id> <branch>`.
- **Pre-Execution Check**: Always run `git status` before editing. If uncommitted changes exist, determine if another agent left active work before touching files.
- **Prohibited Actions Without Human Approval**:
  - `git push --force` or `git push -f`
  - Deleting shared branches
  - Bypassing branch protection or disabling failing security gates
  - Hardcoded credential commits or committing `.env` / database files

---

## 6. MANDATORY SECURITY & GOVERNANCE INVARIANTS

All agents must uphold Keelway's verified security invariants:

1. **Privacy Fail-Closed**: Requests flagged as `private`, `air_gap`, or containing classified tenant data must route strictly to local models (`open_weight` via Ollama/vLLM). Cloud egress attempts must raise `AirGapViolationError` (HTTP 403).
2. **Credential Redaction**: API keys, bearer tokens, passwords, and private certificates must never appear in flight recorder tapes, audit logs, error messages, or commit diffs.
3. **Execution Sandbox**: Shell commands executed by agents must run inside isolated sandboxes (macOS Seatbelt / Linux bubblewrap). Unconfined root execution is prohibited.
4. **Three-Tier Autonomy Gate**:
   - `Tier 1 (Safe)`: Read-only workspace analysis, model evaluation.
   - `Tier 2 (Governed)`: File writes, test executions within approved worktrees.
   - `Tier 3 (High Risk)`: External network egress, git commits/pushes, remote deployments (requires cryptographic human approval nonce).
5. **Merkle Audit Integrity**: Audit events form an append-only cryptographic hash chain. Any truncation or modification breaks verification.

---

## 7. DEFINITION OF DONE (DoD)

A task is **DONE** only when all nine criteria are met:
1. Requested behavior is fully implemented.
2. Acceptance criteria are demonstrably verified with reproducible evidence.
3. Automated unit/integration tests pass in the standard environment.
4. No high or critical security vulnerabilities or privacy regressions introduced.
5. All newly added public interfaces have docstrings and type annotations.
6. Documentation in `docs/` is updated to reflect changes.
7. Uncommitted files are tracked, clean, and formatted.
8. A complete handoff document is committed to `docs/agent-operations/`.
9. Status in `docs/agent-operations/ACTIVE_TASKS.md` is accurately updated.

---

## 8. REPOSITORY KNOWLEDGE MAP

- **Architecture**:
  - `docs/architecture/SYSTEM_OVERVIEW.md`: System topology, components, and data flow
  - `docs/architecture/HYBRID_AI_ARCHITECTURE.md`: Open-weight vs proprietary model tiers
  - `docs/architecture/MODEL_PROVIDER_CONTRACT.md`: Provider adapter & gateway interfaces
  - `docs/architecture/MODEL_COMPATIBILITY_MATRIX.md`: Tested provider/agent compatibility — VERIFIED vs IMPL vs GATED per cell
  - `docs/decisions/`: Architectural Decision Records (ADR-001 through ADR-0042)
- **Engineering Standards**:
  - `docs/engineering/ENGINEERING_STANDARDS.md`: Devin-inspired engineering standards
  - `docs/engineering/QUALITY_GATES.md`: CI/CD, pre-commit, and release quality gates
  - `docs/engineering/TESTING_STRATEGY.md`: Test pyramid, mock policies, and contract testing
  - `docs/engineering/SECURITY_STANDARDS.md`: Security invariants & sandbox requirements
  - `docs/engineering/DEVELOPMENT_WORKFLOW.md`: Branching, worktrees, and PR process
- **Product & Research**:
  - `docs/product/PRODUCT_STRATEGY.md`: Market positioning, hybrid cost advantage
  - `docs/product/ROADMAP.md`: Multi-phase execution roadmap
  - `docs/research/AI_RESEARCH_ROADMAP.md`: LoRA fine-tuning, speculative decoding, and evals
- **Agent Operations**:
  - `docs/agent-operations/ACTIVE_TASKS.md`: Live task board
  - `docs/agent-operations/TASK_TEMPLATE.md`: Specification template for new tasks
  - `docs/agent-operations/AGENT_HANDOFF.md`: Protocol & instructions for cross-agent switching
  - `docs/agent-operations/AGENT_COMPATIBILITY.md`: Platform feature matrix (Antigravity, Claude, Devin, gstack)

---

## 9. STUDIO CSS FRESHNESS

If you change classes in `core/studio/index.html` or `core/studio/assets/studio.js`,
rebuild the generated stylesheet and verify freshness:

```bash
make studio-css        # regenerate core/studio/assets/studio.css (committed)
make studio-css-check  # fails if the committed css is stale
```
