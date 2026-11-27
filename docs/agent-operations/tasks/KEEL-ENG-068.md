# KEEL-ENG-068 — `?token=` bearer leakage mitigation (beta P0-4)

- **Status**: COMPLETED (documented-limitation path, per backlog acceptance)
- **Agent**: Devin
- **Date**: 2026-11-27
- **PR**: #259 (merged `fb86244`)

## Objective & acceptance

Backlog P0-4: "Stop bearer tokens appearing in server request logs and
document the `?token=` convention honestly." The criterion allows either
header-only refactor **or** documented limitation with log mitigation —
header-only is a deep dev-app refactor (~20 test files assert the query
convention, navigation preserves it, deep-link launch depends on it) and
the `/v1/ws/studio` WebSocket legitimately requires the query param (WS
has no header channel). Out of sprint scope → documented-limitation path.

## Work completed

- `docker-compose.yml`: platform entrypoint gains `--no-access-log` —
  uvicorn access logs would otherwise capture `?token=` on every request.
  (`cli.py` dev server already ran uvicorn at `warning`; verified live —
  a `?token=SMOKE-LEAK-TEST` probe produced no request log lines.)
- `docs/beta/11_KNOWN_LIMITATIONS.md`: expanded `?token=` entry — states
  what leaks (browser history, WS requirement), what is mitigated
  (headers always accepted server-side, access logs off in both serving
  paths), and the rotation path (`keelway token create`/`revoke`).
  Header-only auth recorded as post-beta.

## Evidence

- Container log check during P0-3 smoke: no `?token=` request lines.
- `11_KNOWN_LIMITATIONS.md` lines 23-32.
