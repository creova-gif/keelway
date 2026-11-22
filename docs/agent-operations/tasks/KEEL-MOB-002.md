# KEEL-MOB-002 — Receipt screen for the bridge watch (Paper 08.2C)

**Status**: READY_FOR_REVIEW
**Branch**: feature/keel-mob-002-receipt-screen
**Paper source**: `Keelway — Brand Kit & Homepage` page 08, artboard 08.2C
("RECEIPT · proof verifies on-device")

## Scope

Implements the third V3 mobile flow: read-only tape receipts on the paired
phone, with merkle inclusion proofs folded **on device**.

## Changes — backend

- `core/api/auth_routes.py`: `GET /v1/phone/receipts?limit=` (≤100) — newest
  audit entries, same redacted fields as `/v1/audit`. Gated by
  `current_principal`, not `VIEW_AUDIT_LOGS` — minimal-disclosure read.
- `AuditEventResponse`: + `prev_hash` (chain row needs it; `/v1/audit` gains
  the field too — additive schema change).
- `core/security/auth.py`: `PHONE_ROUTES` += `GET /v1/phone/receipts`,
  `GET /v1/audit/merkle/root`, `GET /v1/audit/merkle/proof/{seq}` —
  read-only, consistent with the bridge-watch doctrine; the refusal matrix
  (audit list, tokens, exec, streams) is untouched.

## Changes — mobile

- `api.ts`: `PhoneReceipt`/`MerkleRoot`/`MerkleProof` types + `receipts()`,
  `merkleRoot()`, `merkleProof(seq)`.
- `services/sha256.ts`: dependency-free SHA-256 (Hermes + bun-safe) and
  `verifyMerkleProof` folding `sha256(left+right)` exactly like
  `AuditMerkleTree.verify_proof`.
- `MissionControlScreen`: Receipts section — rows `#seq · action` with
  sealed/denied chips; tap expands the 08.2C detail (exec / actor / proof /
  chain / sealed), `Verify proof on device` (fetches inclusion proof, folds
  client-side, compares to proof's root + entry hash), `Share receipt`
  via the RN Share sheet. Verify result states are honest: ok / fold-failed
  / fetch-failed.
- i18n: 15 new strings × 4 locales.

## Verification

- `pytest tests/test_phone_pairing.py`: 19/19 green — incl. new
  `test_phone_reads_receipts_and_merkle_proofs` (receipts fields, merkle
  root, per-seq proof) + the full refusal matrix still enforced.
- `mobile`: `tsc --noEmit` clean; `bun test` 12/12 — SHA-256 matches
  published vectors, fold matches the Python tree semantics.
- Not verified against a live studio or on device — recorded honestly.

## Follow-ups

- Device/simulator visual pass + live-stack E2E (verify-keelway) once a
  phone can pair to the isolated dev stack.
