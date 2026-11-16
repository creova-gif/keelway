# KBrain Scope-Governed Memory Graph & KHub Air-Gapped Skill Mirror

Users record DLP-protected, scope-governed workspace facts and run **Hybrid BM25 + 3-Gram Cosine** retrieval in **Documentation**, and verify air-gapped **KHub `.skill.tar.gz` Mirrors** in **Marketplace** or via `cli.py kbrain` / `cli.py khub`.

## Sub-features

- Record scope-governed KBrain facts (`Record Memory Fact` across `local_session`, `project`, `team`, `org`), reject leaked credentials (`400 Bad Request`), detect contradictory facts (`status="conflict"`), and resolve conflicts via `runs:approve_p10` (`owner`/`operator` only)
- Search KBrain memory with deterministic Hybrid BM25 + character 3-gram cosine ranking (`Search KBrain Memory`) respecting `max_scope` ACLs
- Inspect built-in `kstack_builtin` skills and run full roundtrip export + verified unpack of air-gapped KHub skill mirrors (`Verify Air-Gapped Skill Mirror`)

## How to get to it (user POV)

1. **Documentation view (`KBrain Memory Graph`):** Open `/app?token=<TOKEN>`, click `Documentation` in `[aria-label="Unified platform views"]`, and locate `[aria-label="KBrain scope-governed memory graph and hybrid BM25 search"]`.
2. **Marketplace view (`KHub Air-Gapped Mirror`):** Click `Marketplace` in `[aria-label="Unified platform views"]` and locate `[aria-label="KHub air-gapped skill registry and mirror verifier"]`.
3. **Sovereign CLI:** Run `python cli.py kbrain record|search|resolve --json` and `python cli.py khub skills|verify-mirror --json`.

## Driving it with control-keelway

Assume `STATE=/tmp/keelway-verify-phase10` is launched and `EVIDENCE=/tmp/keelway-evidence-phase10` is your persistent proof folder:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-phase10
EVIDENCE=/tmp/keelway-evidence-phase10

# 1. Record a KBrain fact & run Hybrid BM25 search in Documentation view
$CTRL browser click    --state-dir "$STATE" --role button --name "Documentation"
$CTRL browser fill     --state-dir "$STATE" --label "KBrain fact statement" --value "All sovereign tables enforce SQLite WAL and SHA-256 provenance."
$CTRL browser click    --state-dir "$STATE" --role button --name "Record Memory Fact"
$CTRL browser fill     --state-dir "$STATE" --label "KBrain hybrid search query" --value "SQLite WAL provenance"
$CTRL browser click    --state-dir "$STATE" --role button --name "Search KBrain Memory"
$CTRL browser wait-for --state-dir "$STATE" --text "arch.storage_engine"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-docs-kbrain-memory.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-docs-kbrain-memory.png" --full-page

# 2. Verify air-gapped KHub skill mirror in Marketplace view
$CTRL browser click    --state-dir "$STATE" --role button --name "Marketplace"
$CTRL browser click    --state-dir "$STATE" --role button --name "Verify Air-Gapped Skill Mirror"
$CTRL browser wait-for --state-dir "$STATE" --text "khub-airgap-mirror-v1"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/02-marketplace-khub-mirror.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/02-marketplace-khub-mirror.png" --full-page

# 3. Cross-check CLI parity + SQLite WAL persistence
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/03-cli-kbrain-search.json" -- kbrain search --query "SQLite WAL" --json
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/04-cli-khub-skills.json" -- khub skills --json
$CTRL db-query --state-dir "$STATE" --out "$EVIDENCE/05-sqlite-kbrain-khub.json" \
  --sql "SELECT id, key, scope, status, fact_sha256 FROM platform_kbrain_facts ORDER BY created_at DESC LIMIT 5"
```

## Gotchas

- Statements containing API keys (`sk-...`, `ghp_...`, `AKIA...`) or private keys fail closed with `400 Bad Request` (`SecretLeakDetectedError`).
- Resolving conflicting facts (`Resolve Conflict (P-10 Approve)`) requires `runs:approve_p10` (`owner` or `operator` only).
