# Keelway Screen Inventory — Implemented × Designed × Needed

> KEEL-DSN-001 · 2026-11-22 · Source of truth for the Phase-2 design backlog and
> Phase-4 implementation mapping. Statuses: **shipped** (in `main`), **artboard**
> (Paper), **spec** (Paper interface-specs row only), **missing** (no design),
> **absent** (not implemented anywhere).

Legend: Paper file `01M7T488WTKN3AQNQ2K9DB40TN`. All views verified live on the
isolated verify-keelway stack 2026-11-22 (evidence `/tmp/keelway-qa-evidence/`).

## A. App shell & chrome

| Surface | Code | Backend | Paper | Gap / note | Phase |
|---|---|---|---|---|---|
| View rail + workspace bar + status bar (10 views) | `DevAppShell.tsx`, `PlatformWorkspaceBar.tsx` | `/v1/platform/*` hydration, `/v1/agent` | ✅ artboard 10.1 | Shell rules in Paper match shipped decongestion; verify pixel parity in P4 | 4 |
| Golden Thread journey breadcrumb | `GoldenThreadJourneyBar.tsx` | task/run state | ✅ implied by 10.1 journey chip | Artboard shows `JOURNEY: gate #1206 awaits you` — parity-check text format | 4 |
| Command palette | in-app (cmd-k) | mixed | ❌ missing | Design needed | 2/3 |
| Onboarding modal (in-app, 2-step) | `App.tsx` + onboarding component | setup/doctor endpoints | ❌ missing | Paper "03 Onboarding" covers *site* pages, not this modal | 2 |
| Review-changes drawer | `TasksDrawers.tsx` (`ReviewChangesContent`) | diff/keep-revert APIs | ❌ missing | Design needed | 3 |
| Live execution drawer | `LiveExecutionDrawer.tsx` | SSE execution stream | ❌ missing | Design needed | 3 |
| Mobile companion mode | `App.tsx` (`companionTab`, `effectiveMobileCompanion`) | same | partial (page 08) | Responsive contract needed for workspace surfaces | 3 |

## B. IDE group (rail sections: tasks · files · record · settings)

| Screen | Code | Backend | Paper | Gap | Phase |
|---|---|---|---|---|---|
| Tasks — live agent run lane + P-10 card | `TasksWorkspace.tsx`, `P10ApprovalCard.tsx`, `AgentComposer.tsx` | `/v1/agent` tasks, P-10 approve/deny, SSE | spec only (13.3) | Flagship working surface has no dedicated artboard — **highest-priority gap** | 2 |
| P-10 approval card — state family (pending/allowed-once/allowed-always/denied/edited/expired) | `P10ApprovalCard.tsx` | P-10 gate API | ❌ missing | Safety-critical component; needs all 6+ states artboarded | 2 |
| Files — tree + editor + tabs + footer | `FilesWorkspace.tsx`, `FilesExplorerSidebar.tsx`, `FilesDiffAndCommit.tsx` | `/v1/files/*` | ✅ artboard 12.1 | Compare detail (editor chrome, tab bar, footer contract) | 4 |
| Record — audit ledger + inspector + chain banner + Merkle expander | `RecordAuditLedger.tsx`, `RecordEntryInspector.tsx` | audit ledger, inclusion proofs | ✅ artboard 10.2 | Compare detail; keep `data-callout-variant` contract | 4 |
| Settings — overview + IA | `SettingsWorkspace.tsx` | mixed | ✅ 17.1 anatomy (`2AQ-0`) | Rail + panel grammar designed | — |
| Settings · Permissions (manifest table, kill-switch, grant rule) | `settings/SettingsPermissionsPanel.tsx` | `/v1/agents/registry`, toggle | ✅ 17.2 (`2CG-0`) | Designed | — |
| Settings · Models | `settings/SettingsModelsPanel.tsx` | model registry/BYOM | spec only | Needs artboard 17.4 | 2 |
| Settings · Governance (DLP, persistence, key verify) | `settings/SettingsGovernancePanel.tsx`, `SettingsKeyMintModal.tsx` | `/v1/governance/*` | ✅ 17.3 (`2EL-0`) incl. mint modal | Designed | — |
| Settings · Network | `settings/SettingsSystemPanels.tsx` | egress posture | spec only | Needs artboard 17.5 | 2 |
| Settings · Appearance (theme/density/locale) | `settings/SettingsSystemPanels.tsx` | local prefs | spec only | Needs artboard 17.6 | 2 |
| Settings · Labs | `settings/SettingsSystemPanels.tsx` | feature flags | spec only | Needs artboard 17.7 | 2 |
| Settings · General | `settings/SettingsSystemPanels.tsx` | local prefs | spec only | Needs artboard 17.8 | 2 |
| Settings · Keyboard (shortcuts) | `settings/SettingsSystemPanels.tsx` | local prefs | spec only | Needs artboard 17.9 | 2 |

