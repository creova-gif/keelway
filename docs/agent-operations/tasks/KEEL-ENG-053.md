# KEEL-ENG-053 — ACP Content-Aware Policy: Edit Bodies Reach the Evaluator

- **STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2026-11-17
- **BRANCH**: `main`

## Objective & Acceptance Criteria

Close the KEEL-ENG-051 boundary: `session/request_permission` evaluation
saw only tool-call titles (`Approve edit: <path>`), never the proposed
edit body — so content-DLP could not fire on secrets written via edits.

- [x] `rawInput` path + body fields fold into the evaluated string
- [x] Content-DLP produces a real DENY on secrets inside proposed edits (e2e)
- [x] Command tools unchanged (command still wins, no regression)

## Implementation

`core/agents/external/acp.py::_extract_tool_call`:
- Extracts `path`/`file_path`/`filePath`/`target_file`/`filename` → `path=<v>`
- Extracts first non-empty of `content`/`contents`/`new_string`/`newString`/
  `text`/`diff`/`patch`/`body`/`edits` → appended to evaluated string
- Evaluated payload capped at `_MAX_EVALUATED_CHARS` (256 KiB)
- `command`/`cmd` still takes precedence; title used when no command and
  no body — backwards compatible.

No signature change: `permission_evaluator(tool_name, command, ticket_id)`
now receives `command` containing path+body for edit calls, so
`intercept_tool_call`'s existing DLP/scrub pipeline applies unchanged.

`tests/fixtures/fake_acp_agent.py`: `FAKE_ACP_TOOL_CALL_JSON` env override
lets tests inject arbitrary toolCall shapes (edit bodies, custom kinds).

## Tests & Evidence

- `test_acp_extract_tool_call_folds_edit_body` — path+content present in
  evaluated string; command tools unchanged.
- `test_acp_content_dlp_deny_e2e` — real `SQLiteAgentCoharnessEngine` as
  evaluator: `.env` edit containing `sk-live-EXAMPLE_DLP_LEAK_000` →
  `DENY dlp_secret_detected` → ACP `cancelled` → `stop_reason: refusal`.
- `pytest tests/test_external_agent_acp.py tests/test_m6_fault_injection_and_perf.py`
  → **18 passed**.

## Known Limits

- Folding uses the *first* matching body key — a rawInput carrying both a
  `diff` and a stray `text` note evaluates only the first found.
- Evaluated payload is capped at 256 KiB; a secret positioned beyond the
  cap would not be seen (commands are near-never that large; documented).
- This closes the *bridge* gap — an agent that never sends the body in
  `rawInput` still yields titles-only evaluation (vendor behavior, recorded).
