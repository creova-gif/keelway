# KEEL-REL-056 — Public Install Source + ACP/Adapter Contract Tests

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / INSTALL / AGENTS` |
| **Agent** | Devin |
| **Date** | 2026-11-17 |
| **Branch** | `fix/KEEL-REL-056-public-install-acp-contract` |

## Objective
Close the last beta blocker (public install source) and run the pending
agent contract tests: real ACP agent, Cursor pinned-schema, vendor re-probe.

## Work Completed

### Public install (founder decision: open creova-gif/keelway)
- Repo flipped PRIVATE→PUBLIC via `gh repo edit` (secret sweep first:
  only detection regexes + synthetic test fixtures found).
- `website/install.sh` + `website/public/install.sh`: `KEELWAY_GIT_URL`
  now defaults to `https://github.com/creova-gif/keelway.git`
  (SOURCE_DIR/PACKAGE still take precedence).
- `tests/test_website_facts.py`: repo-URL tokens exempted for install.sh
  only (repo is intentionally public; ban still applies elsewhere).
- **Live E2E**: zero-env `install.sh` → clone public repo → venv →
  `keelway doctor` HEALTHY 10/10.

### ACP contract test (KEEL-ENG-051 follow-up)
- Registered `GeminiCliAdapter` (`gemini --acp`) and `HermesAcpAdapter`
  (`hermes-acp`, with `--check` health probe in detect()).
- `agents acp` injects adapter `acp_args` (`--acp` for gemini).
- `VALID_AGENT_HOSTS` extended for interception records;
  `render_hook_manifest` fails honestly for ACP-only hosts.
- **Live**: `hermes-acp 0.22.5` real session — initialize/session/new/
  prompt, 73 session/update events, real model reply "ACP_OK",
  stop_reason=end_turn. `session/request_permission` not observed live
  (agent emitted none — its permission config likely auto-approves);
  permission path remains fixture-verified.

### Cursor contract test (schema pinned)
- Official cursor.com/docs/hooks schema now implemented: lowercase
  `preToolUse`/`postToolUse`/`sessionStart`/`sessionEnd` under `hooks`,
  tool-name matcher, nested `permissionDecision` response (claude-code
  format), `sessionEnd` event added. Previous manifest used wrong
  capitalized keys — hooks would never have fired.
- Live delivery still blocked: `cursor-agent` requires `agent login` /
  CURSOR_API_KEY (not authenticated on this host).

### Vendor re-probe
- claude_code: still quota-blocked (UserPromptSubmit hook, 104% daily,
  resets midnight). codex_cli: usage limit until ~Nov 20.

## Tests
- 90 passed: adapters + conformance (now 6 adapters) + ACP + phase18.
- 16 passed: website_facts + phase8 + beta journey.

## Known Limits
- cursor-agent live hook delivery unverified (needs login).
- claude/codex live inference quota-gated.
- gemini --acp session not yet run live.
- PyPI publish still open (install.sh git path now works regardless).

## Next Recommended Action
Re-probe claude after midnight quota reset; cursor-agent login then
live hook-delivery test; optional PyPI publish for `pip install keelway`.
