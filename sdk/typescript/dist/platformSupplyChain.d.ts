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
export declare class PlatformSupplyChainClient {
    private readonly requestJson;
    constructor(requestJson: PlatformJsonRequester);
    pinMcpLockfile(req?: PinMcpLockfileRequest, options?: RequestOptions): Promise<McpLockfileRecord>;
    listMcpLockfiles(wsOrParams?: string | ListMcpLockfilesParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<McpLockfileListResponse>;
    verifyMcpLockfile(req?: VerifyMcpLockfileRequest, options?: RequestOptions): Promise<McpLockVerificationRecord>;
    listMcpLockVerifications(wsOrParams?: string | ListMcpLockVerificationsParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<McpLockVerificationListResponse>;
    runConformanceBenchmark(req?: RunConformanceBenchmarkRequest, options?: RequestOptions): Promise<ConformanceBenchmarkRecord>;
    listConformanceBenchmarks(wsOrParams?: string | ListConformanceBenchmarksParams, limitOrOpts?: number | RequestOptions, options?: RequestOptions): Promise<ConformanceBenchmarkListResponse>;
}
export { PlatformSupplyChainClient as PlatformSupplyChainDelegate };
//# sourceMappingURL=platformSupplyChain.d.ts.map