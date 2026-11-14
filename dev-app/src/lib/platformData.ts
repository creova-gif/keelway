import type {
  ExperienceMode,
  MarketplaceCategoryId,
  PlatformViewId,
  SubscriptionTierId,
} from "./types";

export type { ExperienceMode, MarketplaceCategoryId, PlatformViewId, SubscriptionTierId };

export interface SubscriptionTierInfo {
  id: SubscriptionTierId;
  badgeLabel: string;
  title: string;
  priceLabel: string;
  dailyOpenWeightTokens: number | "unlimited_local";
  rpmLimit: number;
  maxConcurrentAgents: number;
  summary: string;
}

export interface LifecycleAgentItem {
  id: string;
  name: string;
  roleTitle: string;
  plainSummary: string;
  stage: string;
  defaultModel: string;
  tools: string[];
  requiresP10: boolean;
  promptVersion: string;
  status: "ready" | "running" | "needs_approval";
  isCustom?: boolean;
  instructions?: string;
}

export interface MultiAgentTeamStep {
  id: string;
  agentId: string;
  action: string;
  status: "done" | "running" | "needs_approval" | "ready";
}

export interface MultiAgentTeamItem {
  id: string;
  name: string;
  description: string;
  memberAgentIds: string[];
  p10CheckpointLabel: string;
  lastRunStatus: "ready" | "running" | "needs_approval" | "done";
  executionSteps: MultiAgentTeamStep[];
}

export type PmIssueStatus = "backlog" | "todo" | "in_progress" | "in_review" | "done";
export type PmIssuePriority = "urgent" | "high" | "medium" | "low";

export interface PmIssueItem {
  id: string;
  title: string;
  status: PmIssueStatus;
  priority: PmIssuePriority;
  sprint: string;
  milestone: string;
  dependencies: string[];
  assignedAgentId?: string;
  linkedPrdId?: string;
}

export interface ProductPrdItem {
  id: string;
  title: string;
  problemStatement: string;
  riceScore: number;
  releaseStage: "discovery" | "in_delivery" | "beta" | "ga";
  linkedIssueIds: string[];
  acceptanceCriteria: Array<{ id: string; text: string; met: boolean }>;
}

export interface UserFeedbackItem {
  id: string;
  persona: string;
  quote: string;
  impactScore: number;
  linkedPrdId: string;
}

export interface WorkflowNodeItem {
  id: string;
  label: string;
  agentId: string;
  dependsOn: string[];
  status: "passed" | "failed" | "running" | "ready";
  errorDetail?: string;
}

export interface AutomationWorkflowItem {
  id: string;
  name: string;
  triggerKind: "cron" | "webhook" | "event";
  triggerSpec: string;
  lastRunStatus: "passed" | "failed" | "running" | "ready";
  tokenBudget: number;
  nodes: WorkflowNodeItem[];
}

export interface MarketplacePackageItem {
  id: string;
  name: string;
  category: MarketplaceCategoryId;
  publisher: string;
  publisherTier: "first_party" | "verified_third_party" | "enterprise_partner";
  revenueSplitLabel: string;
  priceLabel: string;
  summary: string;
  manifestSha256: string;
  securityVerified: boolean;
}

export interface MarketplaceScanInput {
  name: string;
  category: MarketplaceCategoryId;
  publisherTier: "first_party" | "verified_third_party" | "enterprise_partner";
  instructions: string;
  writePaths: string;
  networkFull: boolean;
  requiresP10Approval: boolean;
}

export interface MarketplaceScanReport {
  passed: boolean;
  riskGrade: "A" | "B" | "BLOCKED";
  manifestSha256: string;
  revenueSplitLabel: string;
  findings: Array<{ code: string; severity: "critical" | "high"; message: string }>;
}

export interface DocGuideItem {
  id: string;
  quadrant: "Tutorial" | "How-To" | "Reference" | "Explanation";
  title: string;
  summary: string;
  audience: "all" | "builder" | "non_coder";
}

