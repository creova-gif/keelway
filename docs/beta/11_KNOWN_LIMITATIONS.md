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

- **Conversations do not persist** across server restart until P0-1
  lands (in-memory `InteractiveChatSession.history`).
- **`?token=` in URL** — bearer may appear in browser history on the
  launch URL; rotate with `keelway token create`/`revoke` if shared.
- **Ollama bridge** hardcodes `127.0.0.1:11434` until P0-6; set no
  `OLLAMA_BASE_URL` expectation in beta without the fix.
- **`keelway swarm` offline benchmark** can hang (harness event-loop
  deadlock) — do not demo; P1-1.
- **Desktop app** opens Chromium app-mode, not a signed bundle.
- **Mobile companion** pairing works; on-device fold on live stack
  pending device re-verify.

## Environment

- Host Ollama busy → LOCAL inference tests/timeouts ~120 s.
- mypy gate runs on `core/` only; `keelway/`, `keelway_core/` excluded.
