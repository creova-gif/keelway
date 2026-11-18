# Repository Map

| Area | Path | Role |
|---|---|---|
| Core API + app | `core/` (api, agents, kflow, orchestration, runner, security, storage, sync, system, billing, kbrain, kspaces, kstack, khub, models, sdk, eval, plugins, pilot) | FastAPI monolith, 159 routes |
| Studio IDE | `core/studio/` | Vanilla JS + Monaco + Tailwind-built CSS; 9 rail sections + Labs drawer |
| Web console | `web-console/` | Lightweight ops console at /console, /web-console |
| CLI (product) | `cli.py` | 56 subcommands, entry `cli:main` |
| CLI (reference) | `keelway_core/` | Separate package, explicit-confirm design |
| Packaging | `keelway/` | Additional product package surface |
| Website | `website/` | Marketing/docs pages |
| Mobile | `mobile/` | Companion app |
| Tests | `tests/` | 936 tests at baseline |
| Evals | `evals/`, `evaluations/` | Golden probes |
| Deploy | `deploy/` | Packaging/deploy assets |
| Docs | `docs/` | Design + this audit |
| Automation | `scripts/`, `bin/`, `examples/`, `research/` | Tooling |

Auth: token-based principal w/ RBAC (`core/security/rbac.py`: owner/admin/engineer/auditor/phone). Storage: file JSON under `.keelway/`. No DB migrations system.
