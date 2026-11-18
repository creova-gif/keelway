# ADR-001: Product Naming — Kora vs Keelway

Status: OWNER_DECISION_REQUIRED
Date: 2026-11-17

## Context
Repository and package paths are named `kora`; product UI, README ("Keelway v1.1.0"), env vars (`KEELWAY_*`), and CLI (`keelway`) use `Keelway`. Mass rename is forbidden without owner approval.

## Options
1. Canonicalize on **Keelway** (user-facing direction; requires repo/package migration plan).
2. Canonicalize on **Kora** (repo-consistent; requires product/UI rename).
3. Dual-name policy: Kora = platform/repo codename, Keelway = product name (documented mapping).

## Decision
Pending owner. Guardrail: no agent may mass-rename; the `kora`/`keelway` mix stays until OD-1 resolves.

## Consequences
Any rename must cover: package name, binary, API namespace, env var prefix, domains, docs — as one versioned migration.
