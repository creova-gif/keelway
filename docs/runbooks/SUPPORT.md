# Runbook — Support Procedures (Beta / Pilot)

> Owner: Sorvex Labs ops · Last verified: 2026-11-17
> Scope: how users report problems, what we collect, how we triage.

## 1. Channels

| Channel | Use for | Visibility |
|---|---|---|
| [GitHub issues](https://github.com/creova-gif/keelway/issues) | Bugs, feature requests, install problems | Public — tell users to redact logs |
| [GitHub private advisory](https://github.com/creova-gif/keelway/security/advisories/new) | Vulnerabilities, credential leaks | Private — see `SECURITY.md` |
| Early-access thread (`KW-…` reference) | Onboarding follow-ups | Issue-tracked |

No email/phone support exists yet — do not promise one in collateral.

## 2. Diagnostic bundle (ask for this first)

When a user reports a problem, request the bundle before debugging blind:

```bash
keelway doctor --json > doctor.json
keelway harness agents detect
keelway tape list --json | head -20
```

Plus, where relevant:

- The exact command and exit code that failed
- `~/.keelway/` file listing (names only — do **not** request `.env`, vault
  contents, or DB files unless the user volunteers them)
- Hook config snippet (`.claude/settings.local.json` etc.) — **with secrets
  redacted**; these files can contain other tools' hooks

Never ask a user to post API keys, vault ciphertext, or full flight tapes
in a public issue.

## 3. Triage

| Severity | Definition | Target first response |
|---|---|---|
| P1 | Governance bypass, credential exposure, data loss, `TAMPER DETECTED` on a real store | 1 business day — private advisory path |
| P2 | Core flow broken (install, doctor, agent hooks, tape verify) | 2 business days |
| P3 | Cosmetic, docs, feature requests | Weekly triage |

P1 security reports follow `SECURITY.md`, not the public tracker.

## 4. Escalation

- Sandbox escape, verdict bypass, audit-chain forgery → treat as release-blocking;
  halt pilot rollout to new users until patched and verified.
- Vendor-side limits (model quota, agent not emitting permission requests,
  Gemini ACP EOL) → document, do not escalate to users as our bug.

## 5. Known-issues register (point users here)

Kept honest in `docs/architecture/MODEL_COMPATIBILITY_MATRIX.md` +
task docs. Highlights as of 2026-11-17:

- `pip install keelway` — PyPI publish pending founder setup.
- `brew install keelway` — formula generated (`packaging/homebrew/`),
  tap repo not yet created.
- Live ACP `DENY` evidence unavailable — Hermes refuses dangerous writes
  in planning before emitting tool calls.
- ACP permission evaluation sees tool titles/paths, not edit bodies —
  content-DLP cannot fire over ACP yet.
- Hermes does not gate credential *reads* (`cat ~/.ssh/...`) — vendor gap.
- `claude`/`codex` live inference may hit vendor quota limits.
- `cursor-agent` hook delivery needs `agent login`.
