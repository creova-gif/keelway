# Personal Agent — First Three Workflows

These are the three real recurring workflows the Personal Agent must complete reliably in the first 90 days.

## Workflow 1: Engineering Brief from Pull Requests

**Name:** `engineering_brief`  
**Permission level:** Read  
**Description:** Review recent Kora Dev pull requests, identify issues, and produce a prioritized engineering brief.

### Trigger
User request:  
"Review the latest Kora Dev pull requests, identify failing tests, compare changes against KORA.md, and prepare a prioritized engineering brief."

### Steps
1. List open PRs in the target repository (read-only GitHub tool).
2. For each relevant PR, fetch summary, changed files, and CI status.
3. Retrieve relevant sections of KORA.md and any linked ADRs.
4. Generate a brief containing:
   - Summary of changes
   - Failing or risky tests
   - Alignment with KORA.md principles
   - Ranked risks
   - Recommended next actions
   - File citations
5. Present the brief for human review (no automatic actions).

### Success criteria
- Brief covers at least the top 3 open PRs or the user-specified ones.
- All claims are backed by citations to files or PR data.
- Completes without modifying any external system.
- User confirms it saves time vs. manual review.

### Tools required
- `github.list_prs`
- `github.get_pr`
- `github.get_file`
- `docs.search` (KORA.md / ADRs)

---

## Workflow 2: Research Paper / ADR Summary with Citations

**Name:** `research_summary`  
**Permission level:** Read  
**Description:** Summarize a research paper or internal ADR and relate it to current Kora work.

### Trigger
User request:  
"Summarize this paper/ADR and tell me how it applies to our agent orchestration or memory design."

### Steps
1. Ingest the document (PDF, Markdown, or URL — treated as untrusted).
2. Extract key claims, methods, and limitations.
3. Search existing Kora docs and ADRs for related decisions.
4. Produce a structured summary:
   - Core contribution
   - Relevance to Kora (specific components)
   - Potential risks or gaps
   - Suggested follow-up experiments or ADRs
   - Citations to both the source and internal docs
5. Store the summary in long-term memory with provenance (optional, user-approved).

### Success criteria
- Accurate extraction of the source material.
- Clear, actionable link to Kora architecture.
- Provenance recorded.
- No hallucinated citations.

### Tools required
- `docs.ingest`
- `docs.search`
- `memory.store` (draft only until approved)

---

## Workflow 3: Sandboxed Test Run + Failure Analysis

**Name:** `sandboxed_test_analysis`  
**Permission level:** Execute in sandbox  
**Description:** Run a specified test suite in a sandbox and produce a failure analysis.

### Trigger
User request:  
"Run the orchestration tests in a sandbox and explain any failures."

### Steps
1. Confirm the request and sandbox scope with the user (approval gate).
2. Spin up an isolated environment (container or restricted process).
3. Execute the requested tests.
4. Capture stdout, stderr, and exit codes.
5. Analyze failures:
   - Root cause hypothesis
   - Related code locations
   - Suggested fixes (draft only)
6. Return the analysis with full logs attached.
7. Destroy the sandbox.

### Success criteria
- Tests run only inside the sandbox.
- Analysis correctly identifies the failing tests and likely causes.
- No changes are made to the real repository or environment.
- User can reproduce the result from the provided logs.

### Tools required
- `sandbox.run_tests`
- `github.get_file` (read-only)
- `docs.search`

---

## Shared Requirements for All Three

- Must go through the Kora Agent Gateway with scoped permissions.
- Must produce an audit log entry for every tool call.
- Must cite sources.
- Must respect the four permission levels (none of these workflows modify external systems without a later explicit approval step).
- Evaluation tasks should be written for each workflow and run before declaring the workflow "reliable."

## Implementation Order (suggested)

1. Workflow 1 (read-only, high value, no sandbox)  
2. Workflow 2 (read-only + document handling)  
3. Workflow 3 (introduces sandbox + approval gate)
