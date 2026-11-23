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
| Command palette | in-app (cmd-k) | mixed | ✅ 18.3 (`2RP-0`) | Designed — actions ranked, P-10 first | — |
| Onboarding modal (in-app, 2-step) | `App.tsx` + onboarding component | setup/doctor endpoints | ✅ 18.3 (`2RP-0`) | Designed — provenance markers kept | — |
| Review-changes drawer | `TasksDrawers.tsx` (`ReviewChangesContent`) | diff/keep-revert APIs | ✅ 18.5 (`2WD-0`) | Designed — keep/revert receipt note | — |
| Live execution drawer | `LiveExecutionDrawer.tsx` | SSE execution stream | ✅ 18.5 (`2WD-0`) | Designed — lens on the same ledger | — |
| Mobile companion mode | `App.tsx` (`companionTab`, `effectiveMobileCompanion`) | same | ✅ page 08 contract wired | Responsive contract landed (APP-078): no terminal/shell, no composer, 44px tabs; RN offline read-only (MOB-003) | — |

## B. IDE group (rail sections: tasks · files · record · settings)

| Screen | Code | Backend | Paper | Gap | Phase |
|---|---|---|---|---|---|
| Tasks — live agent run lane + P-10 card | `TasksWorkspace.tsx`, `P10ApprovalCard.tsx`, `AgentComposer.tsx` | `/v1/agent` tasks, P-10 approve/deny, SSE | ✅ 18.1 (`2O0-0`) | Designed — run lane + flight tape context | — |
| P-10 approval card — state family | `P10ApprovalCard.tsx` | P-10 gate API | ✅ 18.1 (`2O0-0`) | pending/approved/denied/expired artboarded; allow-once vs allow-always + edited variants fold into approve action copy | — |
| Files — tree + editor + tabs + footer | `FilesWorkspace.tsx`, `FilesExplorerSidebar.tsx`, `FilesDiffAndCommit.tsx` | `/v1/files/*` | ✅ artboard 12.1 | Compare detail (editor chrome, tab bar, footer contract) | 4 |
| Record — audit ledger + inspector + chain banner + Merkle expander | `RecordAuditLedger.tsx`, `RecordEntryInspector.tsx` | audit ledger, inclusion proofs | ✅ artboard 10.2 | Compare detail; keep `data-callout-variant` contract | 4 |
| Settings — overview + IA | `SettingsWorkspace.tsx` | mixed | ✅ 17.1 anatomy (`2AQ-0`) | Rail + panel grammar designed | — |
| Settings · Permissions (manifest table, kill-switch, grant rule) | `settings/SettingsPermissionsPanel.tsx` | `/v1/agents/registry`, toggle | ✅ 17.2 (`2CG-0`) | Designed | — |
| Settings · Models | `settings/SettingsModelsPanel.tsx` | model registry/BYOM | ✅ 17.4 (`2H0-0`) | Designed — local runtime, weights, connectors, 4D simulator | — |
| Settings · Governance (DLP, persistence, key verify) | `settings/SettingsGovernancePanel.tsx`, `SettingsKeyMintModal.tsx` | `/v1/governance/*` | ✅ 17.3 (`2EL-0`) incl. mint modal | Designed | — |
| Settings · Network | `settings/SettingsSystemPanels.tsx` | egress posture | ✅ 17.5 (`2JZ-0`) | Designed — posture, air-gap lock, SC-7 checklist | — |
| Settings · Appearance (theme/density/locale) | `settings/SettingsSystemPanels.tsx` | local prefs | ✅ 17.6 (`2LS-0`) | Designed — combined light-panels board | — |
| Settings · Labs | `settings/SettingsSystemPanels.tsx` | feature flags | ✅ 17.6 (`2LS-0`) | Designed — combined light-panels board | — |
| Settings · General | `settings/SettingsSystemPanels.tsx` | local prefs | ✅ 17.6 (`2LS-0`) | Designed — combined light-panels board | — |
| Settings · Keyboard (shortcuts) | `settings/SettingsSystemPanels.tsx` | local prefs | ✅ 17.6 (`2LS-0`) | Designed — combined light-panels board | — |

## C. Platform views (rail sections 2–10)

