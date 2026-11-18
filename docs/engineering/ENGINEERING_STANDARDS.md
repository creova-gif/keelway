# Keelway — Engineering Standards

> **Discipline Benchmark**: Inspired by rigorous autonomous software engineering.  
> **Applies to**: All AI Agents (Antigravity, Claude, Devin, Cursor, Codex, gstack) and Human Contributors.

---

## 1. Core Principles of Autonomous Engineering

We hold AI agents to the quality discipline of a Senior Staff Software Engineer and AI Systems Architect. Producing code that merely looks plausible is unacceptable; production-grade reliability, testability, and security are mandatory.

Every engineer and agent must adhere to the **14 Core Disciplines**:

1. **Understand Before Modifying**: Inspect existing architecture, imports, and tests before writing a single line of code.
2. **Translate to Explicit Acceptance Criteria**: Every task must have unambiguous, falsifiable conditions for satisfaction.
3. **Map Blast Radius**: Identify directly and transitively affected files and consumers before starting implementation.
4. **Proportionate Planning**: Keep plans lightweight for atomic fixes; use structured ADRs for architectural mutations.
5. **Assess Risks**: Explicitly evaluate compatibility, performance, security invariants, and regression risk.
6. **Implement Smallest Coherent Solution**: Avoid speculative abstractions, giant refactors, or touching unrelated systems.
7. **Write Meaningful Automated Tests**: Create unit, integration, and contract tests exercising both happy and error paths.
8. **Run Real Validation Commands**: Execute real test suites and inspect actual terminal outputs.
9. **Critical Self-Review**: Review your own diffs against security standards and design system tokens before declaring completion.
10. **Document Decisions in Git**: Record non-obvious design trade-offs in version-controlled files under `docs/`.
11. **Produce Reproducible Evidence**: Record exact test execution commands, runtimes, and pass/fail tallies.
12. **Prepare Reviewable Pull Requests**: Write descriptive PR summaries detailing motivation, risks, and verification proof.
13. **Distinguish Statuses**: Clearly separate `Implemented`, `Locally Verified`, `CI Verified`, `Reviewed`, `Merged`, and `Deployed`.
14. **Deliver Structured Handoffs**: Always leave an actionable state record for the next agent or human reviewer.

---

## 2. Explicitly Prohibited Behaviors

The following practices violate Keelway engineering discipline:

| Prohibited Action | Why It Is Unacceptable | Correct Engineering Alternative |
|---|---|---|
| **Fabricated Test Results** | Falsely claiming tests passed without executing them destroys engineering trust. | Run pytest/ruff in the active virtualenv and paste real outputs into the handoff. |
| **Invented Repository Findings** | Hallucinating files, functions, or package dependencies that do not exist. | Inspect the filesystem using `git status`, `ls`, `grep`, or file reading tools first. |
| **Unnecessary Rewrites** | Rewriting functional working modules because of stylistic preference. | Make surgical, focused, and backward-compatible edits matching existing patterns. |
| **Undocumented Architecture Changes** | Modifying APIs, schemas, or routing logic without updating documentation. | Author or update ADRs in `docs/decisions/` and schemas in `docs/architecture/`. |
| **Silent Removal of Functionality** | Deleting existing features or tests to make a pipeline green. | Fix the underlying failure or document an explicit deprecation plan. |
| **Hardcoded Credentials** | Putting API keys, passwords, or tokens in source code or tests. | Inject secrets through environment variables or secure vault mocks. |
| **Unexplained Dependencies** | Adding heavy external libraries to `pyproject.toml` or `package.json` for trivial tasks. | Leverage standard library and existing dependencies. Justify any new package addition. |
| **Duplicate Implementations** | Creating new helper functions or adapters when equivalent utilities exist. | Search the codebase (`core/`, `tests/`) and reuse canonical helpers. |
| **Claiming Done Without Criteria Met** | Marking a task complete when tests fail or acceptance criteria remain unverified. | Mark status as `IN_PROGRESS` or `BLOCKED` with detailed next steps. |

---

## 3. Code Quality & Idiomatic Conventions

- **Language Standard**: Modern Python (3.11+), utilizing typing extensions, `from __future__ import annotations`, and strict type hinting.
- **Data Modeling**: Pydantic v2 `BaseModel` and `Field` with strict validation, descriptive metadata, and schema exportability.
- **Asynchronous IO**: Use `async`/`await` for all network, filesystem, and subprocess operations via `httpx.AsyncClient` and `anyio`. Avoid blocking calls in event loops.
- **Error Disclosure**: Never leak internal exception traces, database details, or raw stack traces to public API endpoints. Always filter through `core.security.error_disclosure`.
- **Formatting & Style**: Comply with Ruff / Black formatting guidelines (line length 100).
