# Keelway — Development & Multi-Agent Git Workflow

> **Purpose**: Eliminating merge collisions, lost context, and unreviewed changes across human and AI engineers.

---

## 1. Branch Strategy & Worktree Isolation

Multiple AI tools (Antigravity, Claude Code, Devin, gstack) and human engineers frequently collaborate on Keelway. Concurrent editing in the same working tree causes race conditions and corrupted states.

### 1.1 Branch Naming Conventions
All work must occur in dedicated task branches branched off `main`:
- `feature/<task-id>-<short-description>` (e.g. `feature/KEEL-HYBRID-001-unified-model-gateway`)
- `fix/<task-id>-<short-description>` (e.g. `fix/KEEL-SEC-014-sandbox-leak`)
- `refactor/<task-id>-<short-description>`
- `research/<task-id>-<short-description>`

### 1.2 Git Worktree Isolation for Parallel Agents
When multiple agents run concurrently on the same machine, use Git worktrees to maintain separate workspaces:

```bash
# 1. Create a dedicated isolated worktree for a task
git worktree add ../keelway-worktrees/KEEL-HYBRID-001 -b feature/KEEL-HYBRID-001-unified-model-gateway

# 2. Navigate and perform work inside the worktree
cd ../keelway-worktrees/KEEL-HYBRID-001

# 3. Clean up worktree after merge
git worktree remove ../keelway-worktrees/KEEL-HYBRID-001
```

---

## 2. Universal Agent Execution Lifecycle

Before touching code, every agent must follow this protocol:

### Pre-Task Checklist
1. **Fetch Latest State**: Run `git fetch origin` (if remote is reachable) and verify your branch is aligned.
2. **Inspect Working Tree**: Run `git status`. If uncommitted changes exist, determine if another agent's work is active.
3. **Locate Active Task**: Read `docs/agent-operations/ACTIVE_TASKS.md` and the task document in `docs/agent-operations/tasks/`.
4. **Read Architecture & Decisions**: Consult `docs/architecture/` and recent records in `docs/decisions/`.

### Implementation & Verification
1. Keep diffs focused, surgical, and minimal.
2. Maintain backward compatibility.
3. Run tests frequently in the local virtual environment.
4. If an architectural conflict arises between two agent designs, compare both against `docs/architecture/HYBRID_AI_ARCHITECTURE.md` and acceptance criteria. Never blindly choose whichever was created last.

### Pre-Handoff Checklist
1. All newly added unit and integration tests must pass.
2. Verify zero unhandled linting or syntax errors (`python3 -m py_compile`).
3. Create a clear, atomic commit with Conventional Commit messaging:
   ```bash
   git commit -m "feat(models): add unified hybrid model registry and openai adapter"
   ```
4. Produce a structured handoff document in `docs/agent-operations/tasks/<TASK_ID>.md`.
5. Update `docs/agent-operations/ACTIVE_TASKS.md`.

---

## 3. Pull Request & Merge Policy

1. Pull requests require passing CI (`test` and `release-live-verification`).
2. Must include reproducible test commands and output evidence.
3. Requires human approval for Autonomy Tier 3 changes (network egress, secret modifications, deployment).
4. Merge using Squash and Merge to preserve linear git history on `main`.
