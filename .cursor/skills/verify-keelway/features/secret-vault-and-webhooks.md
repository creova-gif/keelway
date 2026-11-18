# Encrypted Secret Vault & SSRF-Guarded Webhooks

Users store BYOM provider keys, plugin credentials, MCP tokens, and environment secrets in a local `AES-256-GCM` vault (`platform_secrets` in SQLite WAL) that never echoes plaintext after write, and register HMAC-SHA256 outbound webhooks (`platform_webhooks`) protected by strict SSRF validation.

## Sub-features

- Encrypt and store a secret by name, namespace (`byom`, `plugin`, `webhook`, `env`, `mcp`), and plaintext value (`Encrypt & Store Secret` / `cli.py vault put`)
- Mask secret previews (`sk-l...9877`) and clear the plaintext input immediately after storage
- Rotate an existing secret (`Rotate Secret <NAME>` / `cli.py vault rotate`) and increment `version` (`v1` -> `v2`)
- Revoke a secret (`Revoke Secret <NAME>` / `cli.py vault delete`)
- Register loopback/HTTPS webhooks and block private/link-local/metadata SSRF targets (`http://169.254.169.254/...`, `http://10.0.0.1/...`)

## How to get to it (user POV)

1. **Security view in `/app`:** Click `Security` in `[aria-label="Unified platform views"]` to open `[aria-label="Encrypted local secret vault"]` and `[aria-label="Signed outbound webhooks"]` above the hash-chained audit ledger.
2. **Sovereign CLI:** Run `python cli.py vault put|list|rotate|delete ... --json`.
3. **REST API:** Call `GET/POST /v1/platform/vault/secrets`, `DELETE /v1/platform/vault/secrets/{name}`, and `GET/POST /v1/platform/webhooks`.

## Driving it with control-keelway

Assume `STATE=/tmp/keelway-verify-vault` is launched and `EVIDENCE=/tmp/keelway-evidence-vault` is your persistent proof folder:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-vault
EVIDENCE=/tmp/keelway-evidence-vault

# 1. Open Security view and store an AES-256-GCM BYOM secret via the browser form
$CTRL browser click  --state-dir "$STATE" --role button --name "Security"
$CTRL browser fill   --state-dir "$STATE" --label "Secret name" --value "ANTHROPIC_API_KEY"
$CTRL browser select --state-dir "$STATE" --label "Secret namespace" --value "byom"
$CTRL browser fill   --state-dir "$STATE" --label "Plaintext secret value" --value "sk-ant-verify-secret-445566"
$CTRL browser click  --state-dir "$STATE" --role button --name "Encrypt & Store Secret"
$CTRL browser wait-for --state-dir "$STATE" --text "ANTHROPIC_API_KEY"

# 2. Register a loopback signed webhook and verify SSRF rejection on metadata IP
$CTRL browser fill  --state-dir "$STATE" --label "Webhook destination URL" --value "http://127.0.0.1:9999/hooks/keelway"
$CTRL browser click --state-dir "$STATE" --role button --name "Register Signed Webhook"
$CTRL browser wait-for --state-dir "$STATE" --text "127.0.0.1:9999/hooks/keelway"

# 3. Capture UI proof (ARIA + PNG)
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-security-vault-webhooks.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-security-vault-webhooks.png"

# 4. Rotate via Sovereign CLI (second view) and confirm v2 in CLI + SQLite WAL
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/02-cli-vault-rotate.json" -- \
  vault rotate ANTHROPIC_API_KEY "sk-ant-verify-rotated-990011" --json
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/03-cli-vault-list.json" -- \
  vault list --json
$CTRL db-query --state-dir "$STATE" --out "$EVIDENCE/04-sqlite-vault-webhooks.json" \
  --sql "SELECT workspace_id, name, namespace, masked_preview, version, length(nonce) AS nonce_len, length(ciphertext) AS cipher_len, hex(ciphertext) AS ciphertext_hex FROM platform_secrets"
```

Observable end state that proves success:

- `01-security-vault-webhooks.aria.txt` lists `ANTHROPIC_API_KEY`, `[byom]`, `v1`, masked preview `sk-a…5566`, and `http://127.0.0.1:9999/hooks/keelway`, and **never** contains the raw strings `sk-ant-verify-secret-445566` or `sk-ant-verify-rotated-990011`.
- `03-cli-vault-list.json` shows `version: 2` and updated `masked_preview` (`sk-a...0011`) in the same `default` workspace.
- `04-sqlite-vault-webhooks.json` confirms `nonce_len = 12` (96-bit GCM nonce), `cipher_len > 28` (ciphertext + 16-byte GCM tag), and zero plaintext in `ciphertext_hex`.

## Gotchas

- Clicking `Rotate Secret <NAME>` in the browser generates a synthetic rotated marker token in the UI handler; to test rotation with a specific caller-supplied secret value, drive `cli.py vault rotate <NAME> <NEW_VALUE>` or `POST /v1/platform/vault/secrets/{name}/rotate`.
- Plaintext `http://` webhook URLs are strictly rejected unless the host is `127.0.0.1` or `localhost`; non-loopback webhooks must use `https://` and non-private IP space.
- Under RBAC roles `operator` or `viewer` (which lack `secrets:write` and `webhooks:manage`), vault and webhook mutation buttons are disabled in `/app` and return `403` on `/v1/platform/*`.
