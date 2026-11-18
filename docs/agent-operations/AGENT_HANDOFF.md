# Keelway — Cross-Agent Handoff Protocol

> **Purpose**: Seamless, lossless switching between Google Antigravity, Claude Code, Devin, Cursor, and gstack.  
> **Core Rule**: The next agent must verify git branch, HEAD, file modifications, and test results before continuing. Never assume past claims without verification.

---

## 1. The Handoff Lifecycle

When an AI engineering tool completes a session, runs out of context budget, or delegates work to another agent, it must execute this procedure:

```
[ Active Agent Finishing Session ]
                |
  1. Run validation test suite
  2. Commit changes with clear git message
  3. Append structured handoff to docs/agent-operations/tasks/<TASK_ID>.md
  4. Update docs/agent-operations/ACTIVE_TASKS.md
                |
                v
[ Next Agent Resuming Task ]
                |
  1. Read AGENTS.md & docs/agent-operations/ACTIVE_TASKS.md
  2. Read docs/agent-operations/tasks/<TASK_ID>.md
  3. Run `git status` and verify HEAD commit matches handoff
  4. Run reported test command to independently verify baseline
  5. Identify the next atomic engineering action
  6. Proceed with implementation
```

---

## 2. Standard Handoff Record Schema

Every handoff entry appended to a task file must conform to this exact markdown format:

```markdown
### AGENT HANDOFF RECORD
- **TASK ID**: KEEL-<CATEGORY>-<NUMBER>
- **TASK TITLE**: <Title>
- **CURRENT STATUS**: [IN_PROGRESS | BLOCKED | READY_FOR_REVIEW | COMPLETED]
- **LAST AGENT**: [Antigravity | Claude Code | Devin | Cursor | gstack]
- **DATE**: YYYY-MM-DD HH:MM UTC
- **BRANCH**: <branch-name>
- **BASE COMMIT**: <base-commit-sha>
- **HEAD COMMIT**: <head-commit-sha>

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Implemented core model registry and adapters
- [x] Integrated /v1/chat/completions route
- [ ] Implement rate-limit backoff policy

#### WORK COMPLETED & FILES MODIFIED
- `core/models/registry.py`: Defined ModelMetadata, ModelCategory, and canonical catalog
- `core/models/adapters/open_weight.py`: Implemented Ollama & OpenAI-compatible local adapter
- `core/api/routes.py`: Added GET /v1/models and POST /v1/chat/completions
- `tests/test_hybrid_routing_and_api.py`: Added 7 integration tests

#### DECISIONS MADE
- Kept deployment_type and deployment keys aliased for backward compatibility with SDK clients.
- Enforced HTTP 403 AirGapViolationError when private requests target cloud providers.

#### TESTS EXECUTED & EVIDENCE
```bash
pytest tests/test_hybrid_model_registry.py tests/test_hybrid_adapters.py tests/test_hybrid_routing_and_api.py -v
```
**Result**: `16 passed in 0.38s` (Zero failures, zero warnings).

#### OPEN ISSUES & BLOCKERS
- None currently blocking. Live credentials needed only for release verification stage.

#### KNOWN RISKS
- Ollama daemon must be running locally on port 11434 for live local inference; tests use mock transports.

#### NEXT RECOMMENDED ACTION
- Run full regression suite or submit pull request for task KEEL-HYBRID-001.

#### RECOMMENDED VALIDATION
- Run `bash scripts/verify_engineering_gates.sh` to ensure all quality gates pass.
```

---

## 3. Rules for the Resuming Agent

1. **Do Not Trust Blindly**: Run `git status`, `git log -1`, and the reported test command before modifying code.
2. **Do Not Reimplement Finished Work**: Inspect the files listed in `FILES MODIFIED`. Do not restart or overwrite working implementations.
3. **Do Not Alter Unrelated Subsystems**: Limit edits strictly to the scope of the current task.
4. **Preserve Prior Handoff Records**: Append your handoff to the task file; do not delete historical handoffs.
