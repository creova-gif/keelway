/**
 * Keelway Official TypeScript SDK — Phase 8 KFlow DAG Execution, KSpaces CRDT Sync & SBOM.
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */

import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";

export type KflowNodeKind =
  | "trigger"
  | "agent"
  | "mcp_tool"
  | "p10_gate"
  | "transform"
  | (string & {});

export interface KflowNodeSpec {
  id: string;
  label?: string;
  agent_id?: string;
  kind?: KflowNodeKind;
  depends_on?: string[];
  requires_p10?: boolean;
  config?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ExecuteKflowDagRequest {
  workflow_id: string;
  nodes?: KflowNodeSpec[];
  trigger?: string;
  token_budget?: number;
  approved_node_ids?: string[];
  workspace_id?: string;
}

export interface KflowNodeResult {
  id: string;
  label?: string;
  agent_id?: string;
  depends_on?: string[];
  requires_p10?: boolean;
  wave?: number;
  status: string;
  tokens?: number;
  upstream_digests?: string[];
  output_digest?: string | null;
  error_detail?: string | null;
  [key: string]: unknown;
}

export interface KflowRunReceipt {
  run_id: string;
  workspace_id?: string;
  workflow_id: string;
  trigger?: string;
  status: string;
  held_node_id?: string | null;
  topological_order?: string[];
  waves?: string[][];
  nodes?: KflowNodeResult[];
  tokens_used?: number;
  token_budget?: number;
  receipt_sha256?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface ListKflowRunsParams {
  workspace_id?: string;
  workflow_id?: string;
  limit?: number;
}

export interface KflowRunListResponse {
  workspace_id?: string;
  count?: number;
  runs: KflowRunReceipt[];
  [key: string]: unknown;
}

export interface KspacesCrdtOperation {
  namespace?: string;
  key: string;
  value?: unknown;
  op?: "set" | "remove" | (string & {});
  lamport_ts?: number;
  [key: string]: unknown;
}

export interface KspacesCrdtEntry {
  namespace: string;
  key: string;
  value: unknown;
  lamport_ts: number;
  peer_id: string;
  tombstone: boolean;
  [key: string]: unknown;
}

export interface SyncKspacesCrdtRequest {
  peer_id: string;
  operations: KspacesCrdtOperation[];
  workspace_id?: string;
}

export interface KspacesStateResponse {
  workspace_id: string;
  vector_clock?: Record<string, number>;
  state_digest_sha256: string;
  active_keys_count: number;
  entries: KspacesCrdtEntry[];
  [key: string]: unknown;
}

export interface KspacesSyncResponse extends KspacesStateResponse {
  peer_id: string;
  applied_count: number;
}

export interface GetKspacesStateParams {
  workspace_id?: string;
  namespace?: string;
}

export interface GetPlatformSbomParams {
  workspace_id?: string;
}

export interface PlatformSbomComponent {
  name: string;
  version: string;
  component_type?: string;
  purl?: string;
  sha256?: string;
  supplier?: string;
  [key: string]: unknown;
}

export interface PlatformSbomResponse {
  workspace_id?: string;
  verified: boolean;
  verification_status?: string;
  serial_number?: string;
  bom_format: string;
  spec_version: string;
  component_count?: number;
  root_digest_sha256: string;
  provenance_signature: string;
  manifest?: {
    components?: PlatformSbomComponent[];
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

function kflowWsId(params?: { workspace_id?: string } | string): string {
  return typeof params === "string" ? (params || "default") : (params?.workspace_id ?? "default");
}

export class PlatformKflowDelegate {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public executeKflowDag(req: ExecuteKflowDagRequest, options?: RequestOptions): Promise<KflowRunReceipt> {
    return this.requestJson("POST", "/v1/platform/automation/workflows/execute", {
      body: {
        workspace_id: req.workspace_id ?? "default",
        workflow_id: req.workflow_id,
        nodes: req.nodes ?? [],
        trigger: req.trigger ?? "manual",
        token_budget: req.token_budget ?? 25000,
        approved_node_ids: req.approved_node_ids ?? [],
      },
      options,
    });
  }

  public listKflowRuns(params: ListKflowRunsParams | string = {}, options?: RequestOptions): Promise<KflowRunListResponse> {
    const query: Record<string, string> = { workspace_id: kflowWsId(params) };
    if (typeof params !== "string") {
      if (params.workflow_id !== undefined) query.workflow_id = params.workflow_id;
      if (params.limit !== undefined) query.limit = String(params.limit);
    }
    return this.requestJson("GET", "/v1/platform/automation/runs", { query, options });
  }

  public syncKspacesCrdt(req: SyncKspacesCrdtRequest, options?: RequestOptions): Promise<KspacesSyncResponse> {
    return this.requestJson("POST", "/v1/platform/kspaces/sync", {
      body: {
        workspace_id: req.workspace_id ?? "default",
        peer_id: req.peer_id,
        operations: req.operations,
      },
      options,
    });
  }

  public getKspacesState(params: GetKspacesStateParams | string = {}, options?: RequestOptions): Promise<KspacesStateResponse> {
    const query: Record<string, string> = { workspace_id: kflowWsId(params) };
    if (typeof params !== "string" && params.namespace !== undefined) {
      query.namespace = params.namespace;
    }
    return this.requestJson("GET", "/v1/platform/kspaces/state", { query, options });
  }

  public getPlatformSbom(params: GetPlatformSbomParams | string = {}, options?: RequestOptions): Promise<PlatformSbomResponse> {
    return this.requestJson("GET", "/v1/platform/security/sbom", {
      query: { workspace_id: kflowWsId(params) },
      options,
    });
  }
}
