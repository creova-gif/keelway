/**
 * Keelway Official TypeScript SDK — Phase 17 Formal Safety State-Machine Verifier
 * + Federated Edge-to-Cluster Agent Mesh (`client.platform` / `client.platform.safetyMesh`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */

import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";

export type SafetyToolKind = "read_only" | "write" | "destructive_shell" | "external_transfer" | "cloud_egress";
export type SafetyDataClassification = "public" | "internal" | "restricted_pii";
export type SafetyVerificationStatus = "VERIFIED_SAFE" | "VIOLATION_FOUND";
export type MeshTier = "edge_local" | "cluster_burst";
export type MeshHardwareHal = "apple_metal_secure_enclave" | "nvidia_h100_cc" | "linux_tpm2";
export type MeshNodeStatus = "ONLINE" | "DRAINING";
export type MeshHandoffStatus = "ATTESTED_COMPLETE" | "PINNED_EDGE_ONLY";

export interface SafetyWorkflowNodeInput {
  node_id: string;
  role?: string;
  tool_kind?: SafetyToolKind;
  requires_p10?: boolean;
  max_iterations?: number;
  data_classification?: SafetyDataClassification;
  [key: string]: unknown;
}

export interface SafetyWorkflowEdgeInput {
  from_node: string;
  to_node: string;
  condition?: string;
  [key: string]: unknown;
}

export interface VerifyWorkflowSafetyRequest {
  workspace_id?: string;
  workflow_id?: string;
  workflow_name?: string;
  nodes?: SafetyWorkflowNodeInput[];
  edges?: SafetyWorkflowEdgeInput[];
  airgap_mode?: boolean;
  inject_p10_guards?: boolean;
}

export interface SafetyInvariantCheck {
  invariant_id: string;
  passed: boolean;
  description: string;
  [key: string]: unknown;
}
export interface SafetyViolation {
  invariant_id: string;
  severity: string;
  offending_node: string;
  counterexample_path: string[];
  remediation: string;
  [key: string]: unknown;
}
export interface SafetyVerificationRecord {
  verification_id: string;
  workspace_id: string;
  workflow_id: string;
  workflow_name: string;
  status: SafetyVerificationStatus;
  states_explored: number;
  invariants_checked: SafetyInvariantCheck[];
  violations: SafetyViolation[];
  p10_guards_injected: string[];
  dlp_redactions: number;
  proof_sha256: string;
  created_at: string;
  [key: string]: unknown;
}
export interface ListSafetyVerificationsParams {
  workspace_id?: string;
  limit?: number;
}
export interface SafetyVerificationListResponse {
  workspace_id: string;
  count: number;
  verifications: SafetyVerificationRecord[];
  [key: string]: unknown;
}
export interface RegisterMeshNodeRequest {
  workspace_id?: string;
  node_id?: string;
  name: string;
  tier?: MeshTier;
  hardware_hal?: MeshHardwareHal;
  region?: string;
  vram_gb?: number;
  status?: MeshNodeStatus;
}
export interface MeshNodeRecord {
  node_id: string;
  workspace_id: string;
  name: string;
  tier: MeshTier;
  hardware_hal: MeshHardwareHal;
  region: string;
  vram_gb: number;
  status: string;
  attestation_sha256: string;
  registered_at: string;
  [key: string]: unknown;
}
export interface ListMeshNodesParams {
  workspace_id?: string;
}
export interface MeshNodeListResponse {
  workspace_id: string;
  count: number;
  nodes: MeshNodeRecord[];
  [key: string]: unknown;
}
export interface DispatchMeshHandoffRequest {
  workspace_id?: string;
  workflow_name?: string;
  task_summary?: string;
  data_classification?: SafetyDataClassification;
  allow_sanitized_burst?: boolean;
  force_raw_cloud_burst?: boolean;
}
export interface MeshStageExecution {
  stage_name: string;
  target_tier: MeshTier;
  node_id: string;
  model_id: string;
  hardware_hal: string;
  zero_raw_pii_egress: boolean;
  cost_usd: number;
  [key: string]: unknown;
}
export interface MeshHandoffRecord {
  handoff_id: string;
  workspace_id: string;
  workflow_name: string;
  data_classification: string;
  status: MeshHandoffStatus;
  edge_node_id: string;
  burst_node_id: string | null;
  stages: MeshStageExecution[];
  total_cost_usd: number;
  dlp_redactions: number;
  attestation_sha256: string;
  created_at: string;
  [key: string]: unknown;
}
export type ListMeshHandoffsParams = ListSafetyVerificationsParams;
export interface MeshHandoffListResponse {
  workspace_id: string;
  count: number;
  handoffs: MeshHandoffRecord[];
  [key: string]: unknown;
}

