# Live SSE Execution & P-10 Human Approval Gate

Users dispatch governed lifecycle AI agents or KFlow DAG workflows that stream ordered Server-Sent Events (`run.started` -> `step.tool_call` -> `step.completed` -> `p10.held`) into a live console, pause before side-effecting actions, and require an authenticated human with `p10:approve` permission (`owner`, `admin`, or `operator` — never `viewer`, `builder`, automated `agent:*` actors, or the same builder who initiated the run) to click approve or deny.

## Sub-features

- Dispatch a live streaming agent run from the **Agents** view (`Stream Live Execution`) or via `cli.py run`
- Observe live SSE events populate `[aria-label="Live execution SSE event log"]` and hold at `Held · P-10 Human Gate` (`[p10.held]`)
- Enforce RBAC role gating in UI (`viewer` / `builder` disables `Approve P-10 & Resume Stream` and `Deny & Abort Run`) and API (`403` on lateral role escalation or self-approval)
- Approve (`Approve P-10 & Resume Stream`) or deny (`Deny & Abort Run`) via trusted hardware-pipeline click and persist `p10_receipt` in SQLite WAL (`platform_execution_runs`)

## How to get to it (user POV)

1. **Agents view button:** Open `/app?token=<TOKEN>`, click `Agents` in `[aria-label="Unified platform views"]`, and click `Stream Live Execution` (launches `feature-coder` with `requiresP10: true`), or click `Inspect & Supervise <agent>` on any agent card and launch its stream.
2. **Automation view button:** Click `Automation` in `[aria-label="Unified platform views"]` and trigger a governed KFlow DAG stream.
3. **Sovereign CLI:** Run `python cli.py run --kind agent --target agent-coder --objective "Verify P-10 checkpoint" --json`.

## Driving it with control-keelway

Assume `STATE=/tmp/keelway-verify-p10` is launched and `EVIDENCE=/tmp/keelway-evidence-p10` is your persistent proof folder:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-p10
EVIDENCE=/tmp/keelway-evidence-p10

# 1. Navigate to Agents and start a live SSE run
$CTRL browser click --state-dir "$STATE" --role button --name "Agents"
$CTRL browser click --state-dir "$STATE" --role button --name "Stream Live Execution"
$CTRL browser wait-for --state-dir "$STATE" --text "Held · P-10 Human Gate"
$CTRL browser snapshot --state-dir "$STATE" --aria --out "$EVIDENCE/01-p10-held.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-p10-held.png"

# 2. Prove RBAC gating: switching to 'viewer' disables the P-10 approval button (exits 2)
$CTRL browser select --state-dir "$STATE" --label "Active RBAC role" --value "viewer"
$CTRL browser snapshot --state-dir "$STATE" --aria --out "$EVIDENCE/02-viewer-locked.aria.txt"

# 3. Restore 'owner' role and approve P-10 with a trusted mouse click
$CTRL browser select --state-dir "$STATE" --label "Active RBAC role" --value "owner"
$CTRL browser click --state-dir "$STATE" --role button --name "Approve P-10 & Resume Stream"
$CTRL browser wait-for --state-dir "$STATE" --text "p10.approved"
$CTRL browser snapshot --state-dir "$STATE" --aria --out "$EVIDENCE/03-p10-approved.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/03-p10-approved.png"

# 4. Cross-check CLI execution stream and SQLite WAL persistence
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/04-cli-run.json" -- \
  run --kind agent --target agent-reviewer --objective "Audit diff" --json
$CTRL db-query --state-dir "$STATE" --out "$EVIDENCE/05-db-runs.json" \
  --sql "SELECT run_id, workspace_id, status, payload_json FROM platform_execution_runs ORDER BY rowid ASC"
```

Observable end state that proves success:

- `01-p10-held.aria.txt` contains `region "Live streaming execution console"`, `log "Live execution SSE event log"`, `p10.held`, and enabled button `"Approve P-10 & Resume Stream"`.
- `02-viewer-locked.aria.txt` marks `"Approve P-10 & Resume Stream" [disabled]` and `"Deny & Abort Run" [disabled]`.
- `03-p10-approved.aria.txt` shows `p10.approved`, `run.completed`, and status `completed`.
- `05-db-runs.json` shows the browser-initiated run at `status = "completed"` with `"decision":"approve"` inside `payload_json`, alongside the CLI-initiated run at `status = "awaiting_p10"`.

## Gotchas

- `Approve P-10 & Resume Stream` and `Deny & Abort Run` render with `clickOnly` (`data-click-only="true"`). Synthetic JS `element.click()` events have `event.isTrusted === false` and are silently ignored by `Button.tsx`; always use `control-keelway browser click` (CDP `Input.dispatchMouseEvent`).
- If a run is started by a `builder` actor (`initiated_by_role = "builder"`), that same `builder` actor cannot self-approve (`disallow_self_approval=True`) and cannot pass `X-Keelway-Role: operator` to laterally escalate permissions (`403 Forbidden`). A distinct `owner`, `admin`, or `operator` member must approve.
