# Runbook — Pilot Readiness

> Owner: Sorvex Labs ops · Last verified: 2026-11-17
> Scope: what a pilot customer deploys, what honestly works, how we judge
> success, and when to exit a pilot.

## 1. What a pilot is

A pilot is 1–5 engineers on one team running Keelway locally for 2–4 weeks,
using real agents against real repositories, with Keelway governance hooks
in `enforce` mode after a trust-building `audit_only` period. The deliverable
is verifiable evidence (flight tapes, interception records, receipts) — not
a promise of production deployment.

## 2. Environment requirements

| Requirement | Verified |
|---|---|
| Python 3.11+ (3.13 tested) | ✅ |
| macOS arm64 / Linux x86_64 | ✅ (dev on macOS, CI on Ubuntu) |
| Git ≥ 2.40 | implied by clone/install path |
| Ollama with a pulled model | ✅ `qwen3.5`-family live-verified |
| Agent CLI: claude / codex / cursor-agent / hermes-acp / opencode / gemini | per-agent status in §3 |
| Network | local-first works offline; closed-weight providers need egress |

## 3. Honest capability matrix for pilots

### Ship-in-pilot (verified end-to-end)

| Capability | Evidence |
|---|---|
| `install.sh` + `keelway doctor` | clean-env verification suite, REL-049 |
| Dev app on `:7420` (10 views) | verify-keelway stack, live runs |
| Ollama local inference | live `qwen3.5` session |
| Governance hooks → `agents intercept` verdicts | adapter + conformance suites (6 adapters) |
| P-10 single-use tickets, HOLD path | **live** Hermes ACP HOLD on `git reset --hard` |
| Flight tapes + `tape verify` | CLI seal verification, REL-051 |
| Audit hash chain | unit + fault-injection tamper tests |
| Secret scanning (gitleaks CI gate) | live in CI run 44083135509+ |
| Signed release artifacts | cosign keyless on tags, REL-059 |

### Pilot with caveats (document before onboarding)

| Capability | Caveat |
|---|---|
| `claude` / `codex` governed sessions | vendor quota can gate inference; hook delivery verified |
| `cursor-agent` hooks | needs `agent login`; schema pinned from official docs |
| ACP (Hermes) sessions | HOLD verified; DENY not producible — model refuses dangerous ops pre-call |
| Content DLP over ACP | evaluator sees tool titles, not edit bodies — no content scanning yet |
| `pip install keelway` | pending founder PyPI trusted-publisher setup |
| `brew install keelway` | formula generated + verified; tap repo not yet created |
| Proprietary model adapters (OpenAI/Anthropic/Gemini) | code-verified, mock-tested; not live-verified per-model |

### Out of pilot scope (say so explicitly)

- Keelway Cloud / centralized control plane — not shipped
- Marketplace publishing, VPC deployment, no-code automation — planned
- Multi-tenant hosted governance — local single-tenant only today
- SLA-backed support — best-effort per `SUPPORT.md`

## 4. Pilot onboarding checklist

Per `EARLY_ACCESS.md` §1: install → doctor → `agents detect` →
`agents setup --mode audit_only` → governed run → `tape verify`.
Then flip `audit_only` → `enforce` after ~1 week or 20 clean verdicts.

## 5. Success metrics (2–4 week pilot)

| Metric | Target |
|---|---|
| Agent sessions under governance | ≥ 50 intercepted tool calls |
| Tape verifications run | ≥ 1/day used; 100% `SEAL VERIFIED` |
| False blocks (wrongful HOLD/DENY) | < 5% of intercepts, all reviewed |
| Missed blocks (destructive op not gated) | 0 — every miss is a P1 |
| Time-to-first-governed-run | < 15 min (onboarding journey target) |
| Pilot NPS / would-continue | qualitative, founder call |

## 6. Exit criteria

**Graduate** when: metrics in §5 met, tapes verify clean, no unresolved
P1s, customer signs off on capability matrix accuracy.

**Exit / pause** when: vendor quota or agent-side gaps make the governed
flow unusable (e.g., agent emits no permission requests for real ops —
this is a vendor limit, not fixable on our side), or a P1 governance
failure is found. Record the reason in the pilot issue.

## 7. Support during pilot

Follow `docs/runbooks/SUPPORT.md`: diagnostic bundle first, P1 security
via private advisory, everything else via GitHub issues with `KW-…`
reference threading.
