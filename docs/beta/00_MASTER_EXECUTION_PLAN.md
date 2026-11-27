# 00 — Master Execution Plan (Keelway Enterprise Beta)

- **Release:** Keelway controlled enterprise beta
- **Deadline:** Friday 2026-11-27, 11:59 PM EST
- **Feature freeze:** Friday 5:00 PM EST — after that only release blockers,
  security defects, usability failures and regression fixes.
- **Audit baseline:** `origin/main` @ `bdab521` (post KEEL-ENG-065 merge)
- **Prior baseline:** `docs/release-readiness/2026-11-17/` (15 artifacts,
  all 10 known defects now closed)

## Verified product shape (read before planning)

Keelway is a **sovereign, local-first AI developer environment** — not a
multi-tenant SaaS. The shippable beta unit is:

1. `keelway dev` — local FastAPI control plane serving the embedded
   React dev-app (`core/dev_app_dist`), authenticated by a per-process
   launch token plus named role tokens (`keelway token create`,
   POST /v1/auth/tokens) and one-shot phone pairing codes.
2. `docker-compose` / `deploy/` (helm, k8s, terraform) — self-hosted
   control-plane (:8000) + platform (:7420) deployment.
3. `website/` — Next.js marketing site on Vercel (`kora-sable.vercel.app`);
   `web-next/` is the V3 successor in flight.

The plan's SaaS-framed modules map to sovereign equivalents:

| Plan module        | Verified reality |
| ------------------ | ---------------- |
| Login/registration | Launch-token + role-token auth (no user registration by design) |
| Dashboard          | dev-app Studio (10+ views, React, embedded) |
| AI workspace       | Chat modes + agent loops via model gateway |
| Model gateway      | Implemented (Ollama/vLLM/local + cloud adapters, air-gap fail-closed) |
| Conversations      | InteractiveChatSession — **in-memory; persistence is a P0 gap** |
| Settings           | dev-app settings workspace (governance/models/system panels) |
| Team management    | Absent by design (single-operator) — descope or reframe |
| Usage analytics    | Cost ledger / economic observability — implemented |

## Workstream ownership (per user directive)

| Lane      | Agent        | File ownership |
| --------- | ------------ | -------------- |
| Architecture | GStack     | docs/, ADRs — review only |
| Backend   | Devin        | `core/`, `cli.py`, `keelway/`, `api/`, deploy configs |
| Frontend  | Antigravity  | `dev-app/`, `website/`, `web-next/` |
| AI eng    | Claude       | `core/models/`, `core/opencore/`, `evals/` |
| Security  | Review agent | `core/security/`, threat model, audits |
| QA        | Test agent   | `tests/`, `*/e2e/`, release checklist |
| Release   | Justin       | Merge approval, go/no-go |

## Sprint structure (compressed, verified)

1. **Audit (done):** this doc set — 01 audit + 04 backlog are the worklist.
2. **P0 blockers:** see `04_ENGINEERING_BACKLOG.md` — every P0 has a
   falsifiable acceptance criterion and an owning lane.
3. **Freeze at 5 PM Fri:** regression-only afterwards.
4. **Gates:** `10_BETA_RELEASE_CHECKLIST.md` — 25 checks mapped to
   evidence commands.
