# Keelway — Claude Code Operating Guide

> **Entry Point for Claude Code**  
> Canonical Engineering Contract: [AGENTS.md](AGENTS.md)  
> All architecture, security, and testing rules are defined in [AGENTS.md](AGENTS.md).

---

## 1. Fast Orientation

1. **Read Canonical Rules**: Always inspect [AGENTS.md](AGENTS.md) before starting any task.
2. **Check Active Tasks**: Review [docs/agent-operations/ACTIVE_TASKS.md](docs/agent-operations/ACTIVE_TASKS.md) to locate your assigned work.
3. **Verify Git State**: Run `git status` and `git branch` to ensure you are on the correct task branch.

---

## 2. Environment & Validation Commands

Keelway runs Python 3.11+ with Pydantic v2 and FastAPI.

```bash
# Run pytest with virtualenv
pytest tests/test_<feature>.py -v

# Run entire hybrid AI test suite
pytest tests/test_hybrid_model_registry.py tests/test_hybrid_adapters.py tests/test_hybrid_routing_and_api.py -v

# Validate syntax
python3 -m py_compile core/api/routes.py core/models/*.py
```

---

## 3. gstack Integration (When Available)

If gstack is installed on your host machine, utilize structured review commands:
- `/office-hours`: Product framing and edge-case alignment
- `/plan-eng-review`: Architecture and fail-closed validation
- `/review`: Pre-commit engineering review
- `/qa`: End-to-end functional and regression testing
- `/ship`: Release preparation and PR verification

*Note*: If gstack is not installed, follow repository-native review gates in [docs/engineering/QUALITY_GATES.md](docs/engineering/QUALITY_GATES.md). Do not block work if gstack is absent.

---

## 4. Handoff Requirement

Before completing your session, you **must**:
1. Commit your verified changes to your task branch.
2. Update the task handoff in `docs/agent-operations/tasks/<TASK_ID>.md`.
3. Update [docs/agent-operations/ACTIVE_TASKS.md](docs/agent-operations/ACTIVE_TASKS.md).
