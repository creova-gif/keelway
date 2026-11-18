# Data & Migrations

- Persistence: JSON files under `.keelway/` (workspaces, runs, tapes, manifests, tokens hash-store) + `core/storage/`.
- In-memory: KFlow registry, FlowScheduler schedules, runner job queue — reset on restart (UI labeled).
- No ORM, no Alembic, no migration framework. Schema evolution = file format changes; no replay/rollback path defined.
- Release implication: "migration path unknown" → per master prompt, blocks release until persistence contract is formalized.
