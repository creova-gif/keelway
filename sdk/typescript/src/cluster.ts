/**
 * Keelway Official TypeScript SDK — Distributed Cluster Namespace (`client.cluster`).
 *
 * Exposes all 10 `/v1/cluster/*` endpoints (GPU/NPU node discovery, registration,
 * drain/restore, VRAM & residency scheduling, shadow/canary/production lifecycle
 * promotion/rollback, and multi-tenant governance budget reservation) using
 * `KeelwayClient`'s zero-dependency Web Fetch infrastructure.
 */

import type { RequestOptions } from "./types.js";

export type ClusterJsonRequester = <T>(
  method: string,
  path: string,
  params?: {
    query?: Record<string, string>;
    body?: Record<string, unknown>;
    options?: RequestOptions;
  },
) => Promise<T>;

export interface ClusterListNodesParams {
  region?: string;
  runtime?: string;
  include_drained?: boolean;
}

export interface ClusterNodeRecord {
  node_id: string;
  region?: string;
  runtime?: string;
  accelerator?: string;
  total_vram_gb?: number;
  free_vram_gb?: number;
  status?: string;
  [key: string]: unknown;
}

export interface ClusterNodeListResponse {
  nodes: ClusterNodeRecord[];
  count?: number;
  total?: number;
  [key: string]: unknown;
}

export type RegisterClusterNodeRequest = Record<string, unknown>;
export type ClusterScheduleRequest = Record<string, unknown>;

export interface ClusterScheduleResponse {
  scheduled?: boolean;
  selected_node_id?: string | null;
  node_id?: string | null;
  model_id?: string;
  region?: string;
  reason?: string;
  [key: string]: unknown;
}

export interface ClusterLifecycleResponse {
  entries?: Record<string, unknown>[];
  models?: Record<string, unknown>[];
  deployments?: Record<string, unknown>[];
  total?: number;
  [key: string]: unknown;
}

export type PromoteClusterModelRequest = Record<string, unknown>;
export type RollbackClusterModelRequest = Record<string, unknown>;

export interface ClusterGovernanceAdapterStatusResponse {
  status?: string;
  active?: boolean;
  [key: string]: unknown;
}

export type ReserveClusterBudgetRequest = Record<string, unknown>;

export interface ReserveClusterBudgetResponse {
  allowed?: boolean;
  reserved?: boolean;
  reservation_id?: string;
  [key: string]: unknown;
}

export class ClusterNamespace {
  private readonly requestJson: ClusterJsonRequester;

  constructor(requestJson: ClusterJsonRequester) {
    this.requestJson = requestJson;
  }

  public listNodes(
    params: ClusterListNodesParams = {},
    options?: RequestOptions,
  ): Promise<ClusterNodeListResponse> {
    const query: Record<string, string> = {
      include_drained: String(params.include_drained ?? true),
    };
    if (params.region !== undefined) {
      query.region = params.region;
    }
    if (params.runtime !== undefined) {
      query.runtime = params.runtime;
    }
    return this.requestJson<ClusterNodeListResponse>("GET", "/v1/cluster/nodes", {
      query,
      options,
    });
  }

  public registerNode(
    payload: RegisterClusterNodeRequest,
    options?: RequestOptions,
  ): Promise<ClusterNodeRecord> {
    return this.requestJson<ClusterNodeRecord>("POST", "/v1/cluster/nodes/register", {
      body: { ...payload },
      options,
    });
  }

  public drainNode(
    nodeId: string,
    options?: RequestOptions,
  ): Promise<ClusterNodeRecord> {
    return this.requestJson<ClusterNodeRecord>(
      "POST",
      `/v1/cluster/nodes/${encodeURIComponent(nodeId)}/drain`,
      { options },
    );
  }

  public restoreNode(
    nodeId: string,
    options?: RequestOptions,
  ): Promise<ClusterNodeRecord> {
    return this.requestJson<ClusterNodeRecord>(
      "POST",
      `/v1/cluster/nodes/${encodeURIComponent(nodeId)}/restore`,
      { options },
    );
  }

  public schedule(
    payload: ClusterScheduleRequest,
    options?: RequestOptions,
  ): Promise<ClusterScheduleResponse> {
    return this.requestJson<ClusterScheduleResponse>("POST", "/v1/cluster/schedule", {
      body: { ...payload },
      options,
    });
  }

  public listLifecycle(
    params: { stage?: string } = {},
    options?: RequestOptions,
  ): Promise<ClusterLifecycleResponse> {
    const query: Record<string, string> | undefined =
      params.stage !== undefined ? { stage: params.stage } : undefined;
    return this.requestJson<ClusterLifecycleResponse>("GET", "/v1/cluster/lifecycle", {
      query,
      options,
    });
  }

  public promoteModel(
    payload: PromoteClusterModelRequest,
    options?: RequestOptions,
  ): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>(
      "POST",
      "/v1/cluster/lifecycle/promote",
      {
        body: { ...payload },
        options,
      },
    );
  }

  public rollbackModel(
    payload: RollbackClusterModelRequest,
    options?: RequestOptions,
  ): Promise<Record<string, unknown>> {
    return this.requestJson<Record<string, unknown>>(
      "POST",
      "/v1/cluster/lifecycle/rollback",
      {
        body: { ...payload },
        options,
      },
    );
  }

  public governanceAdapterStatus(
    options?: RequestOptions,
  ): Promise<ClusterGovernanceAdapterStatusResponse> {
    return this.requestJson<ClusterGovernanceAdapterStatusResponse>(
      "GET",
      "/v1/cluster/governance-adapter/status",
      { options },
    );
  }

  public reserveBudget(
    payload: ReserveClusterBudgetRequest,
    options?: RequestOptions,
  ): Promise<ReserveClusterBudgetResponse> {
    return this.requestJson<ReserveClusterBudgetResponse>(
      "POST",
      "/v1/cluster/governance-adapter/reserve-budget",
      {
        body: { ...payload },
        options,
      },
    );
  }
}
