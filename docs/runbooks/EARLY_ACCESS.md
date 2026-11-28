# Runbook — Developer Onboarding & Early-Access Fulfillment

> KEEL-REL-052 · Owner: Sorvex Labs ops · Last verified: 2026-11-16
> Scope: what happens between a developer discovering Keelway and a
> governed agent session producing verifiable evidence — plus the
> operational process behind `POST /api/early-access`.

---

## 1. Developer onboarding journey (target: < 15 min to first governed run)

| Step | Command / action | Expected result | If it fails |
|---|---|---|---|
| 1. Install | `bash scripts/install.sh` | `~/.keelway/venv` created, editable install | Run `scripts/verify_install.sh` to reproduce clean-env check |
| 2. Health | `keelway doctor --json` | `overall_status: HEALTHY` | Doctor output names the failing check; fix env (Python ≥3.11, deps) |
| 3. Detect agents | `keelway harness agents detect` | Lists `claude`, `codex`, `cursor-agent` with versions | Missing binary → install that agent CLI first |
| 4. Wire governance | `keelway harness agents setup --agent <host> --mode audit_only` | Writes `.claude/settings.local.json` / `.codex/hooks.toml` / `.cursor/hooks.json` with PreToolUse+PostToolUse+SessionStart hooks | `agent_not_installed` → step 3; rerun after installing the CLI |
| 5. First governed call | Run the agent; hooks pipe payloads to `agents intercept` | Destructive commands denied; sensitive mutations → P-10 hold; decisions recorded | See §3 diagnostics |
| 6. Verify evidence | `keelway tape list` then `keelway tape verify --trace-id <id>` | `SEAL VERIFIED`, exit 0 | `TAMPER DETECTED` → treat as security incident (§4) |

Mode guidance: ship `audit_only` first (records verdicts, never blocks),
then flip to `--mode enforce` once the team trusts the verdict stream.

## 2. Early-access intake (web-next → fulfillment)

### 2.1 Submission path

`POST /api/early-access` (`api/early-access.js`):

1. Enforces strict `Origin` allowlist checks (`403` on untrusted origins), bounded JSON payload caps (`4 KB` max, `413` beyond that), and per-IP sliding-window rate limits (`5 / 10 min` → `429`).
2. Validates RFC-safe work email syntax and allowlisted `interest`/`role`/`region` fields (`400` on invalid input).
3. Mints opaque reference ID `KW-XXXXXXXX`.
4. **If `EARLY_ACCESS_WEBHOOK_URL` is set to a valid private HTTPS sink** (GitHub Issues endpoints and loopback/private SSRF addresses are structurally rejected): delivers a signed JSON intake event (`X-Keelway-Signature-256` when `EARLY_ACCESS_WEBHOOK_SECRET` is configured) and returns `200 { ok: true, referenceId }`.
5. **Otherwise**: fails closed with `503 { ok: false, error: "early access intake is temporarily unavailable" }` without logging submitter PII or writing to any public repository.

### 2.2 Required configuration (production checklist)

- [ ] `EARLY_ACCESS_WEBHOOK_URL` — private HTTPS CRM/intake webhook endpoint (never a public GitHub repository issue API).
- [ ] `EARLY_ACCESS_WEBHOOK_SECRET` — HMAC-SHA256 shared secret verified by the private intake receiver.
- [ ] `EARLY_ACCESS_ALLOWED_ORIGINS` — comma-separated production origins allowed to submit the form.

### 2.3 Triage SLA (proposed, founder to confirm)

| Queue | Target first-response | Owner |
|---|---|---|
| `founder_ops` / `cto_vp` | 1 business day | Founder |
| `ai_engineer` / `security_lead` | 2 business days | Eng |
| `creator_partner` / `ml_researcher` | 3 business days | Eng + founder |

### 2.4 Fulfillment checklist per submission

1. **Acknowledge** — reply referencing the `KW-…` ID; set expectation that
   install currently requires a source checkout (`KEELWAY_SOURCE_DIR`) until
   packaging ships — do not promise a `curl | sh` path that doesn't exist.
2. **Qualify** — map `interest` to the honest capability matrix:
   - `local` / `hybrid_routing` → usable today (real Ollama path verified).
   - `agent` → governance hooks verified; live vendor sessions pending quota.
   - `nocode_automation`, `team`, `marketplace_publish`, `vpc` → **planned**,
     say so explicitly.
3. **Deliver** — send the quickstart + `agents setup` instructions; offer a
   paired install session for `founder_ops`/`cto_vp`.
4. **Close the loop** — comment the outcome on the GitHub issue (or log it if
   fallback path), then close with the reference ID.

### 2.5 Known intake risks

- No-token deployments lose submissions into logs — treat as P1 config bug.
- GitHub issue creation failure is warn-logged but still returns `ok: true`
  to the user (intentional UX choice; monitor `early-access: upstream sync`
  warnings).
- Rate limiter is per-instance memory — serverless cold starts reset it;
  acceptable for beta, note for scale.

## 3. Diagnostics quick reference

| Symptom | Check |
|---|---|
| `agent_not_installed` on setup | `keelway harness agents detect`; verify binary on PATH |
| Hook not firing in agent | Confirm config file written to the *workspace* the agent runs in; check agent's own hook logs |
| P-10 hold never resolves | Ticket is single-use and command-hash-bound — regenerate via the hold flow, don't reuse |
| `tape_not_found` | `--workspace`/`--db-path` must match the store used at record time |
| `TAMPER DETECTED` | §4 |

## 4. Tamper response

`tape verify` uses unkeyed SHA-256 recompute: it proves stored rows match
their seals but cannot distinguish "DB never touched" from "attacker rewrote
rows *and* recomputed seals". On `TAMPER DETECTED`:

1. Preserve the DB file and WAL — do not "repair".
2. Check file mtimes/permissions on the DB directory.
3. Export the tape (`tape verify --json`) and file a security incident.
4. For evidentiary weight, use `keelway receipt verify` on signed receipts
   or request an HMAC-keyed export — unkeyed tapes are tamper-*evident*,
   not tamper-*proof* against a writer who controls the store.