function assertMeshTier(tier: MeshTier): MeshTier {
  switch (tier) {
    case "edge_local":
    case "cluster_burst":
      return tier;
    default: {
      const _exhaustive: never = tier;
      throw new Error(`Invalid tier '${String(_exhaustive)}'.`);
    }
  }
}
function assertHardwareHal(hal: MeshHardwareHal): MeshHardwareHal {
  switch (hal) {
    case "apple_metal_secure_enclave":
    case "nvidia_h100_cc":
    case "linux_tpm2":
      return hal;
    default: {
      const _exhaustive: never = hal;
      throw new Error(`Invalid hardware_hal '${String(_exhaustive)}'.`);
    }
  }
}
function assertNodeStatus(status: MeshNodeStatus): MeshNodeStatus {
  switch (status) {
    case "ONLINE":
    case "DRAINING":
      return status;
    default: {
      const _exhaustive: never = status;
      throw new Error(`Invalid status '${String(_exhaustive)}'.`);
    }
  }
}
function assertDataClassification(cls: SafetyDataClassification): SafetyDataClassification {
  switch (cls) {
    case "public":
    case "internal":
    case "restricted_pii":
      return cls;
    default: {
      const _exhaustive: never = cls;
      throw new Error(`Invalid data_classification '${String(_exhaustive)}'.`);
    }
  }
}

function resolveListCall(
  wsOrParams: string | { workspace_id?: string; limit?: number } | undefined,
  limitOrOpts: number | RequestOptions | undefined,
  options: RequestOptions | undefined,
): { query: Record<string, string>; options?: RequestOptions } {
  const isObj = typeof wsOrParams === "object" && wsOrParams !== null;
  const wsId = ((isObj ? wsOrParams.workspace_id : wsOrParams) ?? "default").trim() || "default";
  const limit = isObj ? (wsOrParams.limit ?? 25) : typeof limitOrOpts === "number" ? limitOrOpts : 25;
  const opts = isObj ? (limitOrOpts as RequestOptions | undefined) : typeof limitOrOpts === "object" ? limitOrOpts : options;
  if (!Number.isInteger(limit) || limit < 1) throw new Error("limit must be >= 1.");
  return { query: { workspace_id: wsId, limit: String(limit) }, options: opts };
}

