import type React from "react";

/* ==========================================================================
   Shell, Navigation, Appearance & Honest Status Bar Types
   ========================================================================== */

export type RailSection = "tasks" | "files" | "record" | "settings";

export type SettingsSubSection =
  | "permissions"
  | "models"
  | "governance"
  | "network"
  | "appearance"
  | "labs"
  | "general"
  | "keyboard";

export type ThemeMode = "dark" | "light" | "system";
export type DensityMode = "compact" | "default" | "comfortable";
export type LocaleCode = "en-US" | "es" | "fr" | "de" | "ja" | "zh-CN" | "pt-BR" | "ar";

export type TaskStatus =
  | "needs_approval"
  | "running"
  | "queued"
  | "done"
  | "ready"
  | "failed";

export type EgressBarMode =
  | "unmeasured"
  | "measured_offline"
  | "air_gapped_verified"
  | "unknown_probe_failed"
  | "connected_warning";

export interface EgressEndpointSummary {
  host: string;
  purpose: string;
  calls: number;
  bytesSent: number | null;
  modelId?: string;
}

export interface EgressTelemetryState {
  mode: EgressBarMode;
  cloudCallsCount: number;
  bytesSent: number | null;
  airGapLocked: boolean;
  endpoints: EgressEndpointSummary[];
  lastCheckedAt?: string;
}

/* ==========================================================================
   Tasks & Step Receipts (Screens 02 & 04)
   ========================================================================== */

export interface SidebarTaskItem {
  id: string;
  title: string;
  status: TaskStatus;
  branch?: string;
  modelLabel?: string;
  updatedAt: string;
  pendingApprovalId?: string;
  filesChangedCount?: number;
}

export type StepReceiptKind = "read" | "searched" | "edited" | "command" | "test";

export interface StepReceiptItem {
  id: string;
  kind: StepReceiptKind;
  title: string;
  target: string;
  detail?: string;
  output?: string;
  status: "ready" | "running" | "passed" | "failed";
  recordSeq?: number;
  durationMs?: number;
  linesAdded?: number;
  linesRemoved?: number;
  exitCode?: number;
  timestamp?: string;
}

/* ==========================================================================
   Inline P-10 Human-Only Gate (Screen 03)
   ========================================================================== */

export type P10ApprovalKind = "file_edit" | "command" | "network_deploy";
export type P10PreviewStatus = "loading" | "ready" | "failed";
export type ProvisionalConfidence = "Low" | "Medium";

export interface P10DiffLine {
  type: "context" | "add" | "del" | "hunk";
  oldLine?: number;
  newLine?: number;
  content: string;
}

export interface P10ApprovalProposal {
  id: string;
  taskId: string;
  kind: P10ApprovalKind;
  title: string;
  summary: string;
  whyReason: string;
  targetPath?: string;
  command?: string;
  workingDir?: string;
  destinationHost?: string;
  payloadBytesEstimate?: number;
  diffLines?: P10DiffLine[];
  previewStatus: P10PreviewStatus;
  previewError?: string;
  modelId: string;
  modelVersion: string;
  promptVersion: string;
  confidence?: ProvisionalConfidence;
  domainPolicyCode?: string;
  createdAt: string;
  recordSeqCandidate?: number;
}

export type P10DecisionAction = "allow_once" | "allow_always_scoped" | "deny";

export interface P10ScopedRuleSpec {
  scopePattern: string;
  actionKind: P10ApprovalKind;
  modelId: string;
  promptVersion: string;
  expiresAfterSession?: boolean;
}

export interface P10ApprovalDecisionPayload {
  proposalId: string;
  taskId: string;
  decision: P10DecisionAction;
  modifiedCommand?: string;
  modifiedTargetPath?: string;
  escalatedToNetwork?: boolean;
  scopedRule?: P10ScopedRuleSpec;
  denyReason?: string;
  confirmedExternalSend?: boolean;
  decidedBy: "human_keyboard_or_pointer";
  decidedAt: string;
}

export interface P10ApprovalReceipt {
  proposalId: string;
  recordSeq: number;
  decision: P10DecisionAction;
  summary: string;
  modifiedByUser: boolean;
  escalatedByEdit?: boolean;
  decidedAt: string;
  actorLabel: string;
}

