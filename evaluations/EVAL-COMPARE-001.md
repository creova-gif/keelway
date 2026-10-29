# Evaluation Task: Claude vs Open-Weight Model

## Task ID: EVAL-COMPARE-001
**Category:** coding + reasoning  
**Description:** Compare Anthropic Claude and a local/open-weight model on a realistic Kora engineering brief task. Measure correctness, citation quality, latency, and cost.

### Input
```
You are a Kora engineering assistant.

Review the following pull request summary and produce a prioritized engineering brief.

PR: "Add task state machine to agent backend"
- Changes: new TaskState enum, transition table, retry logic, human approval gate
- Files touched: core/orchestration/state.py, core/orchestration/engine.py, tests/test_state.py
- Failing test: test_retry_on_transient_error currently times out
- Related: KORA.md says "Prefer explicit state over opaque agent loops"

Produce:
1. Summary of the change (2–3 sentences)
2. Risks (ranked)
3. Recommended next actions (ordered)
4. Citations to the files mentioned
```

### Expected Behavior
- Correctly identifies the state-machine addition and the failing test.
- Mentions the KORA.md principle.
- Ranks risks (e.g., missing recovery path, approval bypass, test flakiness).
- Provides ordered next actions (fix test, add recovery test, document transitions).
- Cites the files by name.
- Does not invent file contents that were not provided.

### Success Criteria
- [ ] All four sections present and accurate
- [ ] File citations present
- [ ] No hallucinated file contents
- [ ] Completes without tool calls (this is a pure generation task for comparison)

### Comparison Protocol
Run the identical prompt against:

1. **Claude** (e.g. `claude-sonnet-4-20250514` via Anthropic adapter)
2. **Open-weight model** (e.g. `qwen2.5:7b` or `llama3.1:8b` via LocalAdapter)

Record for each run:

| Metric              | Claude | Open-weight | Notes |
|---------------------|--------|-------------|-------|
| Correctness (0–5)   |        |             |       |
| Citation quality    |        |             |       |
| Latency (ms)        |        |             |       |
| Cost (USD)          |        |             |       |
| Token usage         |        |             |       |
| Pass / Fail         |        |             |       |

### Scoring Rubric (Correctness)
- 5: All sections accurate, risks well ranked, actions practical
- 3: Main points correct, minor omissions
- 1: Misses key elements or invents details
- 0: Unusable

### Notes
- Use the same system prompt and temperature (0.2) for both.
- Run each model 3 times and average scores to reduce variance.
- Store raw outputs in `evaluations/results/EVAL-COMPARE-001/`.
- This task also validates that the gateway can route to both providers without application changes.
