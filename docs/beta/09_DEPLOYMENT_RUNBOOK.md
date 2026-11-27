# 09 — Deployment Runbook (verified surfaces)

## Deployable units

| Unit | How | Verified state |
| ---- | --- | -------------- |
| Local studio | `keelway dev` → FastAPI serves embedded `core/dev_app_dist` on :7420; launch token printed | WORKING |
| Desktop | `keelway desktop` — Chromium app-mode window | WORKING_COMPONENT (not packaged/signed) |
| Self-hosted | `docker compose up` — control-plane :8000 + platform :7420, `/data` volume, non-root | BUILT, NOT SMOKE-TESTED (P0-3) |
| Enterprise | `deploy/helm`, `deploy/k8s`, `deploy/terraform` | UNVERIFIED E2E |
| Marketing site | `website/` → Vercel `kora-sable.vercel.app` | DEPLOYED |

## Beta onboarding (happy path)

```bash
pip install <wheel>          # or: python -m pip install .
keelway init                 # scaffold .keelway in repo
keelway doctor               # 10-axis preflight (db, gateway, air-gap, sandbox…)
keelway dev                  # prints launch URL + token → opens Studio
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
