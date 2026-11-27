# 08 — Testing & Evaluation (evidence)

## Suite inventory (this turn)

- `pytest`: **1565 tests / 212 files** collected; CI green on
  `bdab521` both legs (3.11, 3.14) — full run ~4–5 min/leg.
- `dev-app`: 25 test files, ~72 tests (`npm test`).
- `website`/`web-next`: Playwright axe WCAG 2.2 AA + perf smoke in CI.
- Quality gates in CI: ruff, mypy (2.4.1, strict_optional,
  check_untyped_defs, warn_unreachable, warn_unused_ignores),
  pip-audit, gitleaks, bubblewrap confinement, phase parity caps,
  lock-freshness, wheel+SBOM.

## Commands

```bash
python -m pytest tests/ -q                 # full suite
python -m pytest tests/test_<area>.py -v   # focused
python -m mypy                             # typecheck (pinned 2.4.1)
ruff check .                               # lint
cd dev-app && npm run build && npm test && npm run typecheck
cd website && npm run build
```

## Known flakes / environmental (documented, not regressions)

| Test | Cause | Action |
| ---- | ----- | ------ |
| `test_cli_swarm_offline_benchmark_json` | `MiroFishSwarmHarness` event-loop deadlock — hangs on clean HEAD | P1-1 fix or quarantine |
| 5 LOCAL-path inference tests | host Ollama hardcoded 11434 wedges under load (P0-6) | env guard + P0-6 |
| SSE test on this host | pre-existing env issue | verify on CI leg |
| Node-24 ESM failure | local Node 24; CI pins 22 | none |

## Beta evaluation focus

- Composed 30-step golden journey (P0-2) — the release-critical test.
- Negative paths: bad tokens, air-gap violations, sandbox escapes
  (covered), provider outage, timeout recovery.
- Any `UNVERIFIED` rows in `10-security-test-matrix.csv` re-run.