/* ==========================================================================
   Files & Codebase Explorer (Screen 05)
   ========================================================================== */

export type GitFileStatus = "M" | "A" | "D" | "U";

export interface WorkspaceFileNode {
  path: string;
  name: string;
  type: "file" | "directory";
  language?: string;
  gitStatus?: GitFileStatus;
  dirty?: boolean;
  saveError?: string;
  aiRecordSeq?: number;
  children?: WorkspaceFileNode[];
}

export interface CodeSymbolItem {
  name: string;
  kind: "function" | "class" | "interface" | "variable" | "method" | "type";
  path: string;
  line: number;
  signature?: string;
}

export interface FileDiffHunk {
  path: string;
  oldStart: number;
  newStart: number;
  additions: number;
  deletions: number;
  aiRecordSeq?: number;
  lines: P10DiffLine[];
}

export interface GitCommitProposal {
  clean: boolean;
  branch: string;
  filesCount: number;
  files: Array<{ path: string; status: string }>;
  proposedTitle: string;
  proposedMessage: string;
  patchHash: string;
  diffPreview?: string;
}

export interface GitCommitResult {
  ok: boolean;
  commitSha: string;
  branch: string;
  message: string;
  author: string;
  clean: boolean;
}

/* ==========================================================================
   Record SHA-256 Hash-Chained Audit Ledger (Screen 06)
   ========================================================================== */

export type RecordActorKind = "human" | "agent" | "system" | "policy";
export type RecordOutcomeKind =
  | "passed"
  | "ready"
  | "allowed"
  | "denied"
  | "blocked"
  | "failed";

export interface RecordFourDRouteReceipt {
  privacy: "private" | "internal" | "public";
  latencyTier: "interactive" | "standard" | "batch";
  costCapUsd: number;
  taskComplexity: "low" | "medium" | "high";
  selectedProvider: string;
  selectedModel: string;
  dataBoundary: "local_loopback" | "sovereign_vpc" | "external_vendor_api";
  reason: string;
}

export interface RecordLedgerEntry {
  seq: number;
  timestampEt: string;
  isoTimestamp: string;
  actorKind: RecordActorKind;
  actorLabel: string;
  action: string;
  target: string;
  modelId: string;
  modelVersion: string;
  promptVersion: string;
  systemPromptHash: string;
  approvalLabel: string;
  approvedByHuman: boolean;
  outcome: RecordOutcomeKind;
  hash: string;
  prevHash: string;
  prevSeq: number | null;
  merkleRoot?: string;
  diffPath?: string;
  fourDRoute?: RecordFourDRouteReceipt;
}

export interface ChainVerificationState {
  status: "verified" | "broken" | "checking" | "unverified";
  totalEntries: number;
  brokenAtSeq?: number;
  expectedPrevHash?: string;
  actualPrevHash?: string;
  merkleRoot?: string;
  verifiedAt?: string;
}

export interface AuditMerkleProof {
  seq: number;
  leafHash: string;
  merkleRoot: string;
  siblings: Array<{ position: "left" | "right"; hash: string }>;
  verified: boolean;
}

/* ==========================================================================
   Settings & Sovereign Control Plane (Screens 08–11)
   ========================================================================== */

export interface ScopedPermissionRule {
  id: string;
  capability: string;
  scopePattern: string;
  mode: "allow_scoped" | "ask_every_time" | "locked_human_only";
  boundModelId: string;
  boundPromptVersion: string;
  currentPromptVersion: string;
  driftDetected: boolean;
  immutable?: boolean;
  policyRef?: string;
  createdAt: string;
}

export interface AgentManifestItem {
  id: string;
  name: string;
  version: string;
  schemaVersion: "keelway.agent/v1";
  description: string;
  enabled: boolean;
  tools: string[];
  networkAllowed: boolean;
  maxTier: 1 | 2 | 3;
  signatureStatus: "verified" | "unsigned" | "invalid";
  rawJson?: string;
}

export interface ManifestInspectResult {
  valid: boolean;
  schemaVersion: string;
  name?: string;
  version?: string;
  riskLevel: "low" | "medium" | "high";
  requiresHumanP10: boolean;
  errors: string[];
  warnings: string[];
  capabilities: string[];
}

