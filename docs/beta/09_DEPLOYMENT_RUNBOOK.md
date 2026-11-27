# 09 — Deployment Runbook (verified surfaces)

## Deployable units

| Unit | How | Verified state |
| ---- | --- | -------------- |
| Local studio | `keelway dev` → FastAPI serves embedded `core/dev_app_dist` on :7420; launch token printed | WORKING |
| Desktop | `keelway desktop` — Chromium app-mode window | WORKING_COMPONENT (not packaged/signed) |
| Self-hosted | `docker compose up` — control-plane :8000 + platform :7420, `/data` volume, non-root | SMOKE-TESTED 2026-11-27 (P0-3): image builds clean; `GET /health` → `{"status":"ok","database_connected":true}` (200); `GET /app/` → 200 HTML; `--no-access-log` confirmed (no `?token=` in container logs). Requires `KEELWAY_POLICY_SIGNING_KEY` in `.env` (see `env.example`). Health route is `/health`, not `/v1/health`. |
| Enterprise | `deploy/helm`, `deploy/k8s`, `deploy/terraform` | UNVERIFIED E2E |
| Marketing site | `website/` → Vercel `kora-sable.vercel.app` | DEPLOYED |

## Beta onboarding (happy path — cold-run verified 2026-11-27)

```bash
pip install <wheel>          # or: python -m pip install .
keelway init                 # scaffold .keelway in repo
keelway doctor               # 10-axis preflight → "HEALTHY — 10/10 Dimensions" (verified)
keelway dev                  # prints launch URL + token → opens Studio at /?token=<launch>
```

First agent run (choose one):

```bash
keelway chat "hello"                    # terminal chat; --conversation <id> resumes
# or in Studio: open /app/ → AI workspace → send a message
# or via API: POST /v1/chat/message {"message":"hi"} → returns conversation_id
```

Self-hosted path:

```bash
cp env.example .env
openssl rand -hex 32                     # paste into KEELWAY_POLICY_SIGNING_KEY
docker compose up -d keelway-platform
curl -sf localhost:7420/health           # {"status":"ok",...}; studio at /app/
```

Optional cloud escalation requires explicit provider API key +
signed authorization; `private` payloads never egress regardless.

## Rollback

- Local: `pip install <previous-wheel>`; `.keelway/` state and SQLite
  DB are per-install — no forward-migration needed for beta data.
- Compose: `docker compose down && git checkout <prev-tag> && docker
  compose up --build`.
- Website: Vercel instant rollback to prior deployment.
- **Backup:** snapshot `KEELWAY_DB_PATH` SQLite + `.keelway/` dir
  before upgrade; no migration framework exists (P2).

## Production checklist deltas

- `KEELWAY_POLICY_SIGNING_KEY` required for compose (`env.example`)
- `OLLAMA_BASE_URL` honored after P0-6 for non-default runtimes
- Vercel env for `website/` unchanged this release