export interface SdlcStageItem {
  stageNumber: number;
  title: string;
  leadAgent: string;
  crossAgentHarness: string;
  gateStatus: "verified" | "p10_human_gate" | "active";
}

export interface DeploymentEnvItem {
  id: string;
  environment: string;
  version: string;
  status: "healthy" | "rolled_back" | "staging_ready";
  url: string;
  lastDeployedAt: string;
  rollbackReceipt?: string;
}

export interface ByomValidationResult {
  valid: boolean;
  code: string;
  message: string;
}

export interface GeneratedProjectBlueprint {
  idea: string;
  templateLabel: string;
  prd: ProductPrdItem;
  issues: PmIssueItem[];
  workflow: AutomationWorkflowItem;
  assignedTeamId: string;
  assignedTeamName: string;
  previewUrl: string;
  generatedAt: string;
}

export const BYOM_CONSUMER_COMPLIANCE_CALLOUT =
  "Compliance rule: consumer ChatGPT Plus/Pro or Claude Pro/Max web subscriptions never grant third-party API access and are rejected fail-closed. Connect authorized vendor API keys (OpenAI, Anthropic, Google Gemini) or self-hosted vLLM/Ollama endpoints with $0.00 Keelway token markup.";

export const SUBSCRIPTION_TIERS: Record<SubscriptionTierId, SubscriptionTierInfo> = {
  community: {
    id: "community",
    badgeLabel: "Community",
    title: "Free / Community Open-Core",
    priceLabel: "$0 / mo",
    dailyOpenWeightTokens: 150_000,
    rpmLimit: 20,
    maxConcurrentAgents: 2,
    summary: "Unlimited $0.00 local hardware OpenCore + 150k/day hosted open-weight fair-use pool.",
  },
  pro: {
    id: "pro",
    badgeLabel: "Pro",
    title: "Keelway Pro",
    priceLabel: "$39 / seat / mo",
    dailyOpenWeightTokens: 2_500_000,
    rpmLimit: 120,
    maxConcurrentAgents: 12,
    summary: "12 concurrent lifecycle agents, Multi-Agent Teams, KSpaces sync, and 2.5M daily open-weight quota.",
  },
  byom: {
    id: "byom",
    badgeLabel: "BYOM · 0% Markup",
    title: "Bring Your Own Model",
    priceLabel: "Seat + $0 Token Markup",
    dailyOpenWeightTokens: "unlimited_local",
    rpmLimit: 240,
    maxConcurrentAgents: 12,
    summary: "Route authorized OpenAI, Anthropic, Gemini, or self-hosted vLLM API keys with 0% token markup.",
  },
  enterprise: {
    id: "enterprise",
    badgeLabel: "Enterprise",
    title: "Keelway Sovereign Enterprise",
    priceLabel: "Custom Annual / VPC",
    dailyOpenWeightTokens: "unlimited_local",
    rpmLimit: 1000,
    maxConcurrentAgents: 64,
    summary: "Dedicated sovereign VPC or air-gapped on-prem GPU clusters, SAML/SSO, RBAC & dual-human quorum.",
  },
};

