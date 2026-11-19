### TASK HANDOFF RECORD
- **TASK ID**: KEEL-APP-045
- **TASK TITLE**: Conductor-style persistent sidebar rail (Tasks + Agents)
- **CURRENT STATUS**: VERIFIED_COMPLETE
- **LAST AGENT**: Devin
- **DATE**: 2026-11-19
- **BRANCH**: feature/keel-app-045-conductor-rail
- **HEAD COMMIT**: d9b1b60 (merge of 832b9db)

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Persistent left rail across all platform views (previously IDE-only via hideSidebar gate)
- [x] Tasks queue remains the rail's primary surface; new Agents region lists the 12 lifecycle agents with real status badges (nested aria-label="Agents" — complementary label stays "Tasks" per test contract)
- [x] Agent row click navigates to the Agents view
- [x] Record/Security context still suppresses the rail (activeSection="record")
- [x] Files/settings sections keep their context sidebars
- [x] 111/111 vitest + axe gate green; live screenshots verify rail on Marketplace + absence on Security

#### WORK COMPLETED & FILES MODIFIED
- `dev-app/src/lib/types.ts`: added SidebarAgentItem
- `dev-app/src/components/shell/DevAppShell.tsx`: AgentsRailList component; agents/onSelectAgent props; shouldRenderSidebar now persists across views; tasks+agents stacked layout in default rail
- `dev-app/src/components/platform/useUnifiedPlatformState.tsx`: expose agents
- `dev-app/src/App.tsx`: removed hideSidebar={platformView!=="ide"}; wired agents + onSelectAgent→agents view
- `dev-app/src/__tests__/unified-10view-platform.test.tsx`: scoped custom-agent assertion to heading role (name now also appears in rail)
- `core/dev_app_dist`: rebuilt

#### TESTS EXECUTED & EVIDENCE
- `npm run test`: 111/111 pass incl. 0 axe violations
- `npm run build`: tsc --noEmit + vite clean
- Live stack /tmp/keelway-verify-rail (port 59350): rail-ide.png, rail-marketplace.png, rail-security.png

#### KNOWN RISKS & BLOCKERS
- Security view still suppresses rail deliberately (forces activeSection="record").

#### NEXT RECOMMENDED ACTION
- Merge; KSTACK skills program next (contracts, execute endpoint, agent manifests).
