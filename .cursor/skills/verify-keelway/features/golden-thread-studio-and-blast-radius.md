# Golden-Thread 4-Stage Journey Bar, Bidirectional KFlow ↔ Code Split Studio & Sandbox Blast-Radius Radar

Users navigate across the **4-Stage Golden-Thread Journey Bar** (*Plan & Import → Build & Sync Studio → Scrub & Blast-Radius → Govern & Ship*), synchronize visual SVG KFlow topologies bidirectionally with line-mapped Python/TypeScript source code (`Lstart–Lend`, zero `eval`/`exec`) in **Automation**, and scrub horizontal **Flight-Tape Waterfall Timelines** paired with a **Live Sandbox Blast-Radius Radar** and **Inline Prompt Regression Gate** in **Agents** or via `cli.py kflow-sync|blast-radius|prompt-gate`.

## Sub-features

- Navigate end-to-end across the 4-stage lifecycle via `[aria-label="Golden-thread lifecycle journey"]` and 1-click stage progression (`Advance golden thread stage`) while keeping all 10 workspace views directly accessible
- Bidirectionally sync SVG KFlow node/edge/cycle topology with Python & TypeScript source (`Sync code to visual KFlow graph` & `Toggle P-10 lock for <id>`) with exact AST line highlighting (`Lstart–Lend`) and `sync_sha256` drift digest
- Scrub counterfactual fork playheads directly on `[aria-label="Flight-tape waterfall timeline scrubber"]`, previewing `$0` cached upstream spans vs. forked downstream branches
- Audit Seatbelt filesystem reads/writes, blocked paths, and zero-unapproved-egress receipts (`Audit sandbox blast-radius` -> `audit_sha256`) and run 1-click Golden Eval prompt/schema gates (`Run prompt regression gate` -> `PASS` / `BLOCK` + `gate_sha256`)

## How to get to it (user POV)

1. **Top Workspace Bar (`Golden-Thread Journey`):** Open `/app?token=<TOKEN>` and inspect `[aria-label="Golden-thread lifecycle journey"]`.
2. **Automation view (`Bidirectional KFlow ↔ Code Studio`):** Click `Automation` (or Stage 2) and locate `[aria-label="Bidirectional KFlow visual and AST code studio"]`.
3. **Agents view (`Flight-Tape Waterfall Scrubber, Blast-Radius Radar & Prompt Gate`):** Click `Agents` (or Stage 3) and locate `[aria-label="Flight-tape waterfall timeline scrubber"]`, `[aria-label="Sandbox blast-radius radar"]`, and `[aria-label="Inline prompt regression gate"]`.
4. **Sovereign CLI:** Run `python cli.py kflow-sync --json`, `python cli.py blast-radius record|list --json`, and `python cli.py prompt-gate evaluate|list --json`.

## Driving it with control-keelway

Assume `STATE=/tmp/keelway-verify-phase12` is launched and `EVIDENCE=/tmp/keelway-evidence-phase12` is your persistent proof folder:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-phase12
EVIDENCE=/tmp/keelway-evidence-phase12

# 1. Exercise Golden-Thread Stage 2 -> Bidirectional SVG KFlow <-> Code Studio in Automation
$CTRL browser click      --state-dir "$STATE" --role button --name "Automation"
$CTRL browser click      --state-dir "$STATE" --role button --name "Sync code to visual KFlow graph"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-automation-bidirectional-kflow-studio.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-automation-bidirectional-kflow-studio.png" --full-page

# 2. Advance Golden Thread -> Agents view: Scrub Flight-Tape Waterfall, Audit Blast-Radius & Run Prompt Gate
$CTRL browser click      --state-dir "$STATE" --role button --name "Agents"
$CTRL browser click      --state-dir "$STATE" --role button --name "Ingest OTel GenAI Trace"
$CTRL browser click      --state-dir "$STATE" --role button --name "Audit sandbox blast-radius"
$CTRL browser wait-for   --state-dir "$STATE" --text "blast-"
$CTRL browser click      --state-dir "$STATE" --role button --name "Run prompt regression gate"
$CTRL browser wait-for   --state-dir "$STATE" --text "pgate-"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/02-agents-scrubber-blast-radius-gate.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/02-agents-scrubber-blast-radius-gate.png" --full-page

# 3. Cross-check CLI parity + SQLite WAL persistence
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/03-cli-blast-radius-list.json" -- blast-radius list --json
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/04-cli-prompt-gate-list.json" -- prompt-gate list --json
$CTRL db-query --state-dir "$STATE" --out "$EVIDENCE/05-sqlite-studio-audits.json" \
  --sql "SELECT audit_id, risk_tier, zero_unapproved_egress, syscalls_audited, audit_sha256 FROM platform_blast_radius_audits ORDER BY recorded_at DESC LIMIT 5"
```

## Gotchas

- `source_code` payloads exceeding `262,144` bytes return `HTTP 413`; malformed Python/TypeScript syntax returns `HTTP 422` without ever calling `eval`/`exec`.
- `viewer` RBAC role can inspect read-only `code_to_graph` previews, blast-radius audits, and prompt-gate runs (`200`), while `graph_to_code` persistence, blast-radius recording, and prompt-gate evaluation require `agents:dispatch` (`403` for `viewer`).