export class PlatformSafetyMeshClient {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public verifyWorkflowSafety(req: VerifyWorkflowSafetyRequest = {}, options?: RequestOptions): Promise<SafetyVerificationRecord> {
    const workflowId = (req.workflow_id ?? "WF-TREASURY-01").trim();
    if (!workflowId) throw new Error("workflow_id must be non-empty.");
    const workflowName = (req.workflow_name ?? "treasury-wire-approver").trim();
    if (!workflowName) throw new Error("workflow_name must be non-empty.");
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      workflow_id: workflowId,
      workflow_name: workflowName,
      airgap_mode: req.airgap_mode ?? false,
      inject_p10_guards: req.inject_p10_guards ?? false,
    };
    if (req.nodes !== undefined) body.nodes = req.nodes;
    if (req.edges !== undefined) body.edges = req.edges;
    return this.requestJson("POST", "/v1/platform/safety/verify", { body, options });
  }

  public listSafetyVerifications(workspaceId?: string, limit?: number, options?: RequestOptions): Promise<SafetyVerificationListResponse>;
  public listSafetyVerifications(params?: ListSafetyVerificationsParams, options?: RequestOptions): Promise<SafetyVerificationListResponse>;
  public listSafetyVerifications(wsOrParams?: string | ListSafetyVerificationsParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<SafetyVerificationListResponse> {
    return this.requestJson("GET", "/v1/platform/safety/verifications", resolveListCall(wsOrParams, limitOrOpts, options));
  }

  public registerMeshNode(req: RegisterMeshNodeRequest, options?: RequestOptions): Promise<MeshNodeRecord> {
    const name = (req.name ?? "").trim();
    if (!name) throw new Error("name must be non-empty.");
    const region = (req.region ?? "local-loopback").trim();
    if (!region) throw new Error("region must be non-empty.");
    const vramGb = req.vram_gb ?? 32;
    if (!Number.isInteger(vramGb) || vramGb < 1) throw new Error("vram_gb must be >= 1.");
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      name,
      tier: assertMeshTier(req.tier ?? "edge_local"),
      hardware_hal: assertHardwareHal(req.hardware_hal ?? "apple_metal_secure_enclave"),
      region,
      vram_gb: vramGb,
      status: assertNodeStatus(req.status ?? "ONLINE"),
    };
    if (req.node_id !== undefined && req.node_id.trim() !== "") body.node_id = req.node_id.trim();
    return this.requestJson("POST", "/v1/platform/mesh/nodes", { body, options });
  }

  public listMeshNodes(workspaceId?: string, options?: RequestOptions): Promise<MeshNodeListResponse>;
  public listMeshNodes(params?: ListMeshNodesParams, options?: RequestOptions): Promise<MeshNodeListResponse>;
  public listMeshNodes(wsOrParams: string | ListMeshNodesParams = "default", options?: RequestOptions): Promise<MeshNodeListResponse> {
    const wsId = typeof wsOrParams === "object" && wsOrParams !== null ? (wsOrParams.workspace_id ?? "default").trim() || "default" : wsOrParams.trim() || "default";
    return this.requestJson("GET", "/v1/platform/mesh/nodes", { query: { workspace_id: wsId }, options });
  }

  public dispatchMeshHandoff(req: DispatchMeshHandoffRequest = {}, options?: RequestOptions): Promise<MeshHandoffRecord> {
    const workflowName = (req.workflow_name ?? "clinical-synthesis-pipeline").trim();
    if (!workflowName) throw new Error("workflow_name must be non-empty.");
    const taskSummary = (req.task_summary ?? "Ingest patient intake & synthesize anonymized cohort summary").trim();
    if (!taskSummary) throw new Error("task_summary must be non-empty.");
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      workflow_name: workflowName,
      task_summary: taskSummary,
      data_classification: assertDataClassification(req.data_classification ?? "restricted_pii"),
      allow_sanitized_burst: req.allow_sanitized_burst ?? true,
      force_raw_cloud_burst: req.force_raw_cloud_burst ?? false,
    };
    return this.requestJson("POST", "/v1/platform/mesh/dispatch", { body, options });
  }

  public listMeshHandoffs(workspaceId?: string, limit?: number, options?: RequestOptions): Promise<MeshHandoffListResponse>;
  public listMeshHandoffs(params?: ListMeshHandoffsParams, options?: RequestOptions): Promise<MeshHandoffListResponse>;
  public listMeshHandoffs(wsOrParams?: string | ListMeshHandoffsParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<MeshHandoffListResponse> {
    return this.requestJson("GET", "/v1/platform/mesh/handoffs", resolveListCall(wsOrParams, limitOrOpts, options));
  }
}

export { PlatformSafetyMeshClient as PlatformSafetyMeshDelegate };
