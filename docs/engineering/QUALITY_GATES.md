# Keelway — Quality Gates & Verification Matrix

> **Governing Boundary**: All code merged to `main` or deployed to production must satisfy these gates.  
> **Enforcement**: Automated via local validation scripts and GitHub Actions (`.github/workflows/ci.yml`).

---

## 1. Quality Gate Hierarchy

```
[ Gate 0: Local Pre-Commit ]
       |  - Ruff lint & syntax check
       |  - Targeted unit tests pass
       v
[ Gate 1: Pull Request CI ]
       |  - Matrix test on Python 3.11, 3.12, 3.14
       |  - Bubblewrap command sandbox isolation
       |  - Automated secret scan & credential detector
       v
[ Gate 2: Security & Governance Review ]
       |  - Air-gap & privacy fail-closed check
       |  - Error disclosure & PII redaction check
       |  - Autonomy Tier 3 approval authorization
       v
[ Gate 3: Release Live Verification Boundary ]
       |  - python -m tests.release_live_gate
       |  - Fail-closed unless every required proof passes
       v
[ Gate 4: Production Deployment ]
          - Sealed release packaging
          - Merkle audit head anchored
```

---

## 2. Gate Specifications

### Gate 0: Local Pre-Commit
Before committing or submitting a handoff, the engineer/agent must run:
```bash
# 1. Syntax & Compilation Check
python3 -m py_compile $(git diff --name-only --diff-filter=d | grep '\.py$')

# 2. Targeted Test Suite
pytest tests/test_<affected_module>.py -v
```

### Gate 1: Pull Request CI (`.github/workflows/ci.yml`)
- **Matrix Build**: Ubuntu 24.04 with Python 3.11, 3.12, 3.14.
- **Sandbox Test**: Bubblewrap sandbox installed and verified (`kernel.apparmor_restrict_unprivileged_userns=0`).
- **Full Suite**: `pytest -v` across core orchestration, models, api, security, and messaging.

### Gate 2: Security Severity & Governance Boundaries

All identified issues are triaged against explicit severity gates:

| Severity Level | Definition | Merge / Deploy Impact |
|---|---|---|
| **CRITICAL** | Air-gap breach (cloud egress of private payload), remote unauthenticated code execution, unredacted credential in tape, broken Merkle hash chain. | **Hard Block**: Merge and release strictly prohibited. Immediate hotfix required. |
| **HIGH** | Flawed RBAC permission check, missing input validation on public routes, unconfined subprocess execution, sandbox escape vector. | **Hard Block**: Cannot merge without documented authorized security exception. |
| **MEDIUM** | Missing test coverage on non-critical edge cases, sub-optimal routing fallback, performance degradation >15%. | Must be tracked with GitHub issue and assigned owner; may merge with review sign-off. |
| **LOW** | Code formatting inconsistency, typo in documentation, cosmetic log message issue. | Trivial fix; does not block merge. |

### Gate 3: Release Live Verification (`tests.release_live_gate`)
- Release gate is **fail-closed**.
- Verifies live cryptographic proofs, audit chain continuity, and packaging integrity.
- Cannot be bypassed by mocking or skipping tests.

---

## 3. Automated Gate Verification Script

To execute the entire verification pipeline locally before submitting a PR or handoff:
```bash
bash scripts/verify_engineering_gates.sh
```
This script runs syntax verification, linting, core unit tests, hybrid AI provider tests, and security invariant checks, outputting a machine-readable summary.
