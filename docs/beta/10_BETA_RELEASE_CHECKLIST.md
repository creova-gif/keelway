# 10 — Beta Release Checklist (25 gates, mapped to evidence)

Status legend: `[x]` verified · `[~]` partial/running · `[ ]` open

## Engineering

- [x] Production build passes — dev-app vite build 2.16s; website next build clean (this turn)
- [x] Type checking and linting pass — mypy 0/297; ruff clean; tsc --noEmit clean
- [ ] Database migrations validated — N/A (no migration framework) → covered by backup/runbook note
- [x] Critical unit and integration tests pass — 1565 tests green in CI on baseline
- [~] No broken primary workflows — pending P0-2 composed-journey re-verify

## Security

- [x] Authentication and authorization tested — token/RBAC/pairing suites green
- [x] Cross-user data isolation tested — single-operator; phone-role allowlist verified
- [x] Secrets excluded from client and repository — gitleaks gate green
- [x] Rate limits and input validation verified — route guards + pydantic schemas
- [~] No known unresolved critical/high vulns — pip-audit gate green; HAL-verifier residual noted (07)

## AI reliability

- [x] Model responses and streaming validated — adapters + SSE decoder tests
- [x] Provider failures handled gracefully — fallback + routing_reason disclosure
- [x] Token and cost limits enforced — cost ledger + quota simulator
- [~] Prompt injection and tool permission tests pass — sandbox/scrub covered; dedicated injection cases P1
- [x] AI outputs evaluated against defined test cases — conformance bench + eval suites exist

## User experience

- [x] Core navigation works — dev-app 10-view shell + palette
- [x] Responsive layouts verified — axe + perf smoke in CI, 390px gate (WEB-047)
- [x] Loading and error states implemented — honest-state UI labels (DSN-005/006)
- [x] Keyboard and accessibility checks completed — axe WCAG 2.2 AA on both sites
- [x] No misleading or nonfunctional beta features — missing features documented not faked

## Deployment

- [ ] Staging smoke tests pass — P0-3 compose smoke pending
- [~] Production configuration verified — env.example + compose envs reviewed; OLLAMA_BASE_URL fix pending (P0-6)
- [x] Monitoring and error reporting active — flight tapes, audit ledger, doctor diagnostics
- [~] Backup and rollback process verified — documented in 09; live drill pending
- [ ] Beta onboarding and known limitations documented — this doc set; onboarding section pending cold-run
