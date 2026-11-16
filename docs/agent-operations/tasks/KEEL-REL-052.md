# KEEL-REL-052 — Onboarding Runbook & Early-Access Fulfillment

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / OPS / DOCS` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `docs/KEEL-REL-052-onboarding-runbook` |

## Objective
Release gap #5: no documented path from early-access submission → install → governed run → evidence verification, and no ops process behind `/api/early-access`.

## Implementation
- `docs/runbooks/EARLY_ACCESS.md`: 6-step developer onboarding table (install → doctor → detect → `agents setup` → governed run → `tape verify`), intake path documentation (rate limit, GitHub-issue vs log fallback, env vars `EARLY_ACCESS_GH_TOKEN`/`EARLY_ACCESS_GH_REPO`), triage SLA table, per-submission fulfillment checklist with honest capability mapping, diagnostics table, and tamper-response procedure.

## Evidence
- Intake code path verified by reading `website/src/app/api/early-access/route.ts` (validation, rate limit, GH issue creation, JSON-log fallback, reference ID).
- Onboarding commands all live-verified this session: `install.sh` (REL-049), `agents setup` (REL-050), `tape verify` incl. tamper detection (REL-051).

## Known Risks (documented, not fixed)
- No-token intake loses submissions to logs — flagged as P1 config requirement.
- Per-instance rate limiter resets on serverless cold starts.
- Triage SLAs are proposed; founder to confirm.

## Next Recommended Action
Remaining release gaps: website a11y/perf CI, Studio empty/error-state audit, simulated-model badges in UI, KEEL-PROD-041 weights decision.
