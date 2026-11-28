# 12 — Agent Coordination

## Lane ownership (no shared-file collisions)

| Lane | Owns (write) | Reads |
| ---- | ------------ | ----- |
| Backend (Devin) | `core/`, `cli.py`, `keelway/`, `api/`, `deploy/`, `pyproject.toml`, `requirements*` | everything |
| Frontend (Antigravity) | `dev-app/`, `web-next/`, `web-console/`, `DESIGN.md` | `core/api/` contracts |
| AI eng (Claude) | `core/models/`, `core/opencore/`, `core/eval/`, `evals/` | gateway call sites |
| Security | `core/security/` + reviews anywhere | everything |
| QA | `tests/`, `*/e2e/`, `docs/beta/` checklists | everything |
| Release | merge + tag + deploy | — |

Overlaps are arbitrated by the release owner (Justin). Shared files
(`pyproject.toml`, `ACTIVE_TASKS.md`, `routes.py`) — one owner per PR.

## Mechanics

- Branch per work item: `feature/<id>-<slug>` or `fix/<id>-<slug>`;
  worktree per lane on the same machine
  (`git worktree add ../keelway-worktrees/<id> <branch>`).
- Commit author: `Justin Mafie
  <244837074+creova-gif@users.noreply.github.com>`; Conventional
  Commits; squash-merge PRs.
- Task IDs on the board: `KEEL-BETA-*` for this sprint; append the
  board row on a separate sync PR after merge (established pattern).
- Handoff format: AGENTS.md §4 TASK HANDOFF RECORD.

## Current in-flight

- Devin: this doc set → P0-1 (conversation persistence) → P0-6
  (Ollama bridge) → P0-3 (compose smoke) — backend lane.