export const INITIAL_LIFECYCLE_AGENTS: LifecycleAgentItem[] = [
  { id: "issue-triager", name: "issue-triager", roleTitle: "Issue Triage & Scope Classifier", plainSummary: "Turns bug reports and ideas into clear, prioritized tasks.", stage: "3. Tracking", defaultModel: "keelway-core:7b", tools: ["read_issues", "label_scope"], requiresP10: false, promptVersion: "p-14", status: "ready" },
  { id: "code-architect", name: "code-architect", roleTitle: "System & AST Code Architect", plainSummary: "Designs clean modular software blueprints before coding begins.", stage: "2. Architecture", defaultModel: "keelway-reasoner:14b", tools: ["ast_graph", "read_file"], requiresP10: false, promptVersion: "p-14", status: "ready" },
  { id: "feature-coder", name: "feature-coder", roleTitle: "Autonomous Feature Implementer", plainSummary: "Writes and refactors application code inside workspace Seatbelt isolation.", stage: "4. Implementation", defaultModel: "keelway-core:7b", tools: ["read_file", "edit_file", "run_tests"], requiresP10: true, promptVersion: "p-14", status: "ready" },
  { id: "pr-reviewer", name: "pr-reviewer", roleTitle: "Staff Diff & Gate Reviewer", plainSummary: "Audits code changes for regressions, security flaws, and gate integrity.", stage: "4. Review", defaultModel: "keelway-reasoner:14b", tools: ["git_diff", "gate_check"], requiresP10: false, promptVersion: "p-14", status: "ready" },
  { id: "qa-ci-runner", name: "qa-ci-runner", roleTitle: "Sandboxed QA & CI Verifier", plainSummary: "Runs unit, accessibility, and browser suites in isolated sandboxes.", stage: "5. Testing", defaultModel: "keelway-core:7b", tools: ["exec_sandbox", "axe_audit"], requiresP10: true, promptVersion: "p-14", status: "ready" },
  { id: "security-auditor", name: "security-auditor", roleTitle: "Threat, RBAC & Vuln Auditor", plainSummary: "Scans dependencies, RBAC rules, secrets, and prompt-injection risks.", stage: "5. Security", defaultModel: "keelway-reasoner:14b", tools: ["sbom_scan", "rbac_verify", "redact_check"], requiresP10: false, promptVersion: "p-14", status: "ready" },
  { id: "tech-writer", name: "tech-writer", roleTitle: "Diataxis Documentation Author", plainSummary: "Keeps tutorials, runbooks, and release changelogs synchronized with code.", stage: "7. Documentation", defaultModel: "keelway-core:7b", tools: ["read_file", "write_docs"], requiresP10: true, promptVersion: "p-14", status: "ready" },
  { id: "workflow-automator", name: "workflow-automator", roleTitle: "KFlow DAG & Webhook Automator", plainSummary: "Builds scheduled automations and event-driven business workflows.", stage: "5. Automation", defaultModel: "keelway-core:7b", tools: ["kflow_compile", "schedule_cron"], requiresP10: true, promptVersion: "p-14", status: "ready" },
  { id: "product-strategist", name: "product-strategist", roleTitle: "Discovery, PRD & RICE Strategist", plainSummary: "Structures user problems into PRDs, acceptance criteria, and roadmaps.", stage: "1. Requirements", defaultModel: "keelway-reasoner:14b", tools: ["prd_author", "rice_rank"], requiresP10: false, promptVersion: "p-14", status: "ready" },
  { id: "devops-sre", name: "devops-sre", roleTitle: "Release, SLO & Rollback Engineer", plainSummary: "Supervises staged rollouts, latency SLOs, and P-10 human-confirmed rollbacks.", stage: "8. Deployment", defaultModel: "keelway-reasoner:14b", tools: ["deploy_preview", "slo_probe", "rollback_env"], requiresP10: true, promptVersion: "p-14", status: "needs_approval" },
  { id: "custom-agent-forge", name: "custom-agent-forge", roleTitle: "Custom Agent & Skill Composer", plainSummary: "Packages reusable team skills and signed keelway.agent/v1 manifests.", stage: "9. Evaluation", defaultModel: "keelway-core:7b", tools: ["manifest_sign", "skill_pack"], requiresP10: true, promptVersion: "p-14", status: "ready" },
  { id: "nocode-app-builder", name: "nocode-app-builder", roleTitle: "Natural-Language App Synthesizer", plainSummary: "Transforms plain-English business ideas into full governed apps without coding.", stage: "1–8. End-to-End", defaultModel: "keelway-reasoner:14b", tools: ["blueprint_gen", "ui_scaffold", "kflow_compile"], requiresP10: true, promptVersion: "p-14", status: "ready" },
];