## C. Platform views (rail sections 2–10)

| Screen | Code | Backend | Paper | Gap | Phase |
|---|---|---|---|---|---|
| Agents — registry grid + lifecycle + run detail | `AgentsWorkspaceView.tsx` | `/v1/agents/*` | run detail ✅ 12.4; registry grid spec only | Registry list artboard needed | 2/4 |
| Project Manager — kanban/delegation board | `PmAndProductViews.tsx` | PM data | spec only | Needs artboard | 2 |
| Product — PRDs / roadmap | `PmAndProductViews.tsx` | product data | spec only | Needs artboard | 2 |
| Automation — KFlow DAGs, workflow runs, autopilot | `AutomationAndOpsViews.tsx`, `CyclicKflowAndAutopilotPanel.tsx`, `BidirectionalKflowStudioPanel.tsx` | `/v1/kflow`, autopilot | spec only | Needs artboard | 2 |
| Marketplace — catalog, trust, install, publish, settlement | `MarketplaceAndDocsViews.tsx` | `/v1/marketplace/*` | ✅ artboard 12.5 | Compare detail (install/publish RBAC gates shipped SEC-065/066) | 4 |
| Security — permissions surface + safety mesh | `SecurityWorkspaceView.tsx`, `FormalSafetyAndEdgeMeshPanel.tsx`, `VaultAndWebhooksPanel.tsx` | vault, webhooks, safety | spec only | Needs artboard | 2 |
| Documentation — docs browser | `DocumentationWorkspaceView.tsx` | docs index | spec only | Needs artboard | 2 |
| Operations — deployments, nodes, tape verify, settlement | `AutomationAndOpsViews.tsx` | ops/cluster APIs | ✅ artboard 12.2 | Compare detail | 4 |
| No-Code Builder — workflow canvas | `NoCodeBuilderView.tsx` | builder APIs | ✅ artboard 12.6 | Compare detail | 4 |

## D. Specialist panels (in-view, designed only if they outgrow current treatment)

`AgentCoharnessAndCiGatePanel`, `FlightTapeDebuggerPanel`,
`FlightTapeScrubberAndRadar`, `GoldenEvalScorecardPanel`, `KBrainMemoryGraphPanel`,
`KHubAirgapMirrorPanel`, `KSpacesCrdtAndKflowPanel`, `LangGraphMigratorPanel`,
`McpInspectorPanel`, `McpLockfileAndBenchPanel`, `QuotaAndPricingSimulatorPanel`,
`ShadowCacheAndDistillationPanel`, `SiemAndObservabilityPanel`,
`StepDebuggerAndBridgePanel`, `StructuredOutputAndSelfHealingPanel`,
`EnterpriseIdentityAndQuorumPanel`, `CycloneDxSbomPanel` — all shipped, all
spec-only or absent in Paper. Phase-2 batch: artboard the parent view first;
panels inherit the section template unless individually flagged.

## E. Missing / net-new surfaces

| Surface | Status | Notes | Phase |
|---|---|---|---|
| Billing / tier management | partial (workspace-bar tier switcher only) | In scope now per owner decision. Must resolve 4-tier (app) vs 5-tier (website) canonical set; design plan/usage/seats/invoices/receipts states | 2 |
| State matrix — every view × {empty, loading, error, offline, denied, P-10-pending} | scattered/half-designed | One dedicated Paper page; currently each view improvises | 3 |
| Responsive contract — workspace at <1024px | mobile companion exists, undocumented | Define which views collapse to companion vs stay desktop-only | 3 |
| Auth/sign-in inside app context | magic-link stub on website only | App is token-gated today; design the in-app auth surface if it ships | 3+ |
| Dashboard/home inside app | absent | Is there a "home" beyond the 10 views? Open question for Phase-2 IA pass | 2 |

## F. Marketing surfaces (parity check only — already both-sided)

Website v3 routes (`/`, `/about`, `/product`, `/pricing`, `/changelog`,
`/contact`, `/sign-in`, 404) shipped and artboarded on Paper pages 01/03/09.
Phase 4 includes a parity sweep against the live deployment
(`kora-sable.vercel.app`), not a redesign.

## Phase-2 design queue (owner-approved order)

1. **Settings** — 17.1–17.3 done (anatomy, Permissions, Governance+mint modal); remaining: Models (17.4), Network (17.5), Appearance (17.6), Labs (17.7), General (17.8), Keyboard (17.9)
2. **P-10 approval card** — full state family
3. **Tasks run lane** — flagship surface artboard
4. **Onboarding modal** — in-app 2-step flow
5. **Automation / Security / Documentation / PM / Product / Agents registry**
6. **Billing / tier management**
7. **Command palette, drawers (review-changes, live-execution)**
8. **State matrix page** (Phase 3 boundary)
