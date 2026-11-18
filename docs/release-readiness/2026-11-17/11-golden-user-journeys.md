# Golden Journeys — Status (updated 2026-11-17 abuse run)

## GJ-1 Coding slice
install WORKING_E2E (macOS) · auth WORKING_E2E (401/403 matrix) · workspace WORKING_E2E (list/activate live) · files WORKING_E2E (tree 200, traversal blocked) · index/search WORKING_COMPONENT (/v1/index/search + repomap exist; journey-level not run) · task create WORKING_COMPONENT (runner enqueue verified) · agent plan WORKING_E2E (team plan) · approval WORKING_COMPONENT (explicit boolean, quorum rules) · isolated worktree MISSING (no worktree route) · agent edit UNVERIFIED · tests WORKING_COMPONENT (verifier node ran pytest) · diff WORKING_COMPONENT (/v1/git/diff, /v1/studio/diff) · checkpoint/rollback MISSING (no route) · commit WORKING_COMPONENT (/v1/git/commit) · PR proposal WORKING_COMPONENT (/v1/git/pr/proposal; real PR creation unverified) · CI status MISSING · evidence WORKING_COMPONENT (sealed tapes)

Verdict: PARTIAL — 3 hard gaps for Gate 2: no isolated worktree, no checkpoint/rollback, no CI-status surface. Composed run still not executed clean-env.

## GJ-2 Agent path — unchanged: AgentSpec versioning MISSING, SDK adapters MISSING.