export const INITIAL_MULTI_AGENT_TEAMS: MultiAgentTeamItem[] = [
  {
    id: "team-idea-to-prod",
    name: "Idea-to-Production Squad",
    description: "End-to-end delivery from structured PRD to tested implementation and P-10 release gate.",
    memberAgentIds: ["product-strategist", "code-architect", "feature-coder", "qa-ci-runner"],
    p10CheckpointLabel: "P-10 Human Checkpoint before workspace mutation & staging deploy",
    lastRunStatus: "ready",
    executionSteps: [
      { id: "st-1", agentId: "product-strategist", action: "Lock PRD acceptance criteria & linked KEEL issues", status: "done" },
      { id: "st-2", agentId: "code-architect", action: "Emit typed module boundaries & zero-CDN contract", status: "done" },
      { id: "st-3", agentId: "feature-coder", action: "Synthesize implementation patch in Seatbelt", status: "ready" },
      { id: "st-4", agentId: "qa-ci-runner", action: "Run Vitest + axe-core + P-10 human sign-off", status: "needs_approval" },
    ],
  },
  {
    id: "team-security-release",
    name: "Security & Release Gate Squad",
    description: "Pre-landing staff code review, SPDX/vuln audit, and governed rollout supervision.",
    memberAgentIds: ["pr-reviewer", "security-auditor", "devops-sre"],
    p10CheckpointLabel: "P-10 Human Checkpoint required on Risk C network/deploy",
    lastRunStatus: "needs_approval",
    executionSteps: [
      { id: "sr-1", agentId: "pr-reviewer", action: "Audit diff hunks & gate integrity", status: "done" },
      { id: "sr-2", agentId: "security-auditor", action: "Verify SHA-256 Record chain & zero leaked secrets", status: "done" },
      { id: "sr-3", agentId: "devops-sre", action: "Await human P-10 approval for production promotion", status: "needs_approval" },
    ],
  },
  {
    id: "team-nocode-launch",
    name: "Guided App Launch Squad",
    description: "No-code app scaffolding, automated KFlow triggers, and instant user documentation.",
    memberAgentIds: ["nocode-app-builder", "workflow-automator", "tech-writer"],
    p10CheckpointLabel: "P-10 Human Checkpoint before external webhook activation",
    lastRunStatus: "ready",
    executionSteps: [
      { id: "nl-1", agentId: "nocode-app-builder", action: "Compile natural-language prompt into app blueprint", status: "done" },
      { id: "nl-2", agentId: "workflow-automator", action: "Wire KFlow schedule & notification nodes", status: "ready" },
      { id: "nl-3", agentId: "tech-writer", action: "Generate operator quickstart guide", status: "ready" },
    ],
  },
];

export const INITIAL_PM_ISSUES: PmIssueItem[] = [
  { id: "KEEL-101", title: "Enforce Marketplace pre-publish prompt-injection & shell scanner", status: "in_progress", priority: "urgent", sprint: "Sprint 14 · Sovereign Platform", milestone: "v1.1 Unified GA", dependencies: [], assignedAgentId: "security-auditor", linkedPrdId: "PRD-01" },
  { id: "KEEL-102", title: "Verify BYOM consumer-subscription fail-closed compliance notice", status: "in_review", priority: "high", sprint: "Sprint 14 · Sovereign Platform", milestone: "v1.1 Unified GA", dependencies: ["KEEL-101"], assignedAgentId: "pr-reviewer", linkedPrdId: "PRD-01" },
  { id: "KEEL-103", title: "Wire Unified 10-View context bar with zero context loss", status: "todo", priority: "high", sprint: "Sprint 14 · Sovereign Platform", milestone: "v1.1 Unified GA", dependencies: ["KEEL-101"], assignedAgentId: "feature-coder", linkedPrdId: "PRD-02" },
  { id: "KEEL-104", title: "Publish Diataxis onboarding guide for Guided Non-Coder studio", status: "backlog", priority: "medium", sprint: "Sprint 15 · Ecosystem", milestone: "v1.1 Unified GA", dependencies: ["KEEL-103"], assignedAgentId: "tech-writer", linkedPrdId: "PRD-02" },
];

