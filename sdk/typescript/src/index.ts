/**
 * `@keelway/sdk` — Official Zero-Dependency TypeScript SDK for Keelway.
 */

export { KeelwayClient } from "./client.js";
export { ClusterNamespace } from "./cluster.js";
export type {
  ClusterGovernanceAdapterStatusResponse,
  ClusterJsonRequester,
  ClusterLifecycleResponse,
  ClusterListNodesParams,
  ClusterNodeListResponse,
  ClusterNodeRecord,
  ClusterScheduleRequest,
  ClusterScheduleResponse,
  PromoteClusterModelRequest,
  RegisterClusterNodeRequest,
  ReserveClusterBudgetRequest,
  ReserveClusterBudgetResponse,
  RollbackClusterModelRequest,
} from "./cluster.js";
export { PlatformNamespace, PlatformClient } from "./platform.js";
export type { PlatformJsonRequester } from "./platform.js";
export { parseSseFrames, PlatformRuntimeDelegate } from "./platform-runtime.js";
export type { ParsedSseFrame, PlatformSseRequester } from "./platform-runtime.js";
export { PlatformMcpEvalDelegate } from "./platformMcpEval.js";
export { PlatformKflowDelegate } from "./platformKflow.js";
export { PlatformEnterpriseDelegate } from "./platformEnterprise.js";
export { PlatformKbrainDelegate } from "./platformKbrain.js";
export { PlatformDevxDelegate } from "./platformDevx.js";
export { PlatformStudioClient, PlatformStudioDelegate } from "./platformStudio.js";
export { PlatformDebuggerClient, PlatformDebuggerDelegate } from "./platformDebugger.js";
export type * from "./platformDebugger.js";
export { PlatformCyclicClient, PlatformCyclicDelegate } from "./platformCyclic.js";
export type * from "./platformCyclic.js";
export * from "./platformHealing.js";

export {
  AirGapEgressError,
  AuthenticationError,
  BudgetExceededError,
  ConnectionError,
  FlightRecorderError,
  KeelwayError,
  mapHttpError,
  PermissionDeniedError,
  PolicyViolationError,
  QuorumRequiredError,
  RateLimitExceededError,
  TaskNotFoundError,
} from "./errors.js";
export type { ErrorDetails } from "./errors.js";

export type * from "./types.js";
export type * from "./platform-types.js";
