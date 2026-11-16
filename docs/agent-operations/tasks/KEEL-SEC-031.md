# KEEL-SEC-031 — Payment Broker Env Secret Wiring

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `SECURITY / BILLING / FAIL-CLOSED` |
| **Agent** | Devin |
| **Date** | 2026-11-16 |
| **Branch** | `fix/KEEL-SEC-031-payment-secret` |

## Objective
Wire `GlobalPaymentBroker` to operator configuration. Review found the hardcoded `KORA_SOVEREIGN_PAYMENT_SECRET_2026` default is already refused by the `is_source_default` fail-closed guard — but no env var existed, so payment intents could never run even for legitimate operators.

## Acceptance Criteria
- [x] `GlobalPaymentBroker()` resolves `KEELWAY_PAYMENT_BROKER_SECRET` when no explicit `broker_secret` is passed
- [x] Env value equal to a published source default is still refused (sentinel preserved)
- [x] Unset env → source-default sentinel → `create_intent` raises `InsecureDefaultConfiguration` (unchanged fail-closed behavior)
- [x] Explicit `broker_secret=` argument behavior unchanged
- [x] `keelway pay` CLI prints a clean configuration error instead of a traceback
- [x] `env.example` documents `KEELWAY_PAYMENT_BROKER_SECRET`

## Files Modified
- `core/storage/payment_broker.py` — env resolution in `__init__`, `Optional[str]` signature
- `cli.py` — `cmd_pay` catches `InsecureDefaultConfiguration`
- `tests/test_package_c_fail_closed.py` — 3 new env-wiring tests
- `env.example` — documented variable

## Tests Executed
- `pytest tests/test_package_c_fail_closed.py tests/test_package_a_safety_negatives.py -q`: 47 passed

## Known Risks & Blockers
- Broker remains simulated (no provider rails connected); this task only fixes secret configuration, not payment processing.

## Next Recommended Action
Merge to `main`; proceed to KEEL-ENG-032 (Python lockfile).
