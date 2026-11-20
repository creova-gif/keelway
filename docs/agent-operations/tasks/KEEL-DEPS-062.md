# KEEL-DEPS-062 — Dependabot Version Updates Config

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `CI / DEPENDENCIES` |
| **Agent** | Devin |
| **Date** | 2026-11-20 |
| **Branch** | `feature/keel-deps-062-dependabot` |

## Objective
Re-land the Dependabot version-updates config from stale PR #57 (closed un-merged);
weekly grouped minor+patch updates across every manifest on `main`.

## Acceptance Criteria
- [x] `.github/dependabot.yml` covers every manifest on `main`: pip (`/`),
      npm (`/dev-app`, `/extensions/vscode-keelway`, `/mobile`, `/sdk/typescript`, `/website`),
      gomod (`/sdk/go`), docker (`/`), github-actions (`/`).
- [x] Weekly schedule; minor+patch grouped per ecosystem; at most 5 open PRs per ecosystem.
- [ ] Repository owner enables Dependabot alerts and security updates
      (Settings → Code security). The config file only drives version updates.

## Files Modified
- `.github/dependabot.yml`: new; 5 update entries.
- `docs/agent-operations/tasks/KEEL-DEPS-062.md`: this record.
- `docs/agent-operations/ACTIVE_TASKS.md`: registry row.

## Tests Executed & Evidence
- YAML parses (`python -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))"`).
- All referenced manifests verified present on `main`:
  `requirements.txt`, `dev-app/package.json`, `extensions/vscode-keelway/package.json`,
  `mobile/package.json`, `sdk/typescript/package.json`, `website/package.json`,
  `sdk/go/go.mod`, `Dockerfile`, `.github/workflows/*`.
- No application code changed; PR CI covers the suite.

## Known Risks & Blockers
- Dependabot *alerts* (security) require a repo-settings toggle the config cannot set.

## Next Recommended Action
- Merge, enable alerts/security updates in Settings → Code security, then confirm
  Insights → Dependency graph → Dependabot lists each directory.
