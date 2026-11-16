# KEEL-DEPS-025: Dependabot version updates for all manifests

- **Task ID**: `KEEL-DEPS-025`
- **Status**: `READY_FOR_REVIEW`
- **Assigned Agent**: Devin
- **Last Agent**: Devin
- **Date**: 2026-11-16
- **Branch**: `devin/1794817551-dependabot`
- **Base Commit**: `aad3a7d` (`main`); delivered in the single `ci: add Dependabot version updates config` commit on this branch

## Acceptance Criteria
- [x] `.github/dependabot.yml` covers every manifest on `main`: pip (`/`), npm (`/dev-app`, `/extensions/vscode-keelway`, `/mobile`, `/sdk/typescript`, `/website`), gomod (`/sdk/go`), docker (`/`), github-actions (`/`).
- [x] Weekly schedule; minor+patch grouped per ecosystem; at most 5 open PRs per ecosystem.
- [ ] Repository owner enables Dependabot alerts and security updates (Settings → Code security). The config file only drives version updates.

## Files Modified
- `.github/dependabot.yml`: new; 5 update entries (pip, npm ×5 directories, gomod, docker, github-actions).
- `docs/agent-operations/tasks/KEEL-DEPS-025.md`: this record.
- `docs/agent-operations/ACTIVE_TASKS.md`: registry row.

## Tests Executed & Evidence
- `python -c "import yaml; d=yaml.safe_load(open('.github/dependabot.yml')); print(len(d['updates']))"`: `5` (parses; 5 entries).
- `ls dev-app/package.json extensions/vscode-keelway/package.json mobile/package.json sdk/typescript/package.json website/package.json sdk/go/go.mod Dockerfile requirements.txt`: all present on the base commit.
- No application code changed, so the pytest suite is unaffected; PR CI runs it.

## Known Risks & Blockers
- Dependabot alerts are currently disabled on this repo; that toggle needs admin access.

## Next Recommended Action
- Merge, enable alerts/security updates in Settings, then confirm Insights → Dependency graph → Dependabot lists each directory.
