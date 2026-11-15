# Flight-Tape Time-Travel Debugger, OTel GenAI Trace Wedge & LangGraph AST Migrator

Users ingest OpenTelemetry GenAI / external agent traces into local SQLite WAL with automatic DLP secret scrubbing, replay deterministic counterfactual forks (reusing cached upstream steps at \$0 cost), promote traces into repeatable Golden Eval dataset cases in **Agents**, and convert legacy `StateGraph` / LangChain code into bounded KFlow + P-10 blueprints in **Automation** or via `cli.py traces|trace-eval|migrate-langgraph`.

## Sub-features

- Ingest standard OTLP `resourceSpans` or flat `gen_ai.*` spans (`Ingest OTel GenAI Trace`) into `platform_flight_tapes` & `platform_flight_steps` with pre-storage DLP scrubbing (`[REDACTED_SECRET]`)
- Rewind to any step index, swap model/prompt (e.g., `gpt-4o` -> local `keelway-core:7b`), and replay counterfactual forks (`Replay Counterfactual Fork`) reusing cached upstream steps (`cached_steps_reused > 0`, negative `cost_delta_usd`)
- Promote any trace into `platform_eval_dataset_cases` in 1 click (`Promote Trace to Golden Eval`)
- Parse Python/TypeScript `StateGraph` code statically (`Convert LangGraph to KFlow`) without `eval`/`exec`, extracting bounded cycle policies (`max_iterations`), `interrupt()` -> `p10_human_gate` nodes, and legacy `LLMChain`/`AgentExecutor` deprecation warnings

## How to get to it (user POV)

1. **Agents view (`Flight-Tape Time-Travel Debugger`):** Open `/app?token=<TOKEN>`, click `Agents` in `[aria-label="Unified platform views"]`, and locate `[aria-label="Flight-tape time-travel debugger and OTel trace evaluator"]`.
2. **Automation view (`LangGraph AST Migrator`):** Click `Automation` in `[aria-label="Unified platform views"]` and locate `[aria-label="LangGraph to KFlow static AST migrator"]`.
3. **Sovereign CLI:** Run `python cli.py traces ingest|list|replay --json`, `python cli.py trace-eval promote|list --json`, and `python cli.py migrate-langgraph --code "..." --json`.

## Driving it with control-keelway

Assume `STATE=/tmp/keelway-verify-phase11` is launched and `EVIDENCE=/tmp/keelway-evidence-phase11` is your persistent proof folder:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-phase11
EVIDENCE=/tmp/keelway-evidence-phase11

# 1. Ingest OTel GenAI trace, replay counterfactual fork & promote to Golden Eval in Agents view
$CTRL browser click    --state-dir "$STATE" --role button --name "Agents"
$CTRL browser click    --state-dir "$STATE" --role button --name "Ingest OTel GenAI Trace"
$CTRL browser click    --state-dir "$STATE" --role button --name "Replay Counterfactual Fork"
$CTRL browser wait-for --state-dir "$STATE" --text "fork-"
$CTRL browser click    --state-dir "$STATE" --role button --name "Promote Trace to Golden Eval"
$CTRL browser wait-for --state-dir "$STATE" --text "evalcase-"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-agents-flight-tape-debugger.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-agents-flight-tape-debugger.png" --full-page

# 2. Convert cyclic StateGraph with interrupt() + LLMChain into KFlow + P-10 in Automation view
$CTRL browser click    --state-dir "$STATE" --role button --name "Automation"
$CTRL browser click    --state-dir "$STATE" --role button --name "Convert LangGraph to KFlow"
$CTRL browser wait-for --state-dir "$STATE" --text "max_iterations"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/02-automation-langgraph-migrator.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/02-automation-langgraph-migrator.png" --full-page

# 3. Cross-check CLI parity + SQLite WAL persistence
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/03-cli-traces-list.json" -- traces list --json
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/04-cli-eval-dataset.json" -- trace-eval list --json
$CTRL db-query --state-dir "$STATE" --out "$EVIDENCE/05-sqlite-flight-tapes.json" \
  --sql "SELECT trace_id, parent_trace_id, cached_steps_reused, cost_delta_usd, tape_sha256 FROM platform_flight_tapes ORDER BY created_at DESC LIMIT 5"
```

## Gotchas

- Raw API credentials (`sk-...`, `ghp_...`, `AKIA...`) inside ingested spans are scrubbed to `[REDACTED_SECRET]` prior to SQLite WAL writes (`dlp_redactions > 0`).
- `viewer` RBAC role can inspect tapes and eval cases (`200`), while ingest, replay, promote, and migrate mutations require `agents:dispatch` (`403` for `viewer`).
