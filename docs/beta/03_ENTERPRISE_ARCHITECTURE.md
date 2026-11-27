# 03 — Enterprise Architecture (verified, not proposed)

## Topology

```
[ dev-app (React, embedded core/dev_app_dist) ]──┐
[ mobile (Expo, paired phone role)           ]  │  X-Studio-Token / Bearer
[ cli.py (operator)                          ]──┤
                                               ▼
                         core.main:app (FastAPI, :7420)
              ┌──────────────┬────────────────┬──────────────┐
              ▼              ▼                ▼              ▼
        core/security    core/api/*       core/models      core/storage
        token auth+RBAC  ~30 route mods   gateway+adapters  SQLAlchemy 2.x
        sandbox gates    SSE + REST       air-gap fail-closed SQLite + .keelway JSON
                                               │
                          ┌────────────────────┼────────────────────┐
                          ▼                    ▼                    ▼
                    Ollama / vLLM        cloud adapters       keelway-core:7b
                    (local open-weight)  (keyed, signed)      simulated fallback
```

- **Governance plane:** `keelway/api/app.py` (:8000) — second FastAPI
  app for governance auth/policy; compose runs both processes.
- **Deployment:** Dockerfile (py3.14-slim, non-root uid 10001),
  docker-compose (control-plane :8000 + platform :7420 + volume),
  `deploy/{helm,k8s,terraform,scripts}` for enterprise install.
- **Website:** `website/` Next.js → Vercel (kora-sable); `web-next/`
  V3 in flight behind the same token-freshness gate.

## Trust boundaries

1. **Token boundary** — every `/v1/*` route behind `Principal.can()`;
   phone tokens restricted to `PHONE_ROUTES`.
2. **Egress boundary** — air-gap mode drops cloud calls in the model
   gateway; `private` payloads never leave the host.
3. **Execution boundary** — agent commands only run under seatbelt
   (macOS) or bubblewrap (Linux); unverifiable isolation = refuse.
4. **Tenant boundary** — single-operator by design; multi-tenant
   isolation is N/A in beta.

## Verified invariants in code

- `AirGapViolationError` (HTTP 403) on cloud egress of private payloads
- `x-api-key`/`Authorization` headers built only from configured keys
- SSE decoder: explicit `(event, is_done)` tuple (KEEL-ENG-065)
- `request.model` Optional → canonical `keelway-core:7b` default
