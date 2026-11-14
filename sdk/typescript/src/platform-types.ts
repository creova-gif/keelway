/**
 * Keelway Official TypeScript SDK — Unified Platform (`/v1/platform/*`) Domain Types.
 * Zero runtime dependencies; compatible with Node 20+, Bun, Deno, Workers, and browsers.
 */

export interface PlatformOverviewParams {
  workspace_id?: string;
}

export interface PlatformViewDescriptor {
  id: string;
  name?: string;
  summary?: string;
  [key: string]: unknown;
}

export interface PlatformOverviewResponse {
  workspace_id: string;
  project_name?: string;
  branch?: string;
  active_model_id?: string;
  experience_mode?: string;
  views: PlatformViewDescriptor[];
  lifecycle_agents_count: number;
  multi_agent_teams_count?: number;
  sdlc_stages?: Record<string, unknown>[];
  counts?: Record<string, number>;
  installed_packages?: Record<string, unknown>[];
  [key: string]: unknown;
}

export interface SubscriptionTierDescriptor {
  id: string;
  name?: string;
  stream_kind?: string;
  monthly_price_usd?: number | null;
  annual_monthly_price_usd?: number | null;
  local_hardware_token_cost_usd?: number;
  daily_open_weight_tokens?: number;
  rpm_limit?: number;
  capabilities?: string[];
  [key: string]: unknown;
}

export interface SubscriptionTiersResponse {
  tiers: SubscriptionTierDescriptor[];
  [key: string]: unknown;
}

export interface QuotaCheckRequest {
  org_id: string;
  tier: string;
  tokens_requested: number;
  current_rpm?: number;
  local_hardware?: boolean;
}

export interface QuotaCheckResponse {
  allowed: boolean;
  status: string;
  org_id: string;
  tier: string;
  used_daily_tokens?: number;
  remaining_daily_tokens?: number;
  rpm_limit?: number;
  reason?: string;
  fallback_advice?: string;
  [key: string]: unknown;
}

export interface ValidateByomRequest {
  provider: string;
  credential_kind: string;
  api_key_preview?: string;
  model_id?: string;
  commercial_use?: boolean;
  license_id?: string;
}

export interface ValidateByomResponse {
  valid: boolean;
  code: string;
  provider: string;
  credential_kind?: string;
  model_id?: string;
  consumer_subscription_grants_api_access: boolean;
  platform_billing_mode?: string | null;
  token_markup_pct?: number;
  message?: string;
  [key: string]: unknown;
}

export interface CheckModelLicenseRequest {
  model_id: string;
  license_id: string;
  commercial_use?: boolean;
  has_authorized_api_key?: boolean;
  has_authorized_api_credential?: boolean;
  exceeds_700m_mau?: boolean;
}

export interface CheckModelLicenseResponse {
  allowed: boolean;
  model_id: string;
  license_id: string;
  commercial_use?: boolean;
  code: string;
  obligations?: string[];
  [key: string]: unknown;
}

export interface ListMarketplacePackagesParams {
  kind?: string;
  query?: string;
  publisher_tier?: string;
  workspace_id?: string;
}

export interface MarketplaceSecurityFinding {
  category: string;
  rule_id: string;
  severity: string;
  field?: string;
  message?: string;
  [key: string]: unknown;
}

export interface MarketplaceScanReport {
  passed: boolean;
  risk_grade: string;
  findings: MarketplaceSecurityFinding[];
  findings_count: number;
  manifest_sha256?: string;
  scanned_at?: string;
  [key: string]: unknown;
}

export type MarketplacePackageInput = Record<string, unknown>;

export interface MarketplacePackageRecord {
  id: string;
  name?: string;
  kind?: string;
  version?: string;
  publisher?: string;
  publisher_tier?: string;
  pricing_model?: string;
  price_usd?: number;
  description?: string;
  security_verified?: boolean;
  manifest_sha256?: string;
  [key: string]: unknown;
}

export interface MarketplacePackageListResponse {
  packages: MarketplacePackageRecord[];
  total: number;
  installed: Record<string, unknown>[];
  [key: string]: unknown;
}

export interface InstallMarketplacePackageRequest {
  package_id: string;
  workspace_id?: string;
  config?: Record<string, unknown>;
}

