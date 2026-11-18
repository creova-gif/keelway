# Release Scorecard (baseline, self-assessed — NOT release-grade evidence)

| Category | Weight | Score | Basis |
|---|---:|---:|---|
| Core E2E journeys | 20 | 4 | GJ-1 PARTIAL; never run clean-env twice |
| Correctness/reliability | 15 | 6 | 936 tests green; crash recovery unverified |
| Security/governance | 15 | 7 | fail-closed exec, RBAC, quorum, XSS closed, honest entitlements; abuse suite not executed |
| Agent dev/orchestration | 12 | 5 | team+kflow+scheduler real; AgentSpec/adapters missing |
| UX/accessibility | 12 | 7 | 5 fix commits this program; hc theme, error std, a11y tablist; no axe run |
| IDE/coding | 10 | 5 | Monaco+fs+terminal; LSP/checkpoint unproven |
| Observability/evals | 6 | 7 | runs/tapes/eval radar real |
| Performance | 4 | U | no baselines |
| Onboarding/docs | 3 | 6 | DESIGN.md + docs exist |
| Enterprise ops | 3 | 4 | token admin/RBAC real; SSO/SCIM/orgs missing |

Weighted (U→0): ~5.7/10. Gate: FAIL vs 9.5 target — expected; this is the baseline, not the release.
