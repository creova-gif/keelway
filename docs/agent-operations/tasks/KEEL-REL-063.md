# KEEL-REL-063 — Community Files: CONTRIBUTING + CODE_OF_CONDUCT

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / COMMUNITY / DOCS` |
| **Agent** | Devin |
| **Date** | 2026-11-20 |
| **Branch** | `feature/keel-rel-063-community-files` |

## Objective
Re-land the community-file half of stale PR #59 (closed un-merged): root
`CONTRIBUTING.md` and `CODE_OF_CONDUCT.md` for the now-public repository.
SECURITY.md was not re-landed — KEEL-REL-060 already shipped a better version
(supported-versions table + disclosure policy).

## Acceptance Criteria
- [x] `CONTRIBUTING.md` exists; quickstart URL corrected to
      `creova-gif/keelway.git` / `cd keelway` (PR #59 still referenced the old
      `kora` remote)
- [x] `CONTRIBUTING.md` references real paths verified on `main`:
      `docs/engineering/DEVELOPMENT_WORKFLOW.md`, `scripts/verify_engineering_gates.sh`,
      `env.example`, `SECURITY.md`, `AGENTS.md`, `LICENSE`
- [x] `CODE_OF_CONDUCT.md` is the unmodified Contributor Covenant from PR #59

## Files Modified
- `CONTRIBUTING.md` — new (from PR #59, clone URL fixed)
- `CODE_OF_CONDUCT.md` — new (Contributor Covenant, verbatim from PR #59)
- `docs/agent-operations/tasks/KEEL-REL-063.md` — this record
- `docs/agent-operations/ACTIVE_TASKS.md` — registry row

## Tests Executed & Evidence
- All markdown-referenced paths verified present on `main` via `ls`.
- No code changed; no test impact.

## Next Recommended Action
- Point remaining stale-PR triage at #55 (Claude Code command gate) and
  #58 (checkout webhook issuer) — both are feature PRs needing review before
  landing or closing.
