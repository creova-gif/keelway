/**
 * Keelway Official TypeScript SDK — Phase 20 Cryptographic MCP & Skill Lockfile,
 * Tool-Poisoning / Rug-Pull Firewall & Conformance Benchmark (`client.platform`).
 * Zero external dependencies; attaches to `KeelwayClient.platform`.
 */

import type { PlatformJsonRequester } from "./platform.js";
import type { RequestOptions } from "./types.js";

export type McpLockfileStatus = "PINNED" | "POISONING_BLOCKED";
export type McpLockSimulateMode = "clean" | "rug_pull" | "poisoning";
export type McpLockVerificationVerdict = "LOCK_VERIFIED" | "DRIFT_RUG_PULL_BLOCKED" | "POISONING_BLOCKED";
export type ConformanceTargetKind = "mcp_server" | "skill_package" | "opencore_model";
export type ConformanceBenchmarkVerdict = "PASS_CERTIFIED" | "FAIL_CONFORMANCE" | "FAIL_BUDGET";

export interface McpLockToolSpec {
  server_id: string;
  tool_name: string;
  version?: string;
  description: string;
  input_schema_json?: string;
}
export interface McpPinnedToolEntry {
  server_id: string;
  tool_name: string;
  version: string;
  description: string;
  input_schema_json: string;
  tool_sha256: string;
  [key: string]: unknown;
}
export interface PinMcpLockfileRequest {
  workspace_id?: string;
  lockfile_name?: string;
  tools?: McpLockToolSpec[];
}
export interface McpLockfileRecord {
  lockfile_id: string | null;
  workspace_id: string;
  lockfile_name: string;
  schema_version: "keelway.lock/v1";
  status: McpLockfileStatus;
  tool_count: number;
  merkle_root_sha256: string;
  tools: McpPinnedToolEntry[];
  findings: string[];
  dlp_redactions: number;
  lockfile_json: string;
  created_at: string;
  [key: string]: unknown;
}
export interface ListMcpLockfilesParams {
  workspace_id?: string;
  limit?: number;
}
export type ListMcpLockfilesOptions = ListMcpLockfilesParams;
export type ListMcpLockVerificationsParams = ListMcpLockfilesParams;
export type ListConformanceBenchmarksParams = ListMcpLockfilesParams;

export interface McpLockfileListResponse {
  workspace_id: string;
  count: number;
  lockfiles: McpLockfileRecord[];
  [key: string]: unknown;
}
export interface VerifyMcpLockfileRequest {
  workspace_id?: string;
  lockfile_id?: string | null;
  live_tools?: McpLockToolSpec[];
  simulate_mode?: McpLockSimulateMode;
}
export interface McpLockVerificationRecord {
  verification_id: string;
  lockfile_id: string;
  workspace_id: string;
  verdict: McpLockVerificationVerdict;
  expected_merkle_root_sha256: string;
  observed_merkle_root_sha256: string;
  drifted_tools: string[];
  poisoning_findings: string[];
  dlp_redactions: number;
  verification_sha256: string;
  verified_at: string;
  [key: string]: unknown;
}
export interface McpLockVerificationListResponse {
  workspace_id: string;
  count: number;
  verifications: McpLockVerificationRecord[];
  [key: string]: unknown;
}
export interface ConformanceScenarioInput {
  scenario_id: string;
  schema_valid: boolean;
  deterministic_match: boolean;
  latency_ms: number;
  frontier_cost_usd?: number;
}
export interface RunConformanceBenchmarkRequest {
  workspace_id?: string;
  target_id?: string;
  target_kind?: ConformanceTargetKind;
  model_id?: string;
  latency_budget_ms?: number;
  min_conformance_score?: number;
  scenarios?: ConformanceScenarioInput[];
}
export interface ConformanceBenchmarkRecord {
  benchmark_id: string;
  workspace_id: string;
  target_id: string;
  target_kind: ConformanceTargetKind;
  model_id: string;
  verdict: ConformanceBenchmarkVerdict;
  scenario_count: number;
  conformance_score: number;
  min_conformance_score: number;
  p95_latency_ms: number;
  latency_budget_ms: number;
  frontier_cost_saved_usd: number;
  cert_sha256: string;
  created_at: string;
  [key: string]: unknown;
}
export interface ConformanceBenchmarkListResponse {
  workspace_id: string;
  count: number;
  runs: ConformanceBenchmarkRecord[];
  [key: string]: unknown;
}

const DEFAULT_TOOL_SCHEMA_JSON = '{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}';

function assertSimulateMode(mode: McpLockSimulateMode): McpLockSimulateMode {
  switch (mode) {
    case "clean":
    case "rug_pull":
    case "poisoning":
      return mode;
    default: {
      const _exhaustive: never = mode;
      throw new Error(`Invalid simulate_mode '${String(_exhaustive)}'.`);
    }
  }
}

