# KEEL-SEC-057 — GitGuardian Bearer Token Remediation (Demo/Fixture Literals)

- **TASK ID**: KEEL-SEC-057
- **CURRENT STATUS**: COMPLETED
- **LAST AGENT**: Devin
- **DATE**: 2026-11-17
- **BRANCH**: `main`
- **HEAD COMMIT**: `b7ae3fd` (CI run `44009638307` — all 4 jobs green)

## OBJECTIVE & ACCEPTANCE CRITERIA

- [x] Identify the Bearer Token flagged by GitGuardian after `creova-gif/kora` went public
- [x] Confirm no real credentials were exposed (all flagged strings were synthetic demo/test fixtures — nothing to rotate)
- [x] Replace realistic-looking token literals with obviously-synthetic placeholders without breaking DLP-demo regexes or tests
- [x] Rebuild `core/dev_app_dist` so the tracked bundle no longer embeds the flagged string

## ROOT CAUSE

GitGuardian's generic "Bearer Token" detector fires on `Bearer <high-entropy-string>`. Three classes of literals qualified:

1. `website/src/components/api/ApiExplorer.tsx` — full `Bearer kw_live_7f3a1c_…` example (rest of file already used `kw_live_...` truncation)
2. `website/src/components/governance/GovernanceGuardrailsLab.tsx` — full `Bearer kw_live_9a2f0c_…` DLP-demo input
3. `sk-live-9876543210secretkey` — dev-app DLP-demo fixtures (`platformDevxApi.ts`, `platformHealingApi.ts`) + the tracked `core/dev_app_dist` bundle

## FILES MODIFIED

- `website/src/components/api/ApiExplorer.tsx`: full key → `kw_live_...` (matches file convention)
- `website/src/components/governance/GovernanceGuardrailsLab.tsx`: `kw_live_dec0de_deadbeefdeadbeefdeadbeef00` — still matches the demo's own `/kw_live_[0-9a-f]{6}_[0-9a-f]{16,}/gi` redaction regex, but `dec0de`/`deadbeef` reads as obviously synthetic
- `dev-app/src/lib/platformDevxApi.ts`, `platformHealingApi.ts`, `__tests__/phase19-shadow-cache-and-distill.test.tsx`, `__tests__/phase20-mcp-lockfile-and-bench.test.tsx`: `sk-live-9876543210secretkey` → `sk-live-EXAMPLE_DLP_LEAK_000` (still matches the `sk-(live-)?…` DLP redaction pattern)
- `tests/test_phase19_sdk_and_vscode_distill.py`, `tests/test_unified_platform.py`: same normalization
- `core/dev_app_dist/`: rebuilt via `npm run build`

## TESTS EXECUTED & EVIDENCE

- `pytest tests/test_phase19_sdk_and_vscode_distill.py tests/test_unified_platform.py tests/test_website_facts.py`: `40 passed`
- `vitest run phase19-shadow-cache-and-distill phase20-mcp-lockfile-and-bench tokens-and-badges`: `18 passed`
- `tsc --noEmit` (dev-app): clean
- Residual scan: zero `Bearer <entropy>` literals outside clearly-marked test placeholders
- GitHub Actions `44009638307`: all jobs success

## KNOWN LIMITS

- Other `ghp_*`/`sk-*`/`oidc-*` Python test fixtures remain — they contain dictionary words (`Secret`, `Test`, sequential digits) below GitGuardian's entropy threshold and were not flagged. Left intentionally; if GitGuardian re-alerts, normalize the specific flagged literal.
- The old literals persist in git history — irrelevant, they are synthetic.
- User action: mark the incident resolved in the GitGuardian dashboard (no rotation needed — the token never corresponded to a real credential).

## NEXT RECOMMENDED ACTION

Consider a `gitleaks`/`ggshield` pre-commit or CI scan so synthetic-looking secrets are caught before push.
