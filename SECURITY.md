# Security Policy

Keelway is a governance and audit platform — security reports get priority handling.

## Supported Versions

| Version | Supported |
|---|---|
| `main` branch | Yes |
| Latest release tag | Yes |
| Older tags | Best effort — please upgrade first |

## Reporting a Vulnerability

**Do not open a public issue for a vulnerability.**

Use [GitHub private vulnerability reporting](https://github.com/creova-gif/keelway/security/advisories/new)
for this repository. That creates a private advisory visible only to
maintainers — we can coordinate disclosure and credit there.

If you cannot use GitHub advisories, open a minimal public issue saying
you have a security report (no details) and we will establish a private
channel.

## What to include

- Affected component / file path
- Reproduction steps or proof of concept
- Impact assessment (what an attacker gains)
- Whether the issue touches: credential handling, audit-chain integrity,
  sandbox confinement, privacy fail-closed routing, or P-10 approvals —
  these are priority surfaces.

## Response expectations

We are a small team and do not promise fixed SLAs, but for reports on the
priority surfaces above we aim to acknowledge within 48 hours. Lower-impact
reports are triaged weekly.

## Scope notes

- Secrets committed to this repo are scanned in CI (gitleaks). If you find
  a *real* credential in history, report it privately — do not test it.
- Demo/fixture keys shaped like `kw_live_...`, `sk-live-EXAMPLE_*`, or
  `dec0de`/`deadbeef` placeholders are intentional test data, not leaks.
- Audit tapes are tamper-*evident* (unkeyed SHA-256 recompute). An attacker
  with write access to the store can re-seal modified rows — that is a
  documented limitation, not a bug; signed receipts and HMAC-keyed exports
  are the evidentiary path.
