# Keelway Unified AI-Native Agent Local Platform — Architecture & Design Specification

**Date:** 2026-11-14
**Status:** Approved for Implementation (`KEEL-PLATFORM-010`)
**Cross-Agent Contract:** `Antigravity` · `Claude Code` · `Devin` · `gstack` (`keelway/AGENTS.md`)

---

## 1. Executive Architecture & Shared-Infrastructure-First Strategy

Keelway is engineered as a **unified, sovereign, AI-native local operating environment** serving experienced software engineers, non-technical builders, startups, and regulated enterprises inside one shared architecture rather than disconnected tools.

Following Pillar 10 (*Shared Infrastructure Before Specialized Products*), all surfaces (`keelway` CLI, `/app` Unified 10-View Workspace, `/v1/platform/*` REST APIs, Python & TypeScript SDKs, and the Next.js 15 website showcase) build upon one canonical foundation:

1. **Identity, RBAC & Tenant Isolation:** Existing `core/security/rbac.py`, `core/security/tenant_governance.py`, and Ed25519 `core/billing/entitlements.py`.
2. **Unified Open-Core + Commercial Model Gateway:** Existing `core/models/gateway.py` and `core/opencore/` extended with Community fair-use quotas, BYOM credential/subscription compliance checks, and SPDX/commercial license enforcement (`core/platform/subscription.py`).
3. **Marketplace & Pre-Publication Security Validator:** Typed `keelway.package/v1` registry supporting 1st-party and verified 3rd-party agents, multi-agent teams, skills, plugins, workflow templates, dev tools, and enterprise systems—gated by mandatory pre-publish prompt-injection, shell/AST exfiltration, secret-leak, and least-privilege permission scanning (`core/platform/marketplace.py`).
4. **Unified Workspace Hub & Extension SDK:** Shared project context (`core/platform/workspace_hub.py`) connecting **Agents**, **IDE**, **Project Manager** (Linear-style issues/sprints/roadmaps), **Product** (PRDs & release plans), **Automation** (DAG/scheduled workflows), **Marketplace**, **Security** (SHA-256 hash-chained Record ledger + RBAC/vuln posture), **Documentation** (Diataxis KB), **Operations** (deployments, costs, SLOs), and **No-Code Builder** (natural-language idea -> PRD -> sprint issues -> agent workflow -> governed app deployment), plus an external **Extension SDK** (`ExtensionRegistry`) so third-party developers register skills, tools, webhooks, and custom business rules without modifying core infrastructure.

---

## 2. Pillar-by-Pillar Technical Design

### Pillar 1 — Keelway Marketplace (`core/platform/marketplace.py`)
- **Supported Package Kinds (`PackageKind`):**
  1. `ai_agent` — Specialized single-role lifecycle agents
  2. `multi_agent_system` — Coordinated multi-role swarms with delegation & P-10 checkpoints
  3. `agent_skill` — Reusable instruction/tool bundles (`SKILL.md` / KHub compatible)
  4. `plugin_extension` — MCP servers, API connectors, webhook bridges (`core/plugins/` compatible)
  5. `automation_template` — Durable KFlow DAG & cron/event workflow blueprints
  6. `dev_tool` — AST analyzers, test runners, code-review gates, CLI extensions
  7. `industry_enterprise_solution` — Vertical compliance/ops systems (fintech, healthcare, sovereign regional VPC)
- **Publisher Tiers & Monetization:**
  - `first_party` (`Sorvex Labs / Keelway Official`): `100%` platform share (`0%` external fee).
  - `verified_third_party`: `85%` creator share / `15%` Keelway marketplace share.
  - `enterprise_partner`: `80%` partner share / `20%` Keelway enterprise distribution & assurance share.
- **Pre-Publication Security Validation (`MarketplaceSecurityScanner`):**
  - Every `publish_package()` call runs deterministic static + policy checks before listing:
    - **Prompt-Injection & Guardrail Bypass Scan:** Rejects instructions attempting `ignore previous instructions`, `bypass p-10`, `disable airgap`, `auto-approve risk c`, or hidden system-prompt exfiltration.
    - **Malicious Code / Execution Scan:** Rejects `eval(`, `exec(`, `subprocess.*shell=True`, `curl ... | sh`, `os.system(`, or raw outbound socket exfiltration hooks.
    - **Permission Envelope Check:** Rejects wildcard root writes (`write_paths` containing `/` or `..`) or unscoped `network="full"` paired with credential paths without `requires_p10_approval=True`.
    - **Secret Hygiene:** Scans manifests and templates via `core/security/redact.py` to reject embedded live API keys or tokens.
  - Emits an immutable `SecurityValidationReport` (`passed`, `risk_grade`, `findings`, `manifest_sha256`).