export interface OpenCoreWeightItem {
  id: string;
  name: string;
  version: string;
  quantization: string;
  sizeGb: number;
  vramGb: number;
  status: "loaded" | "cached" | "available";
  sha256: string;
  license: string;
  localLoopback: boolean;
}

export interface RoutingExplainRequest {
  taskKind: string;
  privacy: "private" | "internal" | "public";
  maxLatencyMs: number;
  maxCostUsd: number;
  candidateEndpoint?: string;
  preferLocal?: boolean;
}

export interface RoutingExplainResult {
  allowed: boolean;
  decision: "routed_local" | "routed_cloud" | "blocked_fail_closed";
  selectedModel: string;
  provider: string;
  dataBoundary: "local_loopback" | "sovereign_vpc" | "external_vendor_api";
  privacyClassification: "private" | "internal" | "public";
  estimatedCostUsd: number;
  estimatedLatencyMs: number;
  rationale: string;
  blockedReason?: string;
  evaluatedCandidates: Array<{
    model: string;
    boundary: string;
    passed: boolean;
    reason: string;
  }>;
}

export type DataResidencyZone =
  | "local_only"
  | "africa_sovereign"
  | "eu_sovereign"
  | "global";

export interface GovernancePersistenceInfo {
  engine: string;
  journalMode: string;
  synchronous: string;
  dbPath: string;
  walBytes: number;
  foreignKeys: boolean;
  healthy: boolean;
}

export interface TenantGovernancePolicy {
  tenantId: string;
  name: string;
  residencyZone: DataResidencyZone;
  monthlyBudgetUsd: number;
  currentSpendUsd: number;
  warnThresholdPct: number;
  hardCapEnforced: boolean;
  fallbackToOpencoreOnBudgetExceeded: boolean;
  fallbackModelId: string;
  requireHumanApprovalForNetwork: boolean;
  updatedAt: string;
}

export interface ScopedApiKeyItem {
  id: string;
  label: string;
  prefix: string;
  scopes: string[];
  spendCapUsd: number;
  spentUsd: number;
  createdAt: string;
  revokedAt?: string | null;
}

export interface MintedScopedApiKeyResult {
  key: ScopedApiKeyItem;
  plaintextSecret: string;
  oneTimeWarning: string;
}

export interface DoctorCheckItem {
  id: string;
  label: string;
  status: "ok" | "warning" | "failed";
  detail: string;
  remediation?: string;
}

export interface LabsExperimentItem {
  id: string;
  kind: "benchmark" | "swarm" | "speculative" | "drift";
  title: string;
  summary: string;
  epistemicStatus: "simulated" | "estimated" | "prototype" | "live";
  metricLabel: string;
  metricValue: string;
  lastRunAt?: string;
  methodologyNote: string;
}

export interface StudioWsEvent {
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

/* ==========================================================================
   P-10 Trusted User Event Verification
   ========================================================================== */

interface MaybeUntrustedFlag {
  __kwUntrustedSynthetic?: boolean;
}

/**
 * Enforces P-10 human-only gesture authenticity:
 * - Any event flagged `__kwUntrustedSynthetic: true` is unconditionally rejected.
 * - Real browser hardware events (`event.isTrusted === true`) are accepted.
 * - In Vitest (`import.meta.env.MODE === "test"`), `@testing-library/user-event`
 *   dispatches synthetic jsdom events unless tagged `__kwUntrustedSynthetic`.
 * - In production/runtime builds (`mode !== "test"`), `event.isTrusted === true`
 *   is strictly required.
 */
export function isTrustedUserEvent(
  event: Event | React.SyntheticEvent,
  envMode: string = import.meta.env.MODE,
): boolean {
  if ((event as unknown as MaybeUntrustedFlag).__kwUntrustedSynthetic === true) {
    return false;
  }

  const native: Event =
    "nativeEvent" in event && event.nativeEvent ? event.nativeEvent : (event as Event);

  if ((native as unknown as MaybeUntrustedFlag).__kwUntrustedSynthetic === true) {
    return false;
  }

  if (native.isTrusted === true) {
    return true;
  }

  if (envMode === "test") {
    return true;
  }

  return false;
}