export interface InstallMarketplacePackageResponse {
  package_id: string;
  workspace_id: string;
  status: string;
  [key: string]: unknown;
}

export interface PurchaseMarketplacePackageRequest {
  package_id: string;
  buyer_tenant_id?: string;
  workspace_id?: string;
  config?: Record<string, unknown>;
}

export interface MarketplaceSettlementRecord {
  settlement_id: string;
  package_id: string;
  package_version: string;
  buyer_tenant_id: string;
  publisher_tier: string;
  gross_cents: number;
  creator_payout_cents: number;
  platform_fee_cents: number;
  gross_usd: number;
  creator_payout_usd: number;
  platform_fee_usd: number;
  split_label: string;
  license_spdx: string;
  entitlement_sha256: string;
  receipt_sha256: string;
  created_at: string;
  installed?: boolean;
  [key: string]: unknown;
}

export interface ListMarketplaceSettlementsParams {
  tenant_id?: string;
}

export interface MarketplaceSettlementSummaryResponse {
  settlements: MarketplaceSettlementRecord[];
  totals: {
    count: number;
    gross_cents?: number;
    creator_payout_cents?: number;
    platform_fee_cents?: number;
    gross_usd: number;
    creator_payout_usd: number;
    platform_fee_usd: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export interface LifecycleAgentsResponse {
  agents: Record<string, unknown>[];
  teams: Record<string, unknown>[];
  sdlc_stages?: Record<string, unknown>[];
  runs?: Record<string, unknown>[];
  [key: string]: unknown;
}

export interface DispatchTeamRequest {
  team_id: string;
  goal?: string;
  objective?: string;
  workspace_id?: string;
  sensitive_mutation?: boolean;
}

export interface TeamRunResponse {
  run_id: string;
  workspace_id?: string;
  team_id: string;
  objective: string;
  status: string;
  p10_checkpoint: { gate: string; human_approval_required: boolean; [key: string]: unknown };
  delegation_trace?: Record<string, unknown>[];
  [key: string]: unknown;
}

export interface ListIssuesParams { workspace_id?: string; status?: string; }
export interface CreateIssueRequest {
  title: string; workspace_id?: string; priority?: string; status?: string;
  assignee_agent?: string; prd_id?: string; sprint_id?: string;
}
export interface PlatformIssueRecord {
  id: string; title: string; status: string; priority?: string;
  sprint_id?: string; prd_id?: string | null; assignee_agent?: string; [key: string]: unknown;
}
export interface PlatformIssueListResponse { issues: PlatformIssueRecord[]; total: number; [key: string]: unknown; }

export interface CreatePrdRequest { title: string; summary: string; workspace_id?: string; acceptance_criteria?: string[]; }
export interface PlatformPrdRecord { id: string; title: string; summary: string; status?: string; acceptance_criteria?: string[]; [key: string]: unknown; }
export interface PlatformPrdListResponse { prds: PlatformPrdRecord[]; total: number; [key: string]: unknown; }

export interface CreateWorkflowRequest { name: string; trigger?: string; workspace_id?: string; nodes?: Record<string, unknown>[]; }
export interface PlatformWorkflowRecord { id: string; name: string; trigger: string; status?: string; nodes?: Record<string, unknown>[]; [key: string]: unknown; }
export interface PlatformWorkflowListResponse { workflows: PlatformWorkflowRecord[]; total: number; [key: string]: unknown; }

export interface CompileBlueprintRequest { idea: string; workspace_id?: string; experience_mode?: string; target_stack?: string; }
export interface CompiledBlueprintResponse {
  workspace_id: string; experience_mode: string; idea?: string; prd: PlatformPrdRecord;
  sprint_issues: PlatformIssueRecord[]; workflow: PlatformWorkflowRecord; team_run?: TeamRunResponse;
  architecture_summary: { target_stack: string; [key: string]: unknown }; [key: string]: unknown;
}

export interface ListExtensionsParams { workspace_id?: string; extension_type?: string; }
export type ExtensionSpecInput = Record<string, unknown>;
export interface PlatformExtensionRecord { id: string; name?: string; extension_type?: string; status: string; manifest_sha256?: string; [key: string]: unknown; }
export interface PlatformExtensionListResponse { extensions: PlatformExtensionRecord[]; total: number; [key: string]: unknown; }