export const INITIAL_PRODUCT_PRDS: ProductPrdItem[] = [
  {
    id: "PRD-01",
    title: "Security-Validated Marketplace & 5-Stream BYOM Governance",
    problemStatement: "Teams need verified agents, skills, and BYOM routing without prompt-injection supply-chain risk or consumer web token misuse.",
    riceScore: 94,
    releaseStage: "in_delivery",
    linkedIssueIds: ["KEEL-101", "KEEL-102"],
    acceptanceCriteria: [
      { id: "ac-1", text: "Block prompt-injection, eval/shell=True, and wildcard '/' writes pre-publish", met: true },
      { id: "ac-2", text: "Reject ChatGPT/Claude consumer web session cookies on BYOM endpoints", met: true },
      { id: "ac-3", text: "Enforce 85% Creator / 15% Platform split on verified 3rd-party packages", met: true },
    ],
  },
  {
    id: "PRD-02",
    title: "Dual Builder & Guided Non-Coder Unified Workspace",
    problemStatement: "Engineers and non-technical operators lose context switching across disconnected PM, PRD, IDE, and no-code tools.",
    riceScore: 91,
    releaseStage: "beta",
    linkedIssueIds: ["KEEL-103", "KEEL-104"],
    acceptanceCriteria: [
      { id: "ac-4", text: "Preserve active workspace, git branch, model, and P-10 queue across all 10 views", met: true },
      { id: "ac-5", text: "Compile plain-language ideas into linked PRDs, KEEL sprint issues, and KFlow DAGs", met: true },
    ],
  },
];

export const INITIAL_USER_FEEDBACK: UserFeedbackItem[] = [
  { id: "fb-1", persona: "Enterprise CISO", quote: "Every third-party skill must pass static prompt-injection and secret hygiene checks before install.", impactScore: 9.6, linkedPrdId: "PRD-01" },
  { id: "fb-2", persona: "Startup Ops Lead", quote: "I want to describe an internal approval tool in English and have engineers inspect the exact same repo.", impactScore: 9.3, linkedPrdId: "PRD-02" },
];

export const INITIAL_AUTOMATION_WORKFLOWS: AutomationWorkflowItem[] = [
  {
    id: "WF-01",
    name: "Nightly Security & SPDX Gate Pipeline",
    triggerKind: "cron",
    triggerSpec: "0 2 * * * (02:00 UTC)",
    lastRunStatus: "passed",
    tokenBudget: 25_000,
    nodes: [
      { id: "n-1", label: "Scan dependencies & SBOM", agentId: "security-auditor", dependsOn: [], status: "passed" },
      { id: "n-2", label: "Verify SHA-256 Record chain", agentId: "qa-ci-runner", dependsOn: ["n-1"], status: "passed" },
    ],
  },
  {
    id: "WF-02",
    name: "PR Triage & Staged Preview Sync",
    triggerKind: "webhook",
    triggerSpec: "POST /v1/webhooks/git-push",
    lastRunStatus: "failed",
    tokenBudget: 40_000,
    nodes: [
      { id: "n-3", label: "Classify changed AST modules", agentId: "issue-triager", dependsOn: [], status: "passed" },
      { id: "n-4", label: "Warm staging preview sandbox", agentId: "devops-sre", dependsOn: ["n-3"], status: "failed", errorDetail: "Sandbox port 7429 busy; retry allocates clean ephemeral port." },
    ],
  },
];

