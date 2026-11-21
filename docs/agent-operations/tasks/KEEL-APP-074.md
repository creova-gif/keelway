# KEEL-APP-074 — Inbox security-events row kind (denied actions from the Record)

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-074
- **TASK TITLE**: Inbox third row kind — denied actions surfaced from the real Record feed
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: `feature/keel-app-074-inbox-denials`

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] The third Paper-19.3 row kind (security events) renders from the real `/v1/audit` tape — no fabricated feed; the Record already stores denial actions (`manifest_denied`, `git_local_commit_rejected`, …) via `record_audit`.
- [x] Popover fetches lazily on first open via injectable `fetchAuditEntriesFn` (defaults to `fetchAuditEntries`); denies detected via `outcome === "denied"` or denial action marker; newest first, capped at 4 rows.
- [x] Each row: `action — target`, `Record #seq · actor · timestamp`, `Tape ↗` → `onOpenRecord` (existing Record nav).
- [x] Honest states: no denials → section absent; endpoint failure → `Security events unavailable — Record endpoint unreachable` (no silent fallback).
- [x] Footer declares all three kinds: P-10 (actionable), run outcomes + denied actions (tape links), no marketing pings.
- [x] P-10 untouched: denials are read-only — no approve affordance anywhere.

#### WORK COMPLETED & FILES MODIFIED
- `dev-app/src/components/shell/InboxPopover.tsx`: `isDenialEntry` export, lazy fetch state, `Security events — from the Record` section, unavailable state, updated footer + empty-state copy.
- `dev-app/src/__tests__/shell-and-palette.test.tsx`: 2 new tests (denial rows newest-first + Tape nav; honest unavailable state); older tests given explicit empty `fetchAuditEntriesFn` to isolate from the fallback tape.
- `core/dev_app_dist/`: rebuilt.

#### TESTS EXECUTED & EVIDENCE
- `npx tsc --noEmit`: clean
- `npx vitest run`: 126 passed (24 files), incl. axe gates
- `npm run build`: clean, dist regenerated

#### KNOWN RISKS & BLOCKERS
- Denial detection is heuristic (`outcome === "denied"` ∪ action-name markers) since the tape has no dedicated denial kind field — matches how the backend actually records them.

#### NEXT RECOMMENDED ACTION
- Optional live verify pass on verify-keelway; deferred item is `--teal-accent` rename + `web-next` scaffold (still paused).
