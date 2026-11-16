# Multi-Workspace Switching, RBAC & No-Code Blueprint

Users create and switch isolated project workspaces (`default`, `hipaa-intake`, or custom slugs) in the unified top bar, toggle between `Builder` and `Guided Non-Coder` personas, and compile natural-language app ideas in **No-Code Builder** into synchronized Product PRDs, Project Manager sprint issues, Automation DAGs, and Agent squad assignments.

## Sub-features

- Create a new isolated workspace via `+ New` (`[aria-label="New workspace"]`) in the top workspace bar or via `cli.py workspace create`
- Switch active workspace via `[aria-label="Active workspace switcher"]` and verify workspace-scoped secrets/runs isolate cleanly across workspaces
- Toggle `[aria-label="Experience persona"]` between `Builder` and `Guided Non-Coder`
- Generate a cross-view project blueprint in **No-Code Builder** (`Generate Project Blueprint`) and jump into synchronized `Product`, `Project Manager`, `Automation`, and `Agents` views

## How to get to it (user POV)

1. **Top workspace bar (persistent across all 10 views):** `[aria-label="Unified workspace bar"]` at the top of `/app` exposes `[aria-label="Active workspace switcher"]`, `[aria-label="New workspace"]`, `[aria-label="Active RBAC role"]`, and `[aria-label="Experience persona"]`.
2. **No-Code Builder view:** Click `No-Code Builder` in `[aria-label="Unified platform views"]` (or switch persona to `Guided Non-Coder`).
3. **Sovereign CLI:** Run `python cli.py workspace list|create|rbac-check --json`.

## Driving it with control-keelway

Assume `STATE=/tmp/keelway-verify-ws` is launched and `EVIDENCE=/tmp/keelway-evidence-ws` is your persistent proof folder:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-ws
EVIDENCE=/tmp/keelway-evidence-ws

# 1. Create a new isolated workspace from the top workspace bar
$CTRL browser click --state-dir "$STATE" --role button --name "New workspace"
$CTRL browser fill  --state-dir "$STATE" --label "New workspace name" --value "FinOps Audit Desk"
$CTRL browser click --state-dir "$STATE" --role button --name "Create Workspace"
$CTRL browser wait-for --state-dir "$STATE" --text "FinOps Audit Desk"

# 2. Switch to Guided Non-Coder persona and open No-Code Builder
$CTRL browser click --state-dir "$STATE" --role button --name "Guided Non-Coder"
$CTRL browser click --state-dir "$STATE" --role button --name "No-Code Builder"
$CTRL browser fill  --state-dir "$STATE" --label "Describe your app or workflow idea" \
  --value "Quarterly vendor SOC2 evidence collector with CFO P-10 approval before filing"
$CTRL browser click --state-dir "$STATE" --role button --name "Generate Project Blueprint"
$CTRL browser wait-for --state-dir "$STATE" --text "Committed to Shared Workspace"

# 3. Capture UI proof and verify workspace persistence in CLI + SQLite WAL
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-nocode-blueprint.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-nocode-blueprint.png" --full-page
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/02-cli-workspaces.json" -- workspace list --json
$CTRL db-query --state-dir "$STATE" --out "$EVIDENCE/03-sqlite-workspaces.json" \
  --sql "SELECT id, name, branch, isolation_mode FROM platform_workspaces_dir ORDER BY created_at ASC"
```

Observable end state that proves success:

- `01-nocode-blueprint.aria.txt` shows `button "Guided Non-Coder" [pressed]`, `region "Generated project blueprint"`, `Synced to Product, PM, Automation & Agents`, and `region "Interactive live app preview"`.
- `02-cli-workspaces.json` and `03-sqlite-workspaces.json` include the newly created `finops-audit-desk` workspace (`name = "FinOps Audit Desk"`) alongside the seeded `default` and `hipaa-intake` rows in `platform_workspaces_dir`.

## Gotchas

- Creating a workspace via `+ New` requires `workspace:manage` permission (`owner` or `admin`). If `[aria-label="Active RBAC role"]` is set to `builder`, `operator`, or `viewer`, the `+ New` button is disabled (`aria-disabled="true"`).
- Blueprint compilation in `NoCodeBuilderView` calls `POST /v1/platform/blueprints/compile` (persisted via `PlatformPersistence` in `platform.db`) while workspace directory rows live in `platform_runtime.db` (`platform_workspaces_dir`). Both databases live inside `$STATE_DIR/home/.keelway/`.