export const MARKETPLACE_CATEGORIES: Array<{ id: MarketplaceCategoryId; label: string }> = [
  { id: "ai_agent", label: "AI Agents" },
  { id: "multi_agent_system", label: "Multi-Agent Teams" },
  { id: "agent_skill", label: "Skills" },
  { id: "plugin_extension", label: "Plugins" },
  { id: "automation_template", label: "Workflows" },
  { id: "dev_tool", label: "Dev Tools" },
  { id: "industry_enterprise_solution", label: "Enterprise" },
];

export const INITIAL_MARKETPLACE_PACKAGES: MarketplacePackageItem[] = [
  { id: "pkg-migration-architect", name: "Zero-Downtime SQL Architect", category: "ai_agent", publisher: "Atlas Data Labs", publisherTier: "verified_third_party", revenueSplitLabel: "85% Creator / 15% Platform", priceLabel: "$19 / mo", summary: "Plans expand-contract PostgreSQL & SQLite WAL schema migrations.", manifestSha256: "sha256:4a91e802c3d1", securityVerified: true },
  { id: "pkg-soc2-swarm", name: "SOC2 Evidence Collector Swarm", category: "multi_agent_system", publisher: "Verity Assurance", publisherTier: "verified_third_party", revenueSplitLabel: "85% Creator / 15% Platform", priceLabel: "$49 / mo", summary: "3-agent compliance squad with P-10 human sign-off on evidence exports.", manifestSha256: "sha256:8f20b714e9a4", securityVerified: true },
  { id: "pkg-wcag-skill", name: "WCAG 2.2 AA Accessibility Skill", category: "agent_skill", publisher: "Sorvex Labs", publisherTier: "first_party", revenueSplitLabel: "100% First-Party · $0 Fee", priceLabel: "Included", summary: "Enforces semantic landmarks, axe-core zero-violation checks, and RTL bidi safety.", manifestSha256: "sha256:1c77d539a012", securityVerified: true },
  { id: "pkg-linear-bridge", name: "Linear & GitHub Issue Sync Plugin", category: "plugin_extension", publisher: "RelayWorks", publisherTier: "verified_third_party", revenueSplitLabel: "85% Creator / 15% Platform", priceLabel: "$12 / mo", summary: "Bidirectional webhook bridge scoped to issue metadata with DLP redaction.", manifestSha256: "sha256:9b34f12088cc", securityVerified: true },
  { id: "pkg-incident-dag", name: "SEV-1 Triage & Rollback KFlow", category: "automation_template", publisher: "Sorvex Labs", publisherTier: "first_party", revenueSplitLabel: "100% First-Party · $0 Fee", priceLabel: "Included", summary: "Automated log correlation DAG gated by P-10 human rollback confirmation.", manifestSha256: "sha256:6e55a90144b2", securityVerified: true },
  { id: "pkg-ast-boundary", name: "Monorepo Module Boundary Guard", category: "dev_tool", publisher: "CraftTooling", publisherTier: "verified_third_party", revenueSplitLabel: "85% Creator / 15% Platform", priceLabel: "$15 / mo", summary: "Deterministic AST import-cycle and 750-line file budget analyzer.", manifestSha256: "sha256:2d81c447f309", securityVerified: true },
  { id: "pkg-hipaa-vault", name: "Regional Sovereign Healthcare Pack", category: "industry_enterprise_solution", publisher: "MedShield Partner", publisherTier: "enterprise_partner", revenueSplitLabel: "80% Partner / 20% Platform", priceLabel: "Enterprise", summary: "PHISafe Harbor redaction policies, regional VPC lock, and 7-year audit retention.", manifestSha256: "sha256:7f19e663b5d8", securityVerified: true },
  { id: "pkg-finops-auditor", name: "OpenCore vs BYOM FinOps Skill", category: "agent_skill", publisher: "CloudLedger IO", publisherTier: "verified_third_party", revenueSplitLabel: "85% Creator / 15% Platform", priceLabel: "$9 / mo", summary: "Forecasts local hardware savings vs external API token spend.", manifestSha256: "sha256:5c02a883d17e", securityVerified: true },
];