### Pillar 2 & Pillar 3 — Open-Core Model Integration & 5-Stream Subscription / BYOM Engine (`core/platform/subscription.py`)
- **Five Revenue & Access Streams:**
  1. **`community` (Free / Community Tier — \$0):** Open-core local platform, unlimited local hardware inference (`$0.00/tok`), capped hosted/community open-weight pool (`daily_open_weight_tokens=150_000`, `rpm_limit=20`, `max_concurrent_agents=2`, `max_active_workflows=3`), core dev tools & basic automation.
  2. **`pro` (Keelway Pro — \$39/seat/mo annual, \$49 monthly):** Advanced lifecycle agents, multi-agent team orchestration (`max_concurrent_agents=12`), unlimited workflows, KSpaces sync, higher quotas (`daily_open_weight_tokens=2_500_000`, `rpm_limit=120`).
  3. **`byom` (Bring Your Own Model — Platform Seat + \$0 Token Markup):** Connect authorized `OpenAI`, `Anthropic`, `Google Gemini`, or self-hosted `vLLM`/`Ollama` endpoints via user API credentials, while Keelway bills transparently for workspace, orchestration, and automation execution.
     - **Hard Consumer-Subscription Compliance Rule:** Consumer web subscriptions (`ChatGPT Plus/Pro/Team web`, `Claude Pro/Max web` session cookies, or non-API OAuth tokens) **MUST NEVER** be assumed to grant third-party API access. `validate_byom_connection()` explicitly rejects consumer session cookies/unofficial tokens (`CREDENTIAL_TYPE_UNSUPPORTED_CONSUMER_SUBSCRIPTION`), permits only authorized API keys or officially sanctioned vendor integrations, and surfaces an explicit compliance notice across API, CLI, Dev App, and `/pricing`.
  4. **`enterprise` (Keelway Enterprise — Custom Annual / Usage / VPC):** Dedicated VPC or air-gapped on-prem GPU clusters, custom SLAs, SAML/SSO, RBAC, dual-human quorum, data retention policies, and custom multi-agent engineering.
  5. **`marketplace` (Marketplace Transactions & Revenue Share):** Paid agents, premium skills, plugins, templates, and enterprise solutions with deterministic creator/platform split accounting.
- **Provider License & Commercial-Use Validator:** Evaluates model licenses (`Apache-2.0`, `MIT`, `Llama-3.3-Community`, `Commercial-API`) against tenant deployment mode and commercial-use flags before dispatch.

### Pillar 4 & Pillar 9 — Unified 10-View Workspace & Dual Builder / Non-Coder UX (`dev-app/` + `core/platform/workspace_hub.py`)
All 10 views operate over a single shared workspace context (`projectId`, `workspacePath`, `branch`, `activeModelId`, `experienceMode: "builder" | "non_coder"`, `issues`, `prds`, `workflows`, `agents`, `installedPackages`, and `P-10` receipts):

| # | Workspace View | Primary Capabilities | Builder vs. Non-Coder Adaptation |
|---|---|---|---|
| 1 | **Agents View** | 12 lifecycle agents, multi-agent team composer, delegation trace, P-10 approval supervisor | Builder: manifest digests, tool scopes, prompt versions · Non-Coder: plain-language role cards & 1-click team launch |
| 2 | **IDE View** | AI-assisted coding (`Tasks` + `Files`), AST symbol jump, unified diff review, sandboxed terminal | Builder: full split-diff, shell & symbol explorer · Non-Coder: guided explanation + visual change preview |
| 3 | **Project Manager View** | Linear-inspired issues, priorities, sprint board, roadmap milestones, dependency tracking, agent assignment | Shared issue store; 1-click `Delegate to Agent` |
| 4 | **Product View** | Discovery, structured PRDs, acceptance criteria, RICE/impact prioritization, user feedback, release plan | Links PRD requirements directly to PM issues & verification gates |
| 5 | **Automation View** | Visual DAG & cron/webhook workflow builder, live node status, retry & failure diagnostics | Compiles into KFlow-compatible DAG specifications |
| 6 | **Marketplace View** | Discover, filter, security-inspect, install, configure, and publish agents, skills, plugins & templates | Displays `SHA-256 Verified` scan report & creator revenue split |
| 7 | **Security View** | SHA-256 hash-chained Record ledger, RBAC permissions, vulnerability & plugin scan posture, retention policies | Preserves `P-10` human-only approval invariant (`Risk A/B/C`) |
| 8 | **Documentation View** | Diataxis technical docs, onboarding guides, knowledge base (`KBrain`), cross-agent `AGENTS.md` contract | Auto-generates runbooks & architecture notes from workspace state |
| 9 | **Operations View** | Deployments, rollback controls, OpenCore vs. BYOM token cost ledger, TTFT latency SLOs, runner health | Live spend & reliability telemetry |
| 10 | **No-Code Builder View** | Natural-language idea -> structured Project + PRD + Sprint Issues + Automation DAG + App Scaffold + Managed Deploy | Enables non-coders to ship end-to-end inside the exact same governed platform |

