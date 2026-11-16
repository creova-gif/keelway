# KEEL-DEPS-025: Dependabot version updates for all manifests

- **Task ID**: `KEEL-DEPS-025`
- **Status**: `READY_FOR_REVIEW`
- **Assigned Agent**: Devin
- **Branch**: `devin/1794817551-dependabot`

## Acceptance Criteria
- [x] `.github/dependabot.yml` covers every manifest on `main`: pip (`/`), npm (`/dev-app`, `/extensions/vscode-keelway`, `/mobile`, `/sdk/typescript`, `/website`), gomod (`/sdk/go`), docker (`/`), github-actions (`/`).
- [x] Weekly schedule; minor+patch grouped per ecosystem; at most 5 open PRs per ecosystem.
- [ ] Repository owner enables Dependabot alerts and security updates (Settings → Code security). The config file only drives version updates.

## Tests Executed & Evidence
- `python -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))"`: parses.

## Known Risks & Blockers
- Dependabot alerts are currently disabled on this repo; that toggle needs admin access.

## Next Recommended Action
- Merge, enable alerts/security updates in Settings, then confirm Insights → Dependency graph → Dependabot lists each directory.