export const INITIAL_DOC_GUIDES: DocGuideItem[] = [
  { id: "doc-1", quadrant: "Tutorial", title: "Ship Your First Governed App in 5 Minutes", summary: "Walk from a plain-English idea in No-Code Builder to a live preview with SHA-256 Record provenance.", audience: "non_coder" },
  { id: "doc-2", quadrant: "How-To", title: "Configure Authorized BYOM Keys & Local OpenCore", summary: "Connect OpenAI/Anthropic/Gemini API keys or local Ollama/vLLM endpoints with $0.00 markup.", audience: "all" },
  { id: "doc-3", quadrant: "Reference", title: "Extension SDK & keelway.package/v1 Security Spec", summary: "Register custom skills, tools, and webhooks that pass MarketplaceSecurityScanner.", audience: "builder" },
  { id: "doc-4", quadrant: "Explanation", title: "Why P-10 Human-Only Gates & Air-Gap Isolation Matter", summary: "How Seatbelt sandboxing, prompt-bound scopes, and hash-chained receipts prevent silent exfiltration.", audience: "all" },
];

export const SDLC_STAGES: SdlcStageItem[] = [
  { stageNumber: 1, title: "Requirements & Acceptance Criteria", leadAgent: "product-strategist", crossAgentHarness: "gstack /office-hours · Antigravity", gateStatus: "verified" },
  { stageNumber: 2, title: "Architecture & System Planning", leadAgent: "code-architect", crossAgentHarness: "Claude Code · gstack /plan-eng-review", gateStatus: "verified" },
  { stageNumber: 3, title: "Issue Tracking & Sprint Assignment", leadAgent: "issue-triager", crossAgentHarness: "Keelway PM Hub · Devin", gateStatus: "verified" },
  { stageNumber: 4, title: "Implementation & Staff Diff Review", leadAgent: "feature-coder", crossAgentHarness: "Antigravity · Claude Code · /review", gateStatus: "active" },
  { stageNumber: 5, title: "Automated QA, Accessibility & Security", leadAgent: "qa-ci-runner", crossAgentHarness: "Vitest + axe-core + MarketplaceScanner", gateStatus: "verified" },
  { stageNumber: 6, title: "Human Approval Checkpoint (P-10)", leadAgent: "human-operator", crossAgentHarness: "Inline P-10 Keyboard/Pointer Gate", gateStatus: "p10_human_gate" },
  { stageNumber: 7, title: "Diataxis Documentation & Changelog", leadAgent: "tech-writer", crossAgentHarness: "gstack /document-release · KBrain", gateStatus: "verified" },
  { stageNumber: 8, title: "Managed Deployment, SLOs & Rollback", leadAgent: "devops-sre", crossAgentHarness: "Keelway Operations · /canary", gateStatus: "p10_human_gate" },
  { stageNumber: 9, title: "Continuous Evaluation & FinOps", leadAgent: "custom-agent-forge", crossAgentHarness: "4D Router & Record Audit Ledger", gateStatus: "verified" },
];

export const INITIAL_DEPLOYMENTS: DeploymentEnvItem[] = [
  { id: "dep-local", environment: "Local Loopback Sandbox", version: "v1.1.0-rc4", status: "healthy", url: "http://127.0.0.1:7420/app", lastDeployedAt: "4m ago" },
  { id: "dep-staging", environment: "Staging Sovereign VPC", version: "v1.1.0-rc4", status: "staging_ready", url: "https://staging.keelway.internal", lastDeployedAt: "19m ago" },
  { id: "dep-prod", environment: "Production Cluster", version: "v1.0.9", status: "healthy", url: "https://app.keelway.internal", lastDeployedAt: "2d ago" },
];

export {
  generateLocalBlueprint,
  scanMarketplacePackageClient,
  syncPlatformBlueprintOptional,
  validateByomCredentialClient,
} from "./platformActions";
