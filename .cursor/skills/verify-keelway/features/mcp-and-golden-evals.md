# MCP Tool Control Plane & 16-Probe Golden Evaluation Suite

Users register SSRF- and shell-guarded Model Context Protocol (`2025-06-18`) servers, test-invoke built-in workspace/governance/vault MCP tools with automatic secret redaction in **Agents**, and run the 16-probe Golden Benchmark & Adversarial Red-Team Suite (`workspace_ast`, `governance_p10`, `security_redteam`, `routing_pricing`) in **Security** or via `cli.py mcp` / `cli.py eval-suite`.

## Sub-features

- Inspect built-in `keelway-core-mcp` (`5` read-only workspace/governance/vault tools) and register scoped `sse` / `stdio` MCP servers (`[aria-label="Model Context Protocol server and tool inspector"]`)
- Block SSRF metadata endpoints (`http://169.254.169.254/...`) on `sse` servers and shell metacharacters (`; | & $()`) on `stdio` servers
- Invoke live MCP tools (`Invoke MCP Tool` / `cli.py mcp call`) with automatic credential scrubbing and SHA-256 execution receipts
- Run the 16-probe Golden Benchmark & Adversarial Red-Team Suite (`Run 16-Probe Golden Suite` / `cli.py eval-suite --json`) and persist pass-rate scorecards in SQLite WAL (`platform_eval_runs`)

## How to get to it (user POV)

1. **Agents view (`MCP Inspector`):** Open `/app?token=<TOKEN>`, click `Agents` in `[aria-label="Unified platform views"]`, and scroll to `[aria-label="Model Context Protocol server and tool inspector"]`.
2. **Security view (`Golden Eval Scorecard`):** Click `Security` in `[aria-label="Unified platform views"]` and locate `[aria-label="Golden benchmark and adversarial red-team suite"]`.
3. **Sovereign CLI:** Run `python cli.py mcp servers|tools|call --json` and `python cli.py eval-suite --category all --json`.

## Driving it with control-keelway

Assume `STATE=/tmp/keelway-verify-phase7` is launched and `EVIDENCE=/tmp/keelway-evidence-phase7` is your persistent proof folder:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-phase7
EVIDENCE=/tmp/keelway-evidence-phase7

# 1. Register a loopback SSE MCP server and invoke workspace.list_files in Agents view
$CTRL browser click  --state-dir "$STATE" --role button --name "Agents"
$CTRL browser fill   --state-dir "$STATE" --label "MCP server name" --value "Local Docs MCP"
$CTRL browser select --state-dir "$STATE" --label "MCP transport" --value "sse"
$CTRL browser fill   --state-dir "$STATE" --label "MCP endpoint or command" --value "http://127.0.0.1:8910/sse"
$CTRL browser click  --state-dir "$STATE" --role button --name "Register MCP Server"
$CTRL browser wait-for --state-dir "$STATE" --text "Local Docs MCP"
$CTRL browser click  --state-dir "$STATE" --role button --name "Invoke MCP Tool"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-agents-mcp-inspector.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-agents-mcp-inspector.png" --full-page

# 2. Run the 16-probe Golden Benchmark & Red-Team Suite in Security view
$CTRL browser click    --state-dir "$STATE" --role button --name "Security"
$CTRL browser click    --state-dir "$STATE" --role button --name "Run 16-Probe Golden Suite"
$CTRL browser wait-for --state-dir "$STATE" --text "16/16"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/02-security-golden-evals.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/02-security-golden-evals.png" --full-page

# 3. Cross-check CLI parity + SQLite WAL persistence
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/03-cli-mcp-servers.json" -- mcp servers --json
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/04-cli-eval-suite.json" -- eval-suite --category all --json
$CTRL db-query --state-dir "$STATE" --out "$EVIDENCE/05-sqlite-mcp-evals.json" \
  --sql "SELECT eval_run_id, workspace_id, category, created_at FROM platform_eval_runs ORDER BY rowid DESC LIMIT 5"
```

Observable end state that proves success:

- `01-agents-mcp-inspector.aria.txt` lists both `keelway-core-mcp` and `Local Docs MCP` plus `region "MCP tool execution result"`.
- `02-security-golden-evals.aria.txt` shows `16/16` (`100%`) across `workspace_ast`, `governance_p10`, `security_redteam`, and `routing_pricing`.
- `03-cli-mcp-servers.json` confirms the browser-registered MCP server is visible to `cli.py mcp servers --json` via SQLite WAL (`platform_mcp_servers`).
- `05-sqlite-mcp-evals.json` shows both the browser-triggered and CLI-triggered `eval-...` runs persisted in `platform_eval_runs`.

## Gotchas

- Under RBAC role `viewer`, `Register MCP Server`, `Invoke MCP Tool`, and `Run 16-Probe Golden Suite` are disabled (`aria-disabled="true"`) and return `403` on `/v1/platform/*`.
- Registering or deleting MCP servers requires `webhooks:manage` (`owner` or `admin`), and the built-in `keelway-core-mcp` server cannot be deleted (`400 Bad Request`).
