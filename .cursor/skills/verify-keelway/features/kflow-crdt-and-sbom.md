# Topological KFlow DAG Runner, KSpaces CRDT Sync & CycloneDX 1.5 SBOM

Users execute topological multi-wave **KFlow DAGs** with P-10 human checkpoints and synchronize conflict-free **KSpaces CRDT** workspace state (Lamport + peer tie-breaking with vector clocks) in **Automation**, and generate cryptographically verified **CycloneDX 1.5 SBOM** manifests in **Security** or via `cli.py kflow` / `cli.py kspaces-sync` / `cli.py sbom`.

## Sub-features

- Execute Kahn-sorted topological KFlow DAGs (`Execute Topological DAG`), pause on `awaiting_p10` nodes (`Approve Held DAG Node` restricted to `owner`/`operator`), and reject cycles (`400 Bad Request`)
- Synchronize multi-peer LWW-Element-Set CRDT operations (`Sync CRDT Operation`) with automatic secret redaction, vector clocks, and `state_digest_sha256`
- Generate & cryptographically verify CycloneDX 1.5 Software Bills of Materials (`Generate & Verify CycloneDX 1.5 SBOM` / `cli.py sbom --verify --json`)

## How to get to it (user POV)

1. **Automation view (`KFlow DAG & KSpaces CRDT`):** Open `/app?token=<TOKEN>`, click `Automation` in `[aria-label="Unified platform views"]`, and locate `[aria-label="Topological KFlow DAG runner and KSpaces CRDT sync"]`.
2. **Security view (`CycloneDX 1.5 SBOM`):** Click `Security` in `[aria-label="Unified platform views"]` and locate `[aria-label="CycloneDX 1.5 SBOM and supply-chain provenance"]`.
3. **Sovereign CLI:** Run `python cli.py kflow execute|runs --json`, `python cli.py kspaces-sync push|state --json`, and `python cli.py sbom --verify --json`.

## Driving it with control-keelway

Assume `STATE=/tmp/keelway-verify-phase8` is launched and `EVIDENCE=/tmp/keelway-evidence-phase8` is your persistent proof folder:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-phase8
EVIDENCE=/tmp/keelway-evidence-phase8

# 1. Execute Topological DAG & sync a KSpaces CRDT entry in Automation view
$CTRL browser click  --state-dir "$STATE" --role button --name "Automation"
$CTRL browser click  --state-dir "$STATE" --role button --name "Execute Topological DAG"
$CTRL browser fill   --state-dir "$STATE" --label "CRDT peer ID" --value "peer-macbook"
$CTRL browser fill   --state-dir "$STATE" --label "CRDT entry key" --value "release.tag"
$CTRL browser fill   --state-dir "$STATE" --label "CRDT entry value" --value "v1.0.0"
$CTRL browser click  --state-dir "$STATE" --role button --name "Sync CRDT Operation"
$CTRL browser wait-for --state-dir "$STATE" --text "peer-macbook"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-automation-kflow-crdt.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-automation-kflow-crdt.png" --full-page

# 2. Generate & verify CycloneDX 1.5 SBOM in Security view
$CTRL browser click    --state-dir "$STATE" --role button --name "Security"
$CTRL browser click    --state-dir "$STATE" --role button --name "Generate & Verify CycloneDX 1.5 SBOM"
$CTRL browser wait-for --state-dir "$STATE" --text "VERIFIED"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/02-security-cyclonedx-sbom.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/02-security-cyclonedx-sbom.png" --full-page

# 3. Cross-check CLI parity + SQLite WAL persistence
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/03-cli-kspaces-state.json" -- kspaces-sync state --json
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/04-cli-sbom-verify.json" -- sbom --verify --json
$CTRL db-query --state-dir "$STATE" --out "$EVIDENCE/05-sqlite-kflow-crdt.json" \
  --sql "SELECT workspace_id, namespace, entry_key, lamport_ts, peer_id FROM platform_crdt_entries ORDER BY lamport_ts DESC LIMIT 5"
```

## Gotchas

- `Approve Held DAG Node` requires `runs:approve_p10` (`owner` or `operator` only); `builder`, `admin`, and `viewer` receive `403 Forbidden`.
- Under RBAC role `viewer`, `Execute Topological DAG` and `Sync CRDT Operation` are disabled (`aria-disabled="true"`).
