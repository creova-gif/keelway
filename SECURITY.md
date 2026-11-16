# Security Policy

## Reporting a vulnerability

Please email **creativeinnovationspace@gmail.com** with:

- a description of the issue and its impact,
- steps to reproduce or a proof of concept,
- the affected version or commit.

Do not open a public issue or pull request for security problems. We aim to acknowledge reports within 3 business days.

## Supported versions

Only the latest `main` branch receives security fixes.

## Security design

Keelway's security invariants (privacy fail-closed routing, credential redaction, sandboxed execution, Merkle-chained audit logs) are described in:

- [`AGENTS.md` §6](AGENTS.md#6-mandatory-security--governance-invariants)
- [`docs/engineering/SECURITY_STANDARDS.md`](docs/engineering/SECURITY_STANDARDS.md)
- [`docs/SECURITY_INVARIANTS_AND_AUDIT_REPORT.md`](docs/SECURITY_INVARIANTS_AND_AUDIT_REPORT.md)