### Pillar 5, 6 & 8 — 12 Lifecycle Agents, Extension SDK & 9-Stage Cross-Agent SDLC
- **12 Built-In Specialized Lifecycle Agents:** `issue-triager`, `code-architect`, `feature-coder`, `pr-reviewer`, `qa-ci-runner`, `security-auditor`, `tech-writer`, `workflow-automator`, `product-strategist`, `devops-sre`, `custom-agent-forge`, and `nocode-app-builder`.
- **Coordinated Multi-Agent Teams:** Pre-wired and customizable teams (e.g., `Idea-to-Production Squad`, `Security & Release Gate Squad`) with explicit tool-permission envelopes, task delegation order, `P-10` human approval checkpoints on high-impact mutations, and observable execution receipts.
- **Extension SDK (`ExtensionRegistry`):** Clean hook registration (`skill`, `tool`, `webhook`, `workflow_rule`, `ui_panel`) validated by `MarketplaceSecurityScanner` so external developers extend Keelway without touching core modules.
- **9-Stage Autonomous Engineering Workflow (`Antigravity` / `Claude` / `Devin` / `gstack`):** Encoded in `SDLC_WORKFLOW_STAGES` (`1. Requirements & Acceptance Criteria` -> `2. Architecture & Planning` -> `3. Issue Tracking & Assignment` -> `4. Implementation & Review` -> `5. Automated Testing & Security` -> `6. Human Approval (P-10)` -> `7. Documentation & Change Mgmt` -> `8. Deployment, Monitoring & Rollback` -> `9. Continuous Evaluation`).

### CLI & Flagship Website Showcases
- **Claude-Code-Style `keelway` TUI Launch (`core/cli_tui.py` + `cli.py`):** Framed Unicode box (`╭─── Keelway v1.1 · Sovereign Local-First AI Developer Platform ───╮`) with 24-bit `#2DD4BF` teal wordmark, live workspace/git/OpenCore/Seatbelt/Air-Gap/Tier telemetry, and `/agents /ide /pm /nocode /marketplace /model /airgap /audit /doctor` slash strip—preserving 100% backward compatibility with `plain=True` ASCII and `NO_COLOR=1`.
- **Website Showcases (`website/`):**
  - `/governance`: `RecordTamperLab` (7-col SHA-256 ledger + 4D Provenance Inspector + `"⚡ Simulate Tamper on #1279"` -> `"Verify Chain"`) & `ManifestDriftSimulator` (`p-13 -> p-14` drift auto-pause + live Marketplace Pre-Publish Security Scanner).
  - `/playground`: Interactive 10-View Unified Platform & Dual `Builder` / `Non-Coder` browser workbench.
  - `/pricing`: Complete 5-Stream Subscription, BYOM (with explicit consumer ChatGPT/Claude subscription non-assumption notice), Enterprise VPC, and Marketplace Revenue-Share presentation.
  - Global `⌘K`: Prefix modes (`>` actions/playground, `@` models, `/` docs, `#` governance/marketplace/API).

---

## 3. Global Security & Quality Constraints
1. **Human-Only P-10 Gates:** Destructive commands, external network egress (`Risk C`), production deploys, and drifted manifests always require explicit human approval; agents cannot self-approve.
2. **Zero Third-Party CDNs:** Neither `dev-app/` nor `website/` may load `fonts.googleapis.com`, `fonts.gstatic.com`, `cdn.tailwindcss.com`, or `cdnjs.cloudflare.com`.
3. **File Size Discipline:** Every new or modified `.ts`, `.tsx`, and new `.py` file must remain strictly `<750` lines (`core/cli_tui.py` holds new CLI TUI code so `cli.py` only receives minimal delegation hooks).
4. **Evidence-Backed Product Claims:** Every `"AVAILABLE"` feature in `website/product-facts.json` and `website/public/product-facts.json` must stay byte-identical and point to real `code_path` and passing `evidence_test` files on disk.
