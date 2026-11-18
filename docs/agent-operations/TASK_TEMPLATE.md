# Task Specification Template

> **Location**: `docs/agent-operations/tasks/<TASK_ID>.md`  
> **Schema Version**: 1.0

---

```markdown
# TASK: <TASK_ID> — <TASK_TITLE>

## 1. METADATA
- **TASK ID**: KEEL-<CATEGORY>-<NUMBER>
- **CATEGORY**: [ARCH | CORE | MODELS | ORCHESTRATION | SECURITY | API | UI | TEST | RESEARCH]
- **CREATOR**: <Agent or Human Name>
- **ASSIGNED AGENT**: <Current Agent or Unassigned>
- **STATUS**: [QUEUED | IN_PROGRESS | BLOCKED | READY_FOR_REVIEW | COMPLETED]
- **TARGET BRANCH**: feature/<task-id>-<short-description>
- **BASE COMMIT**: <Commit SHA>

---

## 2. OBJECTIVE & MOTIVATION
<Clear, unambiguous description of the problem, motivation, and expected outcome.>

---

## 3. ACCEPTANCE CRITERIA
- [ ] Criterion 1: <Specific, falsifiable condition>
- [ ] Criterion 2: <Specific, falsifiable condition>
- [ ] Criterion 3: Automated tests written and passing in pytest
- [ ] Criterion 4: Zero security or privacy regressions
- [ ] Criterion 5: Documentation updated

---

## 4. AFFECTED FILES & COMPONENTS
- Primary Files:
  - `<path/to/file1>`
  - `<path/to/file2>`
- Test Files:
  - `tests/test_<feature>.py`
- Documentation:
  - `docs/...`

---

## 5. SECURITY & PRIVACY CONSIDERATIONS
- Privacy Fail-Closed verification required? [Yes / No]
- Credential handling / secret redaction involved? [Yes / No]
- Autonomy Tier Level: [Tier 1 Safe | Tier 2 Governed | Tier 3 High Risk]

---

## 6. VALIDATION & TEST PLAN
```bash
# Specific test command to verify completion:
pytest tests/test_<feature>.py -v
```

---

## 7. EXECUTION LOG & AGENT HANDOFF HISTORY
*(Appended sequentially as agents perform work on this task)*
```
