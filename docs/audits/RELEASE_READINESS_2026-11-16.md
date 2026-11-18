# Keelway Release-Readiness Assessment — UI/UX, Journeys & Beta Gates

> Date: 2026-11-16 · Branch evidence: `main` @ `8205521` · Scope: what stands between the current build and a credible developer beta.

## 1. Surface inventory (verified)

| Surface | State | Evidence |
|---|---|---|
| Marketing site (`website/`, Next.js on Vercel) | 8 routes: `/`, `/pricing`, `/docs`, `/models`, `/marketplace`, `/governance`, `/brand`, `/api-reference` + sitemap/robots/feed | `website/src/app/` |
| Early access | Working intake → GitHub issue via `EARLY_ACCESS_GH_TOKEN`; 400/500 fail paths handled; role/interest/region taxonomy | `api/early-access.js`, `website/src/app/api/early-access/route.ts` |
| Studio dev-app (`dev-app/`, 10 views) | Tasks, Files, Record/Audit, Settings, P-10 cards, golden-thread journey bar | `dev-app/src/components/screens/` |
| CLI | `harness`, `ci-gate`, `agents detect|intercept|event|run`, doctor, vault, models | `cli.py`, `core/cli_harness.py` |
| Docs | Quickstart, security invariants, ADRs 001–042+, audits, agent-operations | `docs/` |

## 2. User journeys — current state vs. beta bar

**J1 — Developer discovers → installs → runs first agent task**
- ✅ Website explains product; quickstart terminal component exists.
- ⚠️ `website/install.sh` exists but install path is untested end-to-end on a clean machine (no CI job proves `curl | sh` → `keelway doctor` healthy).
- ❌ No onboarding checklist in Studio/CLI ("next step" guidance after install).
- **Gate:** one documented, CI-verified install→doctor→first-task path.

**J2 — Developer governs a third-party agent**
- ✅ `harness hooks` emits working hook configs; `agents intercept/event/run` live; conformance suite exists.
- ⚠️ Requires manual hook install (`--install-dir .`) — no `keelway agents setup <host>` one-command flow.
- ⚠️ Real vendor hook delivery unverified (quota-blocked; Codex frees Nov 20).
- **Gate:** `agents setup` command + one live verified session per claimed host.

**J3 — Developer inspects evidence**
- ✅ Flight tapes, hash-chained interceptions, P-10 tickets, audit ledger UI.
- ⚠️ No user-facing "verify this tape" CLI command (`keelway verify <trace>`?) — evidence exists but verification UX is developer-hostile.
- **Gate:** `keelway tape verify` + Studio deep-link from agent run → tape.

**J4 — Buyer evaluates → requests access → gets onboarded**
- ✅ Early-access form with qualified intake.
- ❌ No onboarding email/template, no waitlist status page, no docs portal gating.
- **Gate:** defined manual onboarding runbook (acceptable pre-scale) + response SLA note on site.

## 3. UI/UX gaps (honest)

- **Brand consistency**: fixed across website/dev-app/vscode (KEEL-WEB-028/029/035) — ✅ done.
- **Accessibility**: axe-tested on key dev-app views; website a11y not systematically audited (no axe/lighthouse CI for `website/`).
- **Empty/error states**: not audited; beta needs a pass on Studio offline/model-unavailable states (we now *have* honest `simulated`/`installed` flags to surface).
- **Model truth surfacing**: `/v1/models` exposes `installed`/`simulated` — UI should badge simulated models rather than hide them (product decision needed).
- **Performance**: no Lighthouse budgets, no bundle analysis in CI.

## 4. Release-blocking gaps (priority order)

| # | Gap | Severity | Effort |
|---|---|---|---|
| 1 | Install path unverified end-to-end (clean machine → doctor healthy) | **Blocker** | S |
| 2 | `keelway-*` models simulated — registry truth decision (KEEL-PROD-041) | **Blocker** for model claims | Founder decision |
| 3 | No `agents setup` one-command hook install | High | S |
| 4 | No tape-verification UX (`keelway tape verify`) | High | S |
| 5 | Onboarding runbook + early-access fulfillment process | High | S |
| 6 | Website a11y/perf CI (Lighthouse/axe budgets) | Medium | M |
| 7 | Studio empty/error-state audit + simulated-model badges | Medium | M |
| 8 | Live vendor hook-delivery verification (post Nov 20 quota) | Medium | S (blocked externally) |
| 9 | OIDC real federation / package consolidation / payments | Post-beta | L |

## 5. Recommended next tasks

- **KEEL-REL-049** — Install verification: scripted clean-env install test + docs fix. *Acceptance:* fresh venv → `install.sh` or pip path → `keelway doctor` HEALTHY, asserted in CI.
- **KEEL-REL-050** — `keelway harness agents setup <host>`: render manifest + install hook config into workspace in one command (composes existing `hooks --install-dir` + `agents` detection).
- **KEEL-REL-051** — `keelway tape verify <trace-id>`: recompute step/tape SHA-256 like the conformance test does; Studio link.
- **KEEL-REL-052** — Onboarding runbook doc + early-access fulfillment checklist.
- Founder decision **KEEL-PROD-041** remains the gating item for any model-capability marketing.

## 6. Beta gate definition (proposed)

Public beta is defensible when: (1) install→first-task verified on clean env, (2) model claims match `installed`/`simulated` flags with no simulated model marketed as real, (3) one third-party host has a live-verified hook session, (4) tape verification is user-runnable, (5) onboarding runbook exists. Items 1–2 are the only true blockers; 3–5 are same-sprint achievable.
