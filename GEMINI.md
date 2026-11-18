# Keelway — Google Antigravity Operating Guide

> **Entry Point for Google Antigravity & Gemini Agents**  
> Canonical Engineering Contract: [AGENTS.md](AGENTS.md)  
> All architecture, security, and testing rules are defined in [AGENTS.md](AGENTS.md).

---

## 1. Operating Discipline

1. **Canonical Contract**: Adhere strictly to the Universal Task Execution Protocol (Stages A–F) in [AGENTS.md](AGENTS.md).
2. **Worktree Isolation**: Antigravity agents working on multi-step tasks must work inside designated task branches or git worktrees.
3. **No Phantom Tools**: Never fabricate tool outputs or skip verification commands. Run pytest and verify actual terminal output.

---

## 2. Key Commands for Antigravity

```bash
# Targeted test execution
pytest tests/test_<module>.py -v

# Hybrid AI verification
pytest tests/test_hybrid_model_registry.py tests/test_hybrid_adapters.py tests/test_hybrid_routing_and_api.py -v

# Verification script
bash scripts/verify_engineering_gates.sh
```

---

## 3. Session Delivery & Handoff

At the conclusion of each task:
1. Verify all modified tests pass without regressions.
2. Produce a structured handoff conforming to Section 4 of [AGENTS.md](AGENTS.md).
3. Record the handoff in `docs/agent-operations/tasks/<TASK_ID>.md` and update `docs/agent-operations/ACTIVE_TASKS.md`.
