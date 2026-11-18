# KEEL-REL-061 — Kora → Keelway Canonical Rename Migration

| Field | Value |
|---|---|
| **Status** | `QUEUED` |
| **Category** | `RELEASE / BRANDING / MIGRATION` |
| **Agent** | Devin (queued for next agent) |
| **Date** | 2026-11-18 |
| **Branch** | `rename/KEEL-REL-061-kora-to-keelway` (not yet created) |
| **Decision** | `docs/release-readiness/2026-11-17/19-architecture-decisions/ADR-001-product-naming.md` — OD-1, Option 1: Keelway canonical |

## Objective
Execute the owner-approved rename (ADR-001, Option 1): `kora` → `keelway` as
the canonical name across the product surface, as **one versioned migration**.
Per ADR-001's guardrail, no piecemeal renames — every surface lands in the
same release window.

## Scope (all required — one migration)
- **Repo**: rename GitHub repo `creova-gif/kora` → `creova-gif/keelway`
  (GitHub auto-redirects the old URL; update remotes in the same window).
- **Package / wheel / PyPI**: package name `kora` → `keelway`; PyPI project,
  `pip install` docs, cosign/Homebrew artifacts regenerated under new name.
- **Binary / CLI**: `keelway` command already canonical — verify nothing
  exposes `kora` to users (`kora` console scripts, `kora` SDK package).
- **API namespace**: internal `/v1` is name-agnostic; verify no `kora` in
  public endpoint names, headers (`X-Keelway-*` already canonical), or tokens.
- **Env var prefix**: `KEELWAY_*` already canonical — confirm no `KORA_*` vars
  exist (check `.env.example`, deploy configs).
- **Deployment domain**: `kora-sable.vercel.app` → `keelway-*.vercel.app`
  (Vercel project rename or new project + domain cutover).
- **Storage / local state**: `~/.kora/` or `kora` DB paths — provide
  migration/symlink so existing installs keep working, or document the reset.
- **Docs**: README, website, `docs/`, AGENTS.md deployment URL, task board.

## Acceptance criteria
1. `grep -ri 'kora'` returns only documented legacy/redirect references —
   no user-facing `kora` remains (a checklist diff script in CI or the task).
2. Install path verified clean-env: `pip install keelway` (or install URL)
   works; old `kora` references redirect, not break.
3. Website + Vercel deploy respond on the keelway domain; old domain redirects.
4. Existing `.keelway/` workspaces unaffected; any `kora` local-state path
   migrated or documented.
5. All suites green: `pytest`, `tsc`, dev-app build, studio-css-check.
6. Docs + this task updated; ADR-001 consequence checklist checked off.

## Out of scope
- Renaming Kora-specific third-party artifacts beyond this repo's control
  (list them in the handoff if discovered).

## Security / integrity constraints
- Do not rename until repo-level rename plan is approved — the ADR requires
  one versioned migration.
- No hardcoded credential changes bundled into the rename diff.