function assertTargetKind(kind: ConformanceTargetKind): ConformanceTargetKind {
  switch (kind) {
    case "mcp_server":
    case "skill_package":
    case "opencore_model":
      return kind;
    default: {
      const _exhaustive: never = kind;
      throw new Error(`Invalid target_kind '${String(_exhaustive)}'.`);
    }
  }
}

function cleanNonEmpty(value: string, fieldName: string): string {
  const clean = value.trim();
  if (!clean) throw new Error(`${fieldName} must be non-empty.`);
  return clean;
}

function normalizeTools(tools: McpLockToolSpec[], fieldName: string): Array<Record<string, unknown>> {
  if (!Array.isArray(tools)) throw new Error(`${fieldName} must be an array.`);
  return tools.map((item) => {
    if (typeof item.description !== "string" || item.description.length === 0) {
      throw new Error(`${fieldName}[].description must be non-empty.`);
    }
    return {
      server_id: cleanNonEmpty(item.server_id, `${fieldName}[].server_id`),
      tool_name: cleanNonEmpty(item.tool_name, `${fieldName}[].tool_name`),
      version: (item.version ?? "1.0.0").trim() || "1.0.0",
      description: item.description,
      input_schema_json: item.input_schema_json && item.input_schema_json.length > 0 ? item.input_schema_json : DEFAULT_TOOL_SCHEMA_JSON,
    };
  });
}

function resolveSupplyChainListCall(
  wsOrParams: string | ListMcpLockfilesParams | undefined,
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

export class PlatformSupplyChainClient {
  constructor(private readonly requestJson: PlatformJsonRequester) {}

  public pinMcpLockfile(req: PinMcpLockfileRequest = {}, options?: RequestOptions): Promise<McpLockfileRecord> {
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      lockfile_name: cleanNonEmpty(req.lockfile_name ?? "keelway.lock.json", "lockfile_name"),
    };
    if (req.tools !== undefined) body.tools = normalizeTools(req.tools, "tools");
    return this.requestJson("POST", "/v1/platform/supply-chain/lock/pin", { body, options });
  }

  public listMcpLockfiles(wsOrParams?: string | ListMcpLockfilesParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<McpLockfileListResponse> {
    return this.requestJson("GET", "/v1/platform/supply-chain/lock/snapshots", resolveSupplyChainListCall(wsOrParams, limitOrOpts, options));
  }

  public verifyMcpLockfile(req: VerifyMcpLockfileRequest = {}, options?: RequestOptions): Promise<McpLockVerificationRecord> {
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      simulate_mode: assertSimulateMode(req.simulate_mode ?? "clean"),
    };
    if (req.lockfile_id !== undefined && req.lockfile_id !== null && req.lockfile_id.trim() !== "") {
      body.lockfile_id = req.lockfile_id.trim();
    }
    if (req.live_tools !== undefined) body.live_tools = normalizeTools(req.live_tools, "live_tools");
    return this.requestJson("POST", "/v1/platform/supply-chain/lock/verify", { body, options });
  }

  public listMcpLockVerifications(wsOrParams?: string | ListMcpLockVerificationsParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<McpLockVerificationListResponse> {
    return this.requestJson("GET", "/v1/platform/supply-chain/lock/verifications", resolveSupplyChainListCall(wsOrParams, limitOrOpts, options));
  }

  public runConformanceBenchmark(req: RunConformanceBenchmarkRequest = {}, options?: RequestOptions): Promise<ConformanceBenchmarkRecord> {
    const budget = req.latency_budget_ms ?? 250;
    const minScore = req.min_conformance_score ?? 0.9;
    if (!Number.isInteger(budget) || budget < 1) throw new Error("latency_budget_ms must be >= 1.");
    if (typeof minScore !== "number" || Number.isNaN(minScore) || minScore < 0 || minScore > 1) {
      throw new Error("min_conformance_score must be between 0.0 and 1.0.");
    }
    const body: Record<string, unknown> = {
      workspace_id: (req.workspace_id ?? "default").trim() || "default",
      target_id: cleanNonEmpty(req.target_id ?? "mcp-git-local", "target_id"),
      target_kind: assertTargetKind(req.target_kind ?? "mcp_server"),
      model_id: cleanNonEmpty(req.model_id ?? "keelway-core:7b", "model_id"),
      latency_budget_ms: budget,
      min_conformance_score: minScore,
    };
    if (req.scenarios !== undefined) body.scenarios = req.scenarios.map((s) => ({ ...s }));
    return this.requestJson("POST", "/v1/platform/supply-chain/bench/run", { body, options });
  }

  public listConformanceBenchmarks(wsOrParams?: string | ListConformanceBenchmarksParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<ConformanceBenchmarkListResponse> {
    return this.requestJson("GET", "/v1/platform/supply-chain/bench/runs", resolveSupplyChainListCall(wsOrParams, limitOrOpts, options));
  }
}

export { PlatformSupplyChainClient as PlatformSupplyChainDelegate };
