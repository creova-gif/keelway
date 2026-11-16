# Contributing to Keelway

Thanks for your interest in Keelway! This page is the short version; the full process lives in [`docs/engineering/DEVELOPMENT_WORKFLOW.md`](docs/engineering/DEVELOPMENT_WORKFLOW.md).

## Setup

Requires Python 3.11+.

```bash
git clone https://github.com/creova-gif/kora.git
cd kora
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp env.example .env   # optional; most tests need no keys
```

## Before you open a pull request

1. Branch from `main` using `feature/<task-id>-<desc>`, `fix/<task-id>-<desc>` or `refactor/<task-id>-<desc>`.
2. Lint: `ruff check .`
3. Engineering gates: `./scripts/verify_engineering_gates.sh`
4. Tests: `make test` (or `pytest tests/test_<feature>.py -v` while iterating).
5. Keep the [security invariants](AGENTS.md#6-mandatory-security--governance-invariants) intact: privacy fail-closed, credential redaction, sandboxed execution.
6. Never commit `.env` files, databases or credentials.
7. Record non-trivial design decisions as an ADR in [`docs/decisions/`](docs/decisions/).

AI coding agents must also follow [`AGENTS.md`](AGENTS.md).

## Reporting bugs and security issues

- Bugs and feature requests: open a GitHub issue with steps to reproduce.
- Security vulnerabilities: see [`SECURITY.md`](SECURITY.md). Do not file a public issue.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions are licensed under the [Apache License 2.0](LICENSE).
