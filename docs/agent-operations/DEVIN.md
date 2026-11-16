# Keelway — Devin Operating Guide

> **Entry Point for Devin**  
> Canonical Engineering Contract: [AGENTS.md](../../AGENTS.md)

---

## 1. Quick Start for Devin

1. Read [AGENTS.md](../../AGENTS.md) for non-negotiable architecture and security invariants.
2. Check [docs/agent-operations/ACTIVE_TASKS.md](ACTIVE_TASKS.md) for task assignments.
3. Review your specific task file in `docs/agent-operations/tasks/<TASK_ID>.md`.
4. Always operate within an isolated task branch.

---

## 2. Test Execution Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Execute hybrid model tests
pytest tests/test_hybrid_model_registry.py tests/test_hybrid_adapters.py tests/test_hybrid_routing_and_api.py -v

# Run full project test suite
pytest tests/ -v
```

---

## 3. Required Handoff Protocol

When pausing or completing a task, append your handoff record to `docs/agent-operations/tasks/<TASK_ID>.md` using the schema defined in [AGENT_HANDOFF.md](AGENT_HANDOFF.md) and update [ACTIVE_TASKS.md](ACTIVE_TASKS.md).
