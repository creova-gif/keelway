---
name: verify-keelway
description: "Drive and verify the real Keelway Unified 11-View Dev App (/app), REST/SSE API (/v1/*), Sovereign CLI (cli.py), and SQLite WAL runtime in an isolated local stack. Use whenever proving UI, P-10 human gate, RBAC, AES-256-GCM vault, webhook, pricing simulator, or CLI behavior in keelway/."
---

# Verify Keelway (`verify-keelway`)

Keelway's primary interactive surface is the Unified 11-View Sovereign Dev App served by FastAPI (`core.main:app`) at `http://127.0.0.1:<PORT>/app?token=<KEELWAY_API_TOKEN>`, backed by the REST + SSE API (`/v1/*`), the Sovereign CLI (`python cli.py ...`), and SQLite WAL (`platform_runtime.db`).

Check [`features/README.md`](features/README.md) first to locate the user journey and observable end-state assertions for the feature under test.

All commands below run from the Keelway repository root (`cd keelway`). Set two explicit paths per verification run:

- `STATE_DIR`: scratch runtime directory (for example `/tmp/keelway-verify-run1`) destroyed by `cleanup`.
- `EVIDENCE_DIR`: persistent proof output directory **outside** `STATE_DIR` (for example `/tmp/keelway-evidence-run1` or your session artifact folder) that survives `cleanup`.

## Launch

Start a completely isolated FastAPI + SQLite WAL + headless Chrome CDP session from an empty data directory:

```bash
cd keelway
./.cursor/skills/verify-keelway/scripts/control-keelway launch \
  --state-dir /tmp/keelway-verify-run1
```

What `launch` isolates and verifies before returning `{"ok": true}`:

1. **Side-by-side multi-instance isolation:** Two or more verification runs can execute concurrently when given distinct `--state-dir` paths. `launch` binds an ephemeral loopback port (`127.0.0.1:<PORT>`), generates a per-instance `kw_verify_<hex>` bearer token, and redirects **both** `HOME` (`$STATE_DIR/home/.keelway/platform_runtime.db`, `vault_master.key`, `keelway.db`) and working directory (`$STATE_DIR/workspace/.keelway/*`) so the operator's real `~/.keelway` and `<repo>/.keelway` are never touched.
2. **True usability readiness (not just port open):** `launch` waits until `GET /health` returns `200`, authenticated `GET /v1/platform/workspaces` initializes `platform_runtime.db` and returns the first-run workspace (`default`), `GET /app?token=<TOKEN>` serves `/app/assets/*` from `core/dev_app_dist`, and headless Chrome hydrates React 19 with `[aria-label="Unified workspace bar"]` mounted in the live DOM.
3. **Prerequisite check:** If `core/dev_app_dist/index.html` is missing or stale after editing `dev-app/src/`, rebuild it first with `(cd dev-app && npm run build)`.

To tear down immediately after a run (or after a failed attempt):

```bash
./.cursor/skills/verify-keelway/scripts/control-keelway cleanup \
  --state-dir /tmp/keelway-verify-run1
```

## Doctor

Before driving an existing instance — or whenever a selector or API response looks unexpected — run the read-only health check:

```bash
./.cursor/skills/verify-keelway/scripts/control-keelway doctor \
  --state-dir /tmp/keelway-verify-run1
```

`doctor` exits `0` only when all six invariants hold:

- `serverPidAlive`: our `uvicorn` PID is alive.
- `chromePidAlive`: our headless Chrome PID is alive.
- `isolatedRuntimeDb`: `platform_runtime.db` exists inside `STATE_DIR` (never `~/.keelway`).
- `authGateOwnedByUs`: unauthenticated `GET /v1/platform/overview` returns `401` while our instance token returns `200`, proving the port belongs to our process and not a stray server.
- `overviewReady`: `GET /v1/platform/overview` returns `200`.
- `browserHydrated`: CDP confirms `[aria-label="Unified workspace bar"]` is mounted and reports the active workspace ID.

