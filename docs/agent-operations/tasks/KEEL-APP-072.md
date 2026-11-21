# KEEL-APP-072 — Inbox popover in workspace bar (Paper `19.3`, `35K-0`)

## Status
READY_FOR_REVIEW

## Delta
New `InboxPopover` shell component on `PlatformWorkspaceBar` — "what needs you" per
artboard 19.3, fed exclusively by real task state (no fabricated notifications):

- **P-10 requests** — `needs_approval` tasks → `Review` selects the task and jumps to
  the approval heading (human gate still click-only; inbox never approves)
- **Run outcomes** — `done`/`failed` tasks → `Tape ↗` opens Record (Security view)
- **Unread dot** on the trigger only when gates are pending (artboard: "rail button,
  unread dot only")
- **Honest empty state** — "Nothing needs you — no pending gates or finished runs."
- Footer states scope truthfully: "P-10 requests (actionable) and run outcomes
  (tape link). No marketing pings, ever." — security-event rows deferred until a
  real denied-event feed exists; not fabricated.

ARIA: `aria-haspopup="dialog"` + expanded state, `role="dialog"` panel, Escape +
outside-click close, dynamic label announcing pending count.

## Wiring
`App.tsx` passes `tasks`, task-select (`setActiveTaskId` + tasks section),
`handleJumpToApprovalHeading`, and `handleSelectPlatformView("security")` for Tape ↗.

## Tests
- 24 files, 122/122 vitest (2 new: rows+actions from real state, honest empty)
- `tsc --noEmit` clean; build green; `core/dev_app_dist` regenerated
