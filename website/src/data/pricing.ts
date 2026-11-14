export interface FaqItem {
  q: string;
  a: string;
}

export interface MatrixRow {
  category: string;
  feature: string;
  community: string | boolean;
  pro: string | boolean;
  byom: string | boolean;
  enterprise: string | boolean;
}

export interface MarketplaceSplitTier {
  tier: string;
  creatorShare: string;
  platformShare: string;
  scope: string;
}

export const COMPARISON_ROWS: MatrixRow[] = [
  {
    category: "Models & Quotas",
    feature: "Local OpenCore 1.5B–14B Weights & Modelfile Compiler ($0.00/tok)",
    community: true,
    pro: true,
    byom: true,
    enterprise: true,
  },
  {
    category: "Models & Quotas",
    feature: "Hosted Community Open-Weight Pool & Fair-Use Rate Limits",
    community: "150K tok/day · 20 RPM",
    pro: "2.5M tok/day · 120 RPM",
    byom: "Pro Pool + BYOM Direct",
    enterprise: "Dedicated GPU Fleet",
  },
  {
    category: "Models & Quotas",
    feature: "Commercial Frontier Routing (OpenAI, Anthropic, Gemini, vLLM)",
    community: "Local BYOK Only",
    pro: "0%-Markup Vault",
    byom: "Authorized API Keys (0% Markup)",
    enterprise: "Private VPC Gateway + SLAs",
  },
  {
    category: "Unified Workspace & Agents",
    feature: "10-View Workspace (Builder & Guided Non-Coder Modes)",
    community: "Core Local Views",
    pro: "Full 10-View + KSpaces Sync",
    byom: "Full 10-View + Orchestration",
    enterprise: "Multi-Org + Custom Views",
  },
  {
    category: "Unified Workspace & Agents",
    feature: "Lifecycle AI Agents & Coordinated Multi-Agent Squads",
    community: "Up to 2 Concurrent",
    pro: "12 Lifecycle Agents",
    byom: "12 Agents + Custom Routing",
    enterprise: "Custom Bespoke Agent Systems",
  },
  {
    category: "Governance & Marketplace",
    feature: "P-10 Human-Only Approval Gates & SHA-256 Record Ledger",
    community: "Local SQLite WAL",
    pro: "Tamper-Evident Sync",
    byom: "Scoped kw_live_* Vault",
    enterprise: "Dual-Human Quorum + SIEM",
  },
  {
    category: "Governance & Marketplace",
    feature: "Keelway Marketplace Extensions (keelway.package/v1)",
    community: "Free / OSS Packages",
    pro: "Install & Publish",
    byom: "Install & Publish",
    enterprise: "Private Org Catalog + Assurance",
  },
];

export const MARKETPLACE_PUBLISHER_SPLITS: MarketplaceSplitTier[] = [
  {
    tier: "Verified Third-Party Creators",
    creatorShare: "85% Creator",
    platformShare: "15% Platform",
    scope:
      "Paid specialized AI agents, reusable SKILL.md bundles, MCP plugins, and KFlow workflow templates after passing pre-publish security validation.",
  },
  {
    tier: "Enterprise Solution Partners",
    creatorShare: "80% Partner",
    platformShare: "20% Keelway Assurance",
    scope:
      "Regulated vertical compliance packs (fintech, healthcare, sovereign regional VPC) with continuous vulnerability & SBOM attestation.",
  },
  {
    tier: "Sorvex Labs First-Party OSS",
    creatorShare: "Open-Core ($0)",
    platformShare: "0% External Fee",
    scope:
      "Core 12 lifecycle agents, Seatbelt/Landlock sandboxes, and baseline developer tools bundled free with every Keelway installation.",
  },
];

export const PRICING_FAQS: FaqItem[] = [
  {
    q: "Do my consumer ChatGPT Plus/Pro or Claude Pro/Max web subscriptions grant BYOM API access?",
    a: "No. Users with existing ChatGPT or Claude subscriptions can use officially supported vendor integrations where available, however consumer ChatGPT Plus/Pro or Claude Pro/Max web subscriptions do NOT automatically grant third-party API access. Keelway's Bring Your Own Model (BYOM) engine enforces strict provider terms compliance: consumer web session cookies are rejected (CREDENTIAL_TYPE_UNSUPPORTED_CONSUMER_SUBSCRIPTION), and BYOM API routing requires authorized provider API credentials (such as OpenAI Platform, Anthropic Console, Google AI/Vertex API keys, or self-hosted vLLM endpoints) at 0% token markup.",
  },
  {
    q: "Does Keelway mark up commercial OpenAI, Gemini, or Anthropic token prices?",
    a: "No. Keelway Pro, BYOM, and Enterprise Sovereign VPC tiers route your authorized API keys with 0% token markup. You pay upstream model providers directly at their published API rate cards while Keelway bills transparently for platform orchestration, agent execution, workspace sync, and governance.",
  },
  {
    q: "How does the Keelway Marketplace 85% / 15% creator revenue share and security scan work?",
    a: "Verified third-party builders keep 85% of gross Marketplace sales across paid agents, premium skills, plugins, and automation templates (15% platform fee). Every keelway.package/v1 submission must pass deterministic pre-publication security scanning that blocks prompt injection, shell=True execution sinks, leaked secrets, and wildcard filesystem scopes before listing.",
  },
  {
    q: "Can I use the Free / Community tier 100% offline or in an air-gapped facility?",
    a: "Yes. Free / Community ($0 forever under Apache-2.0) and Keelway Enterprise VPC operate completely offline over loopback (127.0.0.1) or private subnets with $0.00/tok local OpenCore inference, plus a fair-use community open-weight pool (150K daily tokens, 20 RPM) when connected.",
  },
  {
    q: "What happens when an engineering team hits its monthly cloud spend cap or Community quota?",
    a: "TenantPolicy and SubscriptionPolicyEngine handle limits deterministically: either seamlessly fall back to local keelway-core:7b ($0.00/tok) on your own hardware with zero downtime, or return a typed HTTP 402 / QUOTA_EXCEEDED response with clear upgrade or local-inference guidance.",
  },
];
