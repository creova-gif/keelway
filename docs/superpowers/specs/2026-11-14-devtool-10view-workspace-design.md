# Keelway Local Dev Tool 10-View Unified Workspace & Website De-Scoping Design

- **Date**: 2026-11-14
- **Status**: Approved
- **Scope**: `core/platform/*`, `core/api/platform_routes.py`, `dev-app/*`, `website/*`, `tests/*`

## 1. Problem Statement & Product Intent

The **Unified 10-View Keelway Workspace** (`IDE`, `Agents`, `Project Manager`, `Product`, `Automation`, `Marketplace`, `Security`, `Documentation`, `Operations`, `No-Code Builder`) is the core local operating environment inside the **Keelway Dev Tool** (`dev-app/`, served at `:7420/app` via `keelway dev` / `keelway studio`), not a marketing widget on the public website.

Previously:
1. `website/` mounted a `/playground` route with a 10-tab scrolling widget (`UnifiedPlatformPlayground.tsx`) that wrapped the website top navigation onto two lines and showed shallow 2-line placeholders (such as Documentation).
2. Several views inside `dev-app/` (`Documentation`, `Product`, `Project Manager`, `Security`, `Automation`, `No-Code Builder`) lacked full interactive authoring, editing, scanning, and live preview workflows.

## 2. Architecture

### 2.1 Backend Workspace Hub & SQLite WAL Persistence (`core/platform/*`, `core/api/platform_routes.py`)
- Extend `SQLitePlatformStore` (`VALID_WORKSPACE_COLLECTIONS`) with `"docs"` and `"feedback"`.
- Extend `UnifiedWorkspaceHub` with:
  - Full Markdown `docs` CRUD (`list_docs`, `upsert_doc`) seeded with rich Diataxis guides (Tutorial, How-To, Reference, Explanation) and 1-click PRD/Sprint doc synchronization.
  - `update_issue` (`PATCH /v1/platform/pm/issues/{issue_id}`) persisting status, priority, sprint, description, dependencies, assignee, and PRD links.
  - `list_feedback` / `create_feedback` (`GET/POST /v1/platform/product/feedback`).
  - `scan_workspace_security` (`POST /v1/platform/security/scan`) running `MarketplaceSecurityScanner` + secret redaction checks on arbitrary workspace manifests/files.

### 2.2 Full-Depth 10-View Keelway Dev Tool (`dev-app/src/`)
All 10 views share project path, git branch, active model, composer draft, `Builder` / `Guided Non-Coder` mode, and `P-10` human-only gates, and are reachable from both `PlatformWorkspaceBar` and `⌘K` `CommandPalette`:
1. **IDE**: Tasks, split diff review, inline `P-10` human gate, AST file/symbol explorer, Seatbelt sandbox terminal.
2. **Documentation (`DocumentationWorkspaceView.tsx`)**: Split-pane Diataxis Markdown Knowledge Base & Editor (`Reader` / `Split Editor` / `Markdown`), `+ New Document`, `Save Document`, and `Sync Doc from Active PRD & Sprint`.
3. **Product (`ProductWorkspaceView`)**: `+ Author New PRD` form, dynamic acceptance-criteria builder, interactive RICE calculator (`Reach * Impact * Confidence / Effort`), customer feedback intake, and `Generate Sprint Issues in PM`.
4. **Project Manager (`ProjectManagerView`)**: `List View` + 5-column `Kanban Board` (`Backlog`, `Todo`, `In Progress`, `In Review`, `Done`), sprint progress bar, inline Issue Detail Inspector, and `Delegate to Agent`.
5. **Agents (`AgentsWorkspaceView`)**: 12 lifecycle agents, coordinated teams, custom agent forge, plus interactive **Agent Session Supervisor & `keelway.agent/v1` Manifest Inspector**.
6. **Automation (`AutomationWorkspaceView`)**: Multi-step KFlow DAG builder (custom step list with agent + `P-10` gate per step), step execution logs, and failed-node retry.
7. **Marketplace (`MarketplaceWorkspaceView`)**: Search + 7-category + publisher-tier filter, commercial purchase/install SHA-256 + SPDX receipt display, installed extension config editor, and pre-publish security scanner.
8. **Security (`SecurityWorkspaceView.tsx`)**: Interactive `SOC2` / `HIPAA` / `ISO27001` / `GDPR` compliance posture evaluator, live workspace secret/AST vulnerability scanner, retention/RBAC controls, and embedded `RecordAuditLedger`.
9. **Operations (`OperationsWorkspaceView`)**: Interactive GPU cluster workload scheduler (`/v1/cluster/schedule`), canary traffic promotion/rollback, node drain/restore, BYOM compliance verifier, and creator settlement ledger.
10. **No-Code Builder (`NoCodeBuilderView`)**: Natural-language + template app synthesizer with an **Interactive Live App Preview** (interactive form + live submission preview table + `P-10` publish gate) alongside synced PRD, PM issues, and KFlow DAG.

### 2.3 Public Website De-Scoping (`website/`)
- Remove `website/src/app/playground` and `UnifiedPlatformPlayground.tsx`.
- Configure permanent `308` redirect `/playground` → `/` in `website/next.config.ts`.
- Keep `Header.tsx` primary navigation single-row and crisp (`Marketplace`, `Models & OpenCore`, `Routing & Governance`, `Pricing`, `Docs`, `API Reference`), and route all Dev Tool CTAs cleanly to `/#quickstart` and `/docs`.
