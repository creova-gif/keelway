# 11 — Known Limitations (ship-honest)

These are real product truths for beta onboarding and support.

## Architectural (by design)

- **Single operator** — no user registration, orgs, SSO, or SCIM.
  Auth is per-install launch token + named role tokens.
- **Local-first persistence** — SQLite + `.keelway/` JSON; no
  managed database; scheduler/runner-queue in-memory state resets on
  restart (labeled in UI).
- **No schema migration framework** — upgrades are additive;
  snapshot DB + `.keelway/` before upgrading.
- **`keelway` governance API (:8000)** is a second surface used by
  self-hosted deploys; not all routes are first-class in the Studio UI.

## Functional gaps (tracked)

- **Conversations persist** as of P0-1 (PR #256) — `keelway_conversations`
  table + owner-scoped retrieval. Residual: API chats are owned by the
  token actor and CLI chats by `local`; cross-surface history is
  intentionally isolated.
- **`?token=` in URL** — accepted for beta. The launch URL and internal
  `/v1/platform/*` + `/v1/cluster/*` requests carry the bearer in the
  query string; it can appear in browser history and is required by the
  Studio WebSocket (no header channel exists for WS). Mitigations in
  place: the REST API always accepts `Authorization: Bearer` /
  `X-Studio-Token` headers (preferred for API clients), the CLI server
  runs with access logging off, and the compose platform runs
  `--no-access-log` so tokens are not written to request logs. Rotate
  with `keelway token create`/`revoke` if a URL is shared. Header-only
  auth (removing the query convention + deep-link token) is post-beta.
- **Ollama bridge** honors `OLLAMA_BASE_URL` as of P0-6 (PR #258);
  request timeout bounded at 30s with a 5s connect split and honest 503.
  Residual: generations slower than 30s on CPU-only hosts need
  `timeout_s=` override.
- **`keelway swarm` offline benchmark** can hang (harness event-loop
  deadlock) — do not demo; P1-1.
- **Desktop app** opens Chromium app-mode, not a signed bundle.
- **Mobile companion** pairing works; on-device fold on live stack
  pending device re-verify.

## Environment

- Host Ollama busy → LOCAL inference tests/timeouts ~120 s.
- mypy gate runs on `core/` only; `keelway/`, `keelway_core/` excluded.