## Drive

Drive the live React 19 `/app` DOM over Chrome DevTools Protocol and cross-check via `cli` and `db-query` using real ARIA handles from `dev-app/src/`:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-run1

# Switch top-level platform views (IDE, Agents, Project Manager, Product, Automation,
# Marketplace, Security, Documentation, Operations, No-Code Builder)
$CTRL browser click --state-dir "$STATE" --role button --name "Security"
$CTRL browser click --state-dir "$STATE" --role button --name "Agents"
$CTRL browser click --state-dir "$STATE" --role button --name "Operations"
$CTRL browser click --state-dir "$STATE" --role button --name "No-Code Builder"

# Workspace bar selectors (PlatformWorkspaceBar.tsx)
$CTRL browser select --state-dir "$STATE" --label "Active workspace switcher" --value "default"
$CTRL browser select --state-dir "$STATE" --label "Active RBAC role" --value "operator"
$CTRL browser select --state-dir "$STATE" --label "Subscription tier" --value "byom"
$CTRL browser click  --state-dir "$STATE" --role button --name "Guided Non-Coder"

# Fill React 19 controlled inputs by aria-label
$CTRL browser fill --state-dir "$STATE" --label "Secret name" --value "OPENAI_API_KEY"
$CTRL browser select --state-dir "$STATE" --label "Secret namespace" --value "byom"
$CTRL browser fill --state-dir "$STATE" --label "Plaintext secret value" --value "sk-live-keelway-verify-998877"
$CTRL browser click --state-dir "$STATE" --role button --name "Encrypt & Store Secret"

# Wait for visible UI state transitions
$CTRL browser wait-for --state-dir "$STATE" --text "OPENAI_API_KEY"

# Cross-verify via the real Sovereign CLI against the exact same isolated SQLite WAL DB
$CTRL cli --state-dir "$STATE" -- vault list --json

# Inspect read-only SQLite WAL tables (PRAGMA query_only = ON)
$CTRL db-query --state-dir "$STATE" \
  --sql "SELECT workspace_id, name, namespace, masked_preview, version, length(ciphertext) AS cipher_bytes FROM platform_secrets"
```

Why `browser click` matters for P-10 gates: `Button.tsx` enforces `clickOnly` (`isTrustedUserEvent` checking `nativeEvent.isTrusted === true`) on P-10 approval actions (`Approve P-10 & Resume Stream`, `Deny & Abort Run`). Synthetic DOM `.click()` calls are rejected by design; `control-keelway browser click` dispatches genuine hardware-pipeline CDP `Input.dispatchMouseEvent` (`mousePressed`/`mouseReleased`), which satisfies `event.isTrusted === true` while still refusing `disabled` / `aria-disabled="true"` RBAC locks with exit code `2`.

## Evidence

Store every proof artifact in an explicit `EVIDENCE_DIR` outside `STATE_DIR` (for example `/tmp/keelway-evidence-<topic>` or `<artifactDir>/verify-keelway-proof/`):

```bash
EVIDENCE=/tmp/keelway-evidence-run1
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-after-action.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-after-action.png"
$CTRL cli                --state-dir "$STATE" --out "$EVIDENCE/02-cli-readback.json" -- vault list --json
$CTRL db-query           --state-dir "$STATE" --out "$EVIDENCE/03-sqlite-wal.json" \
  --sql "SELECT workspace_id, name, masked_preview, version, hex(nonce) AS nonce_hex FROM platform_secrets"
