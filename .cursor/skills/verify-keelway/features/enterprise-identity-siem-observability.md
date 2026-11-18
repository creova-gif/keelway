# Enterprise OIDC / SCIM 2.0 Identity, Dual-Human P-10 Quorum, SIEM Streaming & OpenTelemetry Observability

Users provision **SCIM 2.0** directory identities mapped to OIDC IdP groups and enforce **2-of-2 Dual-Human P-10 Quorum** approvals in **Security**, and export tamper-evident **SIEM Audit Batches (`OCSF v1.1` / `ArcSight CEF` / `JSONL`)** alongside live **Prometheus & OpenTelemetry OTLP** metrics in **Operations** or via `cli.py sso` / `cli.py scim` / `cli.py siem-export` / `cli.py metrics`.

## Sub-features

- Configure SSRF-guarded OIDC federation (`cli.py sso configure`), exchange signed `HS256` JWTs (`POST /v1/platform/enterprise/oidc/exchange` rejecting `alg=none`/expired/tampered with `401`), and provision SCIM 2.0 directory users (`Provision SCIM 2.0 User` restricted to `owner`/`admin`)
- Enforce 2-of-2 Dual-Human P-10 Quorum (`Sign P-10 Quorum Approval` restricted to `owner`/`operator`, blocking self-approval, `agent-*` bots, and duplicate signatures from the same human with `409 Conflict`)
- Stream DLP-redacted SIEM audit batches (`Export SIEM Audit Batch` across `OCSF v1.1`, `ArcSight CEF`, and `JSONL` with `batch_sha256`) and inspect live Prometheus / OpenTelemetry OTLP metrics (`Refresh Telemetry Snapshot`)

## How to get to it (user POV)

1. **Security view (`Enterprise Identity & Dual-Human P-10 Quorum`):** Open `/app?token=<TOKEN>`, click `Security` in `[aria-label="Unified platform views"]`, and locate `[aria-label="Enterprise OIDC, SCIM 2.0 directory and dual-human P-10 quorum"]`.
2. **Operations view (`SIEM Streaming & OpenTelemetry Observability`):** Click `Operations` in `[aria-label="Unified platform views"]` and locate `[aria-label="SIEM audit streaming and OpenTelemetry observability"]`.
3. **Sovereign CLI:** Run `python cli.py sso status|configure --json`, `python cli.py scim list|provision --json`, `python cli.py siem-export --format ocsf --json`, and `python cli.py metrics --format prometheus --json`.

## Driving it with control-keelway

Assume `STATE=/tmp/keelway-verify-phase9` is launched and `EVIDENCE=/tmp/keelway-evidence-phase9` is your persistent proof folder:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-phase9
EVIDENCE=/tmp/keelway-evidence-phase9

# 1. Provision SCIM 2.0 user & complete 2-of-2 Dual-Human P-10 Quorum in Security view
$CTRL browser click    --state-dir "$STATE" --role button --name "Security"
$CTRL browser fill     --state-dir "$STATE" --label "SCIM user email" --value "sre.lead@enterprise.example"
$CTRL browser click    --state-dir "$STATE" --role button --name "Provision SCIM 2.0 User"
$CTRL browser wait-for --state-dir "$STATE" --text "sre.lead@enterprise.example"
$CTRL browser fill     --state-dir "$STATE" --label "Human approver identity" --value "alice@keelway.local"
$CTRL browser click    --state-dir "$STATE" --role button --name "Sign P-10 Quorum Approval"
$CTRL browser wait-for --state-dir "$STATE" --text "awaiting_quorum"
$CTRL browser fill     --state-dir "$STATE" --label "Human approver identity" --value "bob@keelway.local"
$CTRL browser click    --state-dir "$STATE" --role button --name "Sign P-10 Quorum Approval"
$CTRL browser wait-for --state-dir "$STATE" --text "quorum_approved"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-security-enterprise-quorum.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-security-enterprise-quorum.png" --full-page

# 2. Export SIEM OCSF batch & refresh Prometheus/OTLP metrics in Operations view
$CTRL browser click    --state-dir "$STATE" --role button --name "Operations"
$CTRL browser click    --state-dir "$STATE" --role button --name "Export SIEM Audit Batch"
$CTRL browser click    --state-dir "$STATE" --role button --name "Refresh Telemetry Snapshot"
$CTRL browser wait-for --state-dir "$STATE" --text "keelway_scim_active_users"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/02-operations-siem-metrics.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/02-operations-siem-metrics.png" --full-page

# 3. Cross-check CLI parity + SQLite WAL persistence
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/03-cli-scim-users.json" -- scim list --json
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/04-cli-siem-export.json" -- siem-export --format ocsf --json
$CTRL db-query --state-dir "$STATE" --out "$EVIDENCE/05-sqlite-scim-quorum.json" \
  --sql "SELECT proposal_id, approval_count, status FROM platform_p10_quorums ORDER BY proposal_id LIMIT 5"
```

## Gotchas

- `Provision SCIM 2.0 User` requires `rbac:manage` (`owner` or `admin`).
- `Sign P-10 Quorum Approval` requires `runs:approve_p10` (`owner` or `operator` only) and two **distinct** human identities; submitting the same `approver_id` twice returns `409 Conflict`.
