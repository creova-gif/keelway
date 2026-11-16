# TASK: KEEL-BILLING-025 — Provider-neutral checkout: verified payment webhooks issue signed licences

## 1. METADATA
- **TASK ID**: KEEL-BILLING-025
- **CATEGORY**: SECURITY / API
- **CREATOR**: Justin (creova-gif)
- **ASSIGNED AGENT**: Devin
- **STATUS**: READY_FOR_REVIEW
- **TARGET BRANCH**: devin/1794818145-checkout

## 2. OBJECTIVE & MOTIVATION
Sell paid plans without committing to a payment provider yet. A verified payment event must produce an Ed25519-signed licence (from the issuer's private key, see `keelway entitlements keygen`) that customers install and check offline; refunds and cancellations must end the order.

## 3. ACCEPTANCE CRITERIA
- [x] `ProviderAdapter` boundary (`verify`, `parse` → `PaymentEvent`); no provider hard-coded. Proof: `core/billing/checkout.py`.
- [x] `paid` issues a licence that a customer `EntitlementManager` holding only the public key accepts as `ACTIVE`; a later `paid` on the same order renews from the current expiry.
- [x] Each event id is processed once, across issuer restarts (ledger on disk).
- [x] `refunded` / `cancelled` end the order; later payments on it are refused. Offline licences already issued stay valid until they expire (documented limit).
- [x] Fails closed: no/short/source-default webhook secret refuses to start; unsigned, wrongly signed or stale webhooks get 401; unknown plans and unsafe ids get 422 and stay retryable.
- [x] Tests: `tests/test_checkout.py`.
- [x] Docs: README "Licences and checkout".

## 4. AFFECTED FILES & COMPONENTS
- `core/billing/checkout.py` (new), `cli.py` (`entitlements serve-issuer`)
- `tests/test_checkout.py` (new); `tests/test_evidence_room.py`, `tests/test_runtime_truth_package_b.py` (stop scanning the random commit SHA for the banned "745")
- `README.md`

## 5. SECURITY & PRIVACY CONSIDERATIONS
- Credential handling involved: Yes. The private signing key and `KEELWAY_CHECKOUT_WEBHOOK_SECRET` stay on the issuing server; neither is a CLI argument or committed. The issuer is never mounted on the customer runtime API.
- Autonomy Tier Level: Tier 3 (issues paid entitlements).

## 6. VALIDATION & TEST PLAN
```bash
pytest tests/test_checkout.py tests/test_licence_signing.py -v
```

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-BILLING-025
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-16
- **BRANCH**: devin/1794818145-checkout

#### TESTS EXECUTED & EVIDENCE
- `ruff check .`: All checks passed
- `pytest tests/test_evidence_room.py tests/test_runtime_truth_package_b.py tests/test_checkout.py tests/test_licence_signing.py`: 26 passed
- `pytest -q` (before the two evidence-room test fixes): 1279 passed, 2 failed (the SHA-containing-"745" flake), 13 skipped
- Live: `entitlements serve-issuer` + signed `paid` then `cancelled` → 200 issued, 200 cancelled; unsigned → 401; short secret → refuses to start

#### KNOWN RISKS & BLOCKERS
- No real provider adapter yet (provider not chosen). No licence delivery (email); licences are written to `DIR/licences/`.
- `TRUSTED_LICENCE_KEYS` is empty until Sorvex Labs supplies its public key, so every licence check is still refused.

#### NEXT RECOMMENDED ACTION
- When the provider is chosen, add its adapter in `core/billing/checkout.py` (signature check + event-name mapping) with tests against the provider's documented sample payloads.