```

Proof standards for Keelway:

1. **Drive the real user path:** Trigger features through `/app` UI controls or `cli.py` subcommands — never mutate SQLite rows directly (`db-query` enforces `PRAGMA query_only = ON`) and never hit internal Python helpers to fake state.
2. **Capture before/action/after + side effects:** A complete feature proof includes (a) the ARIA tree snapshot (`*.aria.txt`), (b) a visual PNG screenshot (`*.png`), (c) a second-surface confirmation (`cli.py --json` or `api --path /v1/...`), and (d) a read-only SQLite WAL side-effect readback (`platform_secrets`, `platform_execution_runs`, `platform_workspaces_dir`, or `platform_webhooks`) when persistence is involved.
3. **Honest simulation boundaries:** Two surfaces operate deterministically offline by design when external systems are absent:
   - `SignedWebhookBus` records HMAC-SHA256 deliveries (`X-Keelway-Signature-256: sha256=...`) in `platform_webhook_deliveries` with `status="recorded_local"` without opening outbound sockets unless external delivery is wired.
   - `PricingMiroFishSimulator` runs deterministic 5-persona elasticity math locally (`POST /v1/platform/pricing/simulate` and `cli.py pricing-eval`) with zero LLM network egress. Observe and report those exact boundaries rather than claiming live third-party HTTP traffic.

## Cleanup

Always tear down the verification instance — including after failed steps — using `cleanup`:

```bash
./.cursor/skills/verify-keelway/scripts/control-keelway cleanup \
  --state-dir /tmp/keelway-verify-run1
```

Cleanup rules:

- **Never kill by process name:** Never run `pkill uvicorn`, `killall python`, or `pkill Google Chrome`. `cleanup` reads `$STATE_DIR/instance.json` and sends `SIGTERM` (escalating to `SIGKILL` after 3.5s) strictly to the recorded `chromePid` and `serverPid`.
- **Evidence survives teardown:** `cleanup` deletes `$STATE_DIR` (`home/`, `workspace/`, `chrome-profile/`, `logs/`, `instance.json`) and never touches `EVIDENCE_DIR`. Always verify `ls -la "$EVIDENCE_DIR"` after `cleanup` completes.

## Helpers

The skill ships one executable zero-dependency helper (backed by [`scripts/control-keelway.mjs`](scripts/control-keelway.mjs)):

- [`scripts/control-keelway`](scripts/control-keelway)

Supported subcommands:

| Command | Purpose |
| --- | --- |
| `control-keelway launch [--state-dir <DIR>] [--port <PORT>]` | Start isolated FastAPI + SQLite WAL + headless Chrome and wait for React `/app` hydration |
| `control-keelway doctor [--state-dir <DIR>]` | Read-only 6-point health, auth-ownership, DB-isolation, and DOM check |
| `control-keelway browser click --name <TEXT> [--role <ROLE>] [--exact]` | Scroll into view and dispatch trusted CDP mouse click (refuses disabled controls with exit code `2`) |
| `control-keelway browser fill --label <LABEL> --value <TEXT>` | Populate React 19 controlled `<input>` / `<textarea>` by `aria-label` or label text |
| `control-keelway browser select --label <LABEL> --value <VALUE>` | Select `<option>` on a React 19 `<select>` by `aria-label` or label text |
| `control-keelway browser wait-for --text <TEXT> [--timeout-ms 8000]` | Poll visible page text until substring appears |
| `control-keelway browser snapshot --aria [--out <FILE>]` | Export structured W3C ARIA tree of the current `/app` view |
| `control-keelway browser screenshot --out <FILE.png> [--full-page]` | Capture PNG screenshot via CDP |
| `control-keelway cli [--out <FILE.json>] -- <cli.py args...>` | Run `python cli.py ...` bound to the instance's isolated `HOME` and `platform_runtime.db` |
| `control-keelway api --method <M> --path </v1/...> [--role <R>] [--actor <A>] [--body <JSON>] [--out <FILE.json>]` | Send authenticated loopback REST request with optional RBAC role/actor headers |
| `control-keelway db-query --sql "<SELECT ...>" [--out <FILE.json>]` | Run strictly read-only (`PRAGMA query_only = ON`) SQLite WAL inspection |
| `control-keelway cleanup [--state-dir <DIR>]` | Terminate tracked `chromePid` + `serverPid` and remove `--state-dir` while preserving evidence |