| Screen | Code | Backend | Paper | Gap | Phase |
|---|---|---|---|---|---|
| Agents — registry grid + lifecycle + run detail | `AgentsWorkspaceView.tsx` | `/v1/agents/*` | run detail ✅ 12.4; registry grid ✅ artboard 12.7 (new 2026-11-23) | Registry list artboard landed — compare detail | 2/4 |
| Agents — Home · Overview dashboard | new surface, no code counterpart yet | mixed (reads existing APIs) | ✅ artboard 12.8 (new 2026-11-23) | **SIGNED OFF 2026-11-23** — answers "Dashboard/home inside app" (section E); approved for Phase-4 implementation | 2/4 |
| Agents — agent profile | new surface, no code counterpart yet | `/v1/agents/*` | ✅ artboard 12.9 (new 2026-11-23) | **SIGNED OFF 2026-11-23** — profile view for a single agent (run history, permissions, cost); approved | 2/4 |
| Agents — agent builder / creation flow | new surface, no code counterpart yet | `/v1/agents/registry` | ✅ artboard 12.10 (new 2026-11-23) | **SIGNED OFF 2026-11-23** — creation flow for registering a new agent, backed by the shipped AgentSpec v1 compiler; approved | 2/4 |
| Project Manager — kanban/delegation board | `PmAndProductViews.tsx` | PM data | ✅ 18.4c (`3X9-0`, split from `2TC-0` 2026-11-23) | Designed — lanes + delegated markers; now its own spacious board, not combined | — |
| Product — PRDs / roadmap | `PmAndProductViews.tsx` | product data | ✅ 18.4c (`3X9-0`) | Designed — folded into Project Manager board | — |
| Automation — KFlow DAGs, workflow runs, autopilot | `AutomationAndOpsViews.tsx`, `CyclicKflowAndAutopilotPanel.tsx`, `BidirectionalKflowStudioPanel.tsx` | `/v1/kflow`, autopilot | ✅ 18.4a (`3WS-0`, split from `2TC-0` 2026-11-23) | Designed — DAG list + P-10-locked node; now its own board | — |
| Marketplace — catalog, trust, install, publish, settlement | `MarketplaceAndDocsViews.tsx` | `/v1/marketplace/*` | ✅ artboard 12.5 | Compare detail (install/publish RBAC gates shipped SEC-065/066) | 4 |
| Security — permissions surface + safety mesh | `SecurityWorkspaceView.tsx`, `FormalSafetyAndEdgeMeshPanel.tsx`, `VaultAndWebhooksPanel.tsx` | vault, webhooks, safety | ✅ 18.4b (`3WZ-0`, split from `2TC-0` 2026-11-23) | Designed — posture/scan/chain rows; now its own board | — |
| Documentation — docs browser | `DocumentationWorkspaceView.tsx` | docs index | ✅ 18.4d (`3XG-0`, split from `2TC-0` 2026-11-23) | Designed — repo-docs list + search index; now its own board | — |
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
| Billing / tier management | partial (workspace-bar tier switcher only) | ✅ 18.2 (`2PV-0`) — plan/usage/settlement designed. **RESOLVED 2026-11-23**: app and website both have 4 tiers (Community/BYOM/Pro/Enterprise); the "5-tier" figure was a stale README claim, fixed in PR #218. The Paper board itself was also corrected (was showing a 3rd, wrong set: Solo/Pro/Enterprise with no BYOM) | — |
| State matrix — every view × {empty, loading, error, offline, denied, P-10-pending} | ✅ 18.4e (`3XK-0`, split from `2TC-0` 2026-11-23) — cross-view render contract designed (empty/loading/error/offline/denied/P-10-pending × never-rules); now its own standalone board | — |
| Responsive contract — workspace at <1024px | ✅ wired + documented | Companion = watch/gates/receipts only: Tasks inline-review, Record, Status, Approvals; Files/Terminal/composer stay desktop (APP-078) | — |
| Auth/sign-in inside app context | magic-link stub on website only | App is token-gated today; design the in-app auth surface if it ships | 3+ |
| Dashboard/home inside app | **SIGNED OFF 2026-11-23** — artboard 12.8 "Home · Overview" answers this; approved for Phase-4 implementation planning alongside 12.9/12.10 | Home surface sitting above IDE in the rail, surfacing attention-required items/gates/cost across every view | 2 |
| New developer → first gate journey | missing → **artboard added 2026-11-23** | ✅ page 20 artboard 20.1 (`3MP-0`) — end-to-end journey diagram, no clickable prototype (explicitly not required) | — |
| Sealed agent → marketplace settlement journey | missing → **artboard added 2026-11-23** | ✅ page 20 artboard 20.2 (`3OG-0`) — includes corrected 80/20 Enterprise Solution Partner split, verified against `MARKETPLACE_PUBLISHER_SPLITS` in `pricing.ts` | — |
| Desktop app — per-OS native chrome (macOS/Windows/Linux) | **SIGNED OFF 2026-11-23** — explicit product direction to override page 11's own "never ships OS-specific chrome" rule | ✅ page 11 artboard "T-E" (`3TH-0`), documented inline on the page as a deliberate override; flagship macOS build at `19.5` (`3UM-0`) — window-chrome height fixed from a hardcoded 1100px (left a dead void below content) to `fit-content` in this pass | Approved; ready for Windows/Linux flagship builds + Phase-4 implementation | — |
| CLI surface | shipped (`cli.py`, `keelway`/`keelway-ops` console scripts) | ✅ page `06 - CLI & Terminal`, artboards `06.1` "First run & command grammar" (`T9-0`) and `06.2` "Output states" (`U6-0`) | **CORRECTION 2026-11-23**: an earlier pass in this doc wrongly listed the CLI as un-artboarded and still needed. It was already fully designed on page 06 before this engagement started — first-run output, command grammar table, and sealed/denied/failed output states, all in JetBrains Mono matching the shipped `core/cli_tui.py` argument-parsing behavior (confirmed NOT an interactive TUI — see README TUI-claim fix in PR #218). No gap here | — |

## F. Marketing surfaces (parity check only — already both-sided)

Website v3 routes (`/`, `/about`, `/product`, `/pricing`, `/changelog`,
`/contact`, `/sign-in`, 404) shipped and artboarded on Paper pages 01/03/09.
Phase 4 includes a parity sweep against the live deployment
(`kora-sable.vercel.app`), not a redesign.

## G. Sorvex Labs (parent/maker engineering lab — new pages, added 2026-11-23)

| Surface | Code | Backend | Paper | Gap / note | Phase |
|---|---|---|---|---|---|
| Sorvex Labs — homepage | none (no separate Sorvex site exists in the repo) | n/a | ✅ artboard 05.3 (`3KU-0`) | Proposed marketing surface — Sorvex is Keelway's maker/parent lab, confirmed via direct repo inspection (not an independent or ambiguous entity) | 2 |
| Sorvex Labs — Research | none | grounded in `docs/research/AI_RESEARCH_ROADMAP.md` (real 3-phase roadmap: Data/Eval Harness, Supervised LoRA/QLoRA, Speculative Edge Inference) | ✅ artboard 05.4 (`3PJ-0`) | Proposed — content is fact-grounded, not invented | 2 |
| Sorvex Labs — Posture | none | grounded in `docs/SECURITY_INVARIANTS_AND_AUDIT_REPORT.md` (12 Non-Negotiable Security Invariants, 79/79 tests passing) | ✅ artboard 05.5 (`3QQ-0`) | Proposed — "no standing egress by default" claim informs the ad-tech-posture recommendation in `COMPLETENESS_AUDIT.md` | 2 |
| Sorvex Labs — Careers | none | n/a | ✅ artboard 05.6 (`3S3-0`) | Proposed | 2 |

## Phase-2 design queue (owner-approved order)

**Phase 2 coverage: complete**, plus the 2026-11-23 additions above. Every shipped screen is artboarded: page 17 Settings (`17.1`–`17.6`), page 18 Missing Surfaces (`18.1` P-10 + run lane, `18.2` billing, `18.3` overlays, `18.4a`–`18.4e` remaining views + state matrix (split from the former combined `18.4`), `18.5` drawers). Remaining:

1. ~~4-tier vs 5-tier billing canonical set~~ **RESOLVED 2026-11-23** — see section E.
2. ~~Agents registry grid~~ **RESOLVED 2026-11-23** — artboard 12.7 landed.
3. ~~**Dashboard/home, agent profile, agent builder** (12.8/12.9/12.10)~~ **SIGNED OFF 2026-11-23** — product go-ahead given (agent UI/UX, including onboarding and profiles, was explicitly requested as in-scope for this kit). All three move from "proposed" to approved Phase-2 deliverables; ready for Phase-4 implementation planning.
4. ~~**Per-OS desktop chrome** (page 11 "T-E", flagship 19.5)~~ **SIGNED OFF 2026-11-23** — explicit product direction to override the prior "never ships OS-specific chrome" rule (page 11's own documented constraint) and build real macOS/Windows/Linux native window chrome. Flagship macOS build (`19.5`) QA'd this pass: fixed a layout bug where the window chrome's fixed height (1100px) left a large empty void below the Home dashboard it wraps — changed to `height: fit-content` so the window hugs its content like a real native app.
5. ~~Light-theme token set~~ **RESOLVED 2026-11-23** — artboard `02.5 — Light-theme reference` added on page 04 (Brand System), documenting the real values shipped in `dev-app/tokens.css`'s `[data-theme="light"]` block. Reference only; Paper itself stays dark-native per DESIGN.md §8.
6. **CORRECTION 2026-11-23**: the CLI surface row in section B was wrong — it is NOT missing. Page `06 - CLI & Terminal` already fully covers it (`06.1`, `06.2`), predating this engagement.

## Page 19 — Desktop Completeness additions (KEEL-DSN-003)

| Surface | Component | Artboard | Status |
|---|---|---|---|
| Component primitives spec | all `dev-app` controls | `19.1` (`322-0`) | designed |
| Agent composer deep-dive | `AgentComposer.tsx` | `19.2` (`35J-0`) | implemented (APP-079) — model/route selector, explainRouting pre-flight strip, @-cite, Plan run |
| Workspace switcher + Inbox | `PlatformWorkspaceBar.tsx` + new inbox surface | `19.3` (`35K-0`) | designed — new surface |
| App auth + About & updates | new surfaces | `19.4` (`35L-0`) | designed — new surface |

