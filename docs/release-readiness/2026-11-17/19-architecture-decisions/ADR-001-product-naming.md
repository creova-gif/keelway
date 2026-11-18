# ADR-001: Product Naming — Kora vs Keelway

Status: DECIDED — Option 1, **Keelway canonical** (owner decision OD-1, 2026-11-18)
Date: 2026-11-17

## Context
Repository and package paths are named `kora`; product UI, README ("Keelway v1.1.0"), env vars (`KEELWAY_*`), and CLI (`keelway`) use `Keelway`. Mass rename is forbidden without owner approval.

## Options
1. Canonicalize on **Keelway** (user-facing direction; requires repo/package migration plan).
2. Canonicalize on **Kora** (repo-consistent; requires product/UI rename).
3. Dual-name policy: Kora = platform/repo codename, Keelway = product name (documented mapping).

## Decision
**Option 1 — Keelway canonical** (owner decision OD-1, 2026-11-18).
The user-facing product name wins; `kora` migrates to `keelway` as one versioned
migration tracked under `docs/agent-operations/tasks/KEEL-REL-061.md`.
Until the migration lands, the `kora`/`keelway` mix stays and no agent may
mass-rename — the guardrail below still applies.

## Consequences
The migration must cover — as one versioned migration, not piecemeal renames:
package name, repo URL (`creova-gif/kora`), binary/CLI entry, API namespace,
env var prefix, deployment domain (`kora-sable.vercel.app`), and all docs.
Repo URL redirects make the old clone URL keep working, but remotes should be
updated in the same release window.
