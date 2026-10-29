# Kora Technologies + Kora Labs Repository Audit Playbook

## Audit scope and evidence requirement
Collect exact repository URL, owner, visibility, default branch, HEAD SHA, last commit, license, languages, manifests, tests, CI, release tags, packages, deployment config, secrets policy, ADRs, research datasets, reproducibility scripts and provenance. For every observation, attach path and commit. Do not paste secrets.

## Discovery checklist
- [ ] Confirm organization(s), ownership and access permissions.
- [ ] Enumerate repositories and archived/forked mirrors.
- [ ] Locate mission/vision and architecture source of truth.
- [ ] Inspect README, LICENSE, NOTICE, CONTRIBUTING and CODEOWNERS.
- [ ] Review workflow files, branch protection, environments and release provenance.
- [ ] Inspect Dockerfiles, IaC, service topology and dependency locks.
- [ ] Run approved read-only security and dependency inventory.
- [ ] Find Kora Labs hypotheses, experiment manifests, data licenses and benchmark results.
- [ ] Map code and docs to white-paper assertions.
- [ ] Document ownership and licensing lineage for TNet/chacc/africa-stack references.

## Audit matrix template
| Repo | Owner | Commit | Purpose | CI/tests | Security | Research evidence | License/IP | Risk | Confidence |
|---|---|---|---|---|---|---|---|---|---|
| Kora Technologies (URL TBD) | Unknown | — | Platform | Unverified | Unverified | Unverified | Unverified | Access gap | Low |
| Kora Labs (URL TBD) | Unknown | — | Research | Unverified | Unverified | Unverified | Unverified | Access gap | Low |
| Kora Dev (URL TBD) | Unknown | — | Devtool | Unverified | Unverified | Unverified | Unverified | Access gap | Low |

## Gap scoring
Score each gap by **impact (1–5) × likelihood (1–5)**, then add an urgency flag for blocking issues. No scores should be assigned as factual without inspection.

### Initial provisional gaps (not repository findings)
- **P0 — Repository access and provenance:** prevents trustworthy engineering decisions.
- **P0 — Mission and product status reconciliation:** avoids building against an outdated plan.
- **P0 — Ownership/license mapping:** especially historic TNet/chacc references.
- **P1 — CI/security/evaluation baseline:** cannot yet assess readiness.
- **P1 — AI Core interface contracts:** define before adding many integrations.
- **P1 — Labs reproducibility contract:** essential before making technical claims.
- **P2 — Desktop, marketplace, proprietary model training:** defer pending evidence.

## Read-only audit commands (execute only on authorized clones)
```bash
git remote -v
git status --short
git rev-parse HEAD
git log -1 --format='%h %ad %s' --date=iso
find . -maxdepth 3 \( -name 'pyproject.toml' -o -name 'package.json' -o -name 'Cargo.toml' -o -name 'go.mod' -o -name 'Dockerfile*' -o -name 'LICENSE*' \) -print
find .github/workflows -maxdepth 1 -type f 2>/dev/null
```

## Required output
`REPOSITORY_INVENTORY.md`, `CURRENT_ARCHITECTURE.md`, `DEPENDENCY_AND_LICENSE_REGISTER.csv`, `SECURITY_BASELINE.md`, `RESEARCH_PROVENANCE.md`, `GAP_BACKLOG.md`, `DECISION_LOG.md`.
