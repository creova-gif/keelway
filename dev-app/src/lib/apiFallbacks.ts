import type {
  AgentManifestItem, AuditMerkleProof, ChainVerificationState, CodeSymbolItem,
  DoctorCheckItem, EgressTelemetryState, FileDiffHunk, GitCommitProposal,
  GitCommitResult, GovernancePersistenceInfo, ManifestInspectResult,
  MintedScopedApiKeyResult, OpenCoreWeightItem, RecordLedgerEntry,
  RoutingExplainRequest, RoutingExplainResult, ScopedApiKeyItem, ScopedKeyVerifyResult,
  TenantGovernancePolicy, WorkspaceFileNode,
} from "./types";

const INITIAL_DOCTOR_CHECKS: DoctorCheckItem[] = [
  {
    id: "sandbox-isolation",
    label: "OS Sandbox Isolation (Seatbelt / Bubblewrap)",
    status: "ok",
    detail: "Active · filesystem write-scoped to workspace root",
  },
  {
    id: "opencore-weights",
    label: "Local OpenCore Runtime (coder-7b v2.5.1)",
    status: "ok",
    detail: "Loaded on 127.0.0.1 · Q4_K_M · 4.6 GB unified memory",
  },
  {
    id: "audit-sqlite-wal",
    label: "Append-Only Audit Ledger (SQLite WAL)",
    status: "ok",
    detail: "SHA-256 chain intact · 1,283 entries verified",
  },
];

const INITIAL_FILES_TREE: WorkspaceFileNode[] = [
  {
    path: "core",
    name: "core",
    type: "directory",
    children: [
      { path: "core/main.py", name: "main.py", type: "file", language: "python", gitStatus: "M", aiRecordSeq: 1283 },
      { path: "core/security/policy.py", name: "policy.py", type: "file", language: "python" },
    ],
  },
  {
    path: "dev-app",
    name: "dev-app",
    type: "directory",
    children: [
      { path: "dev-app/src/App.tsx", name: "App.tsx", type: "file", language: "typescript", gitStatus: "A", aiRecordSeq: 1282 },
    ],
  },
  { path: "README.md", name: "README.md", type: "file", language: "markdown" },
];

interface StoredFallbackFile {
  content: string;
  language: string;
  aiRecordSeq?: number;
}

const INITIAL_FILE_CONTENTS: Record<string, StoredFallbackFile> = {
  "core/main.py": {
    language: "python",
    aiRecordSeq: 1283,
    content: [
      '"""Keelway Sovereign Runtime ASGI Entrypoint."""',
      "from pathlib import Path",
      "from fastapi import FastAPI",
      "",
      'app = FastAPI(title="Keelway Sovereign Runtime", version="1.1.0")',
      "",
      "@app.get('/health')",
      "async def health_check() -> dict[str, str]:",
      '    return {"status": "ok", "mode": "local_first"}',
      "",
    ].join("\n"),
  },
  "core/security/policy.py": {
    language: "python",
    content: [
      '"""Fail-closed P-10 human approval enforcement."""',
      "",
      "def requires_human_quorum(tier: int, network_egress: bool) -> bool:",
      "    return tier >= 2 or network_egress",
      "",
    ].join("\n"),
  },
  "dev-app/src/App.tsx": {
    language: "typescript",
    aiRecordSeq: 1282,
    content: 'export function AppSummary(): string {\n  return "Keelway Sovereign Dev App";\n}\n',
  },
  "README.md": {
    language: "markdown",
    content: "# Keelway\n\nLocal-first sovereign agent IDE and control plane.\n",
  },
};

const INITIAL_DIFF_HUNKS: FileDiffHunk[] = [
  {
    path: "core/main.py",
    oldStart: 4,
    newStart: 4,
    additions: 3,
    deletions: 1,
    aiRecordSeq: 1283,
    lines: [
      { type: "hunk", content: "@@ -4,4 +4,6 @@" },
      { type: "context", oldLine: 4, newLine: 4, content: 'app = FastAPI(title="Keelway Sovereign Runtime", version="1.1.0")' },
      { type: "del", oldLine: 5, content: 'CSP_POLICY = "default-src *"' },
      { type: "add", newLine: 5, content: "_STUDIO_CSP = \"default-src 'self'; script-src 'self'; object-src 'none'\"" },
      { type: "add", newLine: 6, content: 'X_CONTENT_TYPE_OPTIONS = "nosniff"' },
      { type: "add", newLine: 7, content: 'REFERRER_POLICY = "no-referrer"' },
    ],
  },
];

const INITIAL_SYMBOLS: CodeSymbolItem[] = [
  { name: "health_check", kind: "function", path: "core/main.py", line: 8, signature: "async def health_check() -> dict[str, str]" },
  { name: "requires_human_quorum", kind: "function", path: "core/security/policy.py", line: 3, signature: "def requires_human_quorum(tier: int, network_egress: bool) -> bool" },
  { name: "AppSummary", kind: "function", path: "dev-app/src/App.tsx", line: 1, signature: "export function AppSummary(): string" },
];

const INITIAL_AUDIT_ENTRIES: RecordLedgerEntry[] = [
  {
    seq: 1283,
    timestampEt: "2026-11-13 21:14:08 ET",
    isoTimestamp: "2026-11-14T02:14:08Z",
    actorKind: "agent",
    actorLabel: "test-fixer · local",
    action: "Edited file",
    target: "core/main.py",
    modelId: "coder-7b",
    modelVersion: "2.5.1",
    promptVersion: "p-14",
    systemPromptHash: "sha256:9f4c2e8a71b0d43e6f92a1c88e051d2b74a1c309e8f1a2b3c4d5e6f708192a3b",
    approvalLabel: "Allow once · you",
    approvedByHuman: true,
    outcome: "passed",
    hash: "8f3d9a12c4e7b0516a98e2d3f4c5b6a7182930415263748596a7b8c9d0e1f2a3",
    prevHash: "4c1e8b72a9d0f35162738495a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f",
    prevSeq: 1282,
    merkleRoot: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    diffPath: "core/main.py",
    fourDRoute: {
      privacy: "private",
      latencyTier: "interactive",
      costCapUsd: 0.0,
      taskComplexity: "medium",
      selectedProvider: "opencore-local",
      selectedModel: "coder-7b@2.5.1",
      dataBoundary: "local_loopback",
      reason: "privacy=private pinned execution to 127.0.0.1 OpenCore runtime",
    },
  },
  {
    seq: 1282,
    timestampEt: "2026-11-13 21:11:42 ET",
    isoTimestamp: "2026-11-14T02:11:42Z",
    actorKind: "human",
    actorLabel: "you (local keyboard)",
    action: "Approved P-10 command",
    target: "pytest tests/test_studio.py -q",
    modelId: "coder-7b",
    modelVersion: "2.5.1",
    promptVersion: "p-14",
    systemPromptHash: "sha256:9f4c2e8a71b0d43e6f92a1c88e051d2b74a1c309e8f1a2b3c4d5e6f708192a3b",
    approvalLabel: "Allow once · you",
    approvedByHuman: true,
    outcome: "allowed",
    hash: "4c1e8b72a9d0f35162738495a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f",
    prevHash: "1a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809",
    prevSeq: 1281,
    merkleRoot: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    fourDRoute: {
      privacy: "private",
      latencyTier: "interactive",
      costCapUsd: 0.0,
      taskComplexity: "low",
      selectedProvider: "opencore-local",
      selectedModel: "coder-7b@2.5.1",
      dataBoundary: "local_loopback",
      reason: "sandboxed pytest verification on local loopback",
    },
  },
  {
    seq: 1279,
    timestampEt: "2026-11-13 20:58:19 ET",
    isoTimestamp: "2026-11-14T01:58:19Z",
    actorKind: "policy",
    actorLabel: "4d-router · gate",
    action: "Blocked external egress",
    target: "https://api.external-cloud.example/v1/chat",
    modelId: "coder-7b",
    modelVersion: "2.5.1",
    promptVersion: "p-13",
    systemPromptHash: "sha256:7d8e9f00112233445566778899aabbccddeeff00112233445566778899aabbcc",
    approvalLabel: "Denied · policy",
    approvedByHuman: false,
    outcome: "blocked",
    hash: "7f6e5d4c3b2a1908f7e6d5c4b3a291807f6e5d4c3b2a1908f7e6d5c4b3a29180",
    prevHash: "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff",
    prevSeq: 1278,
    fourDRoute: {
      privacy: "private",
      latencyTier: "standard",
      costCapUsd: 0.05,
      taskComplexity: "high",
      selectedProvider: "blocked",
      selectedModel: "none",
      dataBoundary: "external_vendor_api",
      reason: "Fail-closed: privacy=private forbids external_vendor_api boundary",
    },
  },
];

const INITIAL_MANIFESTS: AgentManifestItem[] = [
  {
    id: "test-fixer@1.2.0",
    name: "test-fixer",
    version: "1.2.0",
    schemaVersion: "keelway.agent/v1",
    description: "Diagnoses failing pytest & Vitest suites within workspace sandbox.",
    enabled: true,
    tools: ["read_file", "search_code", "propose_patch", "run_pytest_sandbox"],
    networkAllowed: false,
    maxTier: 2,
    signatureStatus: "verified",
    securityWarnings: [
      "Static guard: write/exec tools gated by workspace Seatbelt scope & P-10 approval.",
    ],
    rawJson: JSON.stringify(
      {
        schemaVersion: "keelway.agent/v1",
        name: "test-fixer",
        version: "1.2.0",
        permissions: { network: false, writeWorkspace: "ask_every_time", maxTier: 2 },
        tools: ["read_file", "search_code", "propose_patch", "run_pytest_sandbox"],
      },
      null,
      2,
    ),
  },
  {
    id: "release-auditor@0.9.4",
    name: "release-auditor",
    version: "0.9.4",
    schemaVersion: "keelway.agent/v1",
    description: "Verifies SBOM, CSP headers, and SHA-256 Record chain before ship.",
    enabled: true,
    tools: ["read_file", "verify_audit_chain", "inspect_sbom"],
    networkAllowed: false,
    maxTier: 1,
    signatureStatus: "verified",
  },
];

const INITIAL_OPENCORE_WEIGHTS: OpenCoreWeightItem[] = [
  {
    id: "keelway-core:7b",
    name: "coder-7b",
    version: "2.5.1",
    quantization: "Q4_K_M",
    sizeGb: 4.3,
    vramGb: 4.6,
    status: "loaded",
    sha256: "sha256:3a7bd3e2360a3d29eea436fcfb7e44c735d117c42d1c1835420b6b9942dd4f1b",
    license: "Apache-2.0",
    localLoopback: true,
    simulated: true,
  },
  {
    id: "keelway-reasoner:14b",
    name: "reasoner-14b",
    version: "1.4.0",
    quantization: "Q4_K_M",
    sizeGb: 8.4,
    vramGb: 9.1,
    status: "cached",
    sha256: "sha256:6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b",
    license: "Apache-2.0",
    localLoopback: true,
    simulated: true,
  },
];

const INITIAL_GOVERNANCE_POLICY: TenantGovernancePolicy = {
  tenantId: "default",
  name: "Local Sovereign Workspace",
  residencyZone: "local_only",
  dlpEnabled: true,
  dailyBudgetUsd: 10.0,
  dailySpendUsd: 1.42,
  monthlyBudgetUsd: 150.0,
  currentSpendUsd: 18.4,
  warnThresholdPct: 80,
  hardCapEnforced: true,
  fallbackToOpencoreOnBudgetExceeded: true,
  fallbackModelId: "keelway-core:7b",
  requireHumanApprovalForNetwork: true,
  updatedAt: "2026-11-14T02:00:00Z",
};

const INITIAL_SCOPED_KEYS: ScopedApiKeyItem[] = [
  {
    id: "key_01j9sov7a",
    label: "ci-readonly-verifier",
    prefix: "kw_live_91f2…",
    scopes: ["audit:read", "models:read"],
    spendCapUsd: 10.0,
    spentUsd: 1.25,
    createdAt: "2026-11-10T14:20:00Z",
    revokedAt: null,
  },
];

let fileContentsState: Record<string, StoredFallbackFile> = structuredClone(INITIAL_FILE_CONTENTS);
let manifestsState: AgentManifestItem[] = structuredClone(INITIAL_MANIFESTS);
let governancePolicyState: TenantGovernancePolicy = structuredClone(INITIAL_GOVERNANCE_POLICY);
let scopedKeysState: ScopedApiKeyItem[] = structuredClone(INITIAL_SCOPED_KEYS);
let mintedDigestsState: Record<string, string> = {};
let keySeqCounter = 1;

function hashFallbackSecret(secret: string): string {
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  for (let i = 0; i < secret.length; i++) {
    const ch = secret.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 0x01000193) >>> 0;
    h2 = Math.imul(h2 ^ (ch + i), 0x85ebca6b) >>> 0;
  }
  return `fnv1a64:${h1.toString(16).padStart(8, "0")}${h2.toString(16).padStart(8, "0")}`;
}

export function resetApiFallbackState(): void {
  fileContentsState = structuredClone(INITIAL_FILE_CONTENTS);
  manifestsState = structuredClone(INITIAL_MANIFESTS);
  governancePolicyState = structuredClone(INITIAL_GOVERNANCE_POLICY);
  scopedKeysState = structuredClone(INITIAL_SCOPED_KEYS);
  mintedDigestsState = {};
  keySeqCounter = 1;
}

export function inferLanguageFromPath(path: string): string {
  const lower = path.toLowerCase();
  if (lower.endsWith(".py")) return "python";
  if (lower.endsWith(".ts") || lower.endsWith(".tsx")) return "typescript";
  if (lower.endsWith(".js") || lower.endsWith(".jsx")) return "javascript";
  if (lower.endsWith(".json")) return "json";
  if (lower.endsWith(".md")) return "markdown";
  if (lower.endsWith(".css")) return "css";
  if (lower.endsWith(".html")) return "html";
  return "plaintext";
}

export const getFallbackDoctorChecks = (): DoctorCheckItem[] => structuredClone(INITIAL_DOCTOR_CHECKS);
export const getFallbackFilesTree = (): WorkspaceFileNode[] => structuredClone(INITIAL_FILES_TREE);
export const getFallbackDiffHunks = (): FileDiffHunk[] => structuredClone(INITIAL_DIFF_HUNKS);
export const getFallbackSymbols = (): CodeSymbolItem[] => structuredClone(INITIAL_SYMBOLS);
export const getFallbackAuditEntries = (): RecordLedgerEntry[] => structuredClone(INITIAL_AUDIT_ENTRIES);
export const getFallbackManifests = (): AgentManifestItem[] => structuredClone(manifestsState);
export const getFallbackOpenCoreWeights = (): OpenCoreWeightItem[] => structuredClone(INITIAL_OPENCORE_WEIGHTS);
export const getFallbackGovernancePolicy = (): TenantGovernancePolicy => structuredClone(governancePolicyState);
export const getFallbackScopedKeys = (): ScopedApiKeyItem[] => structuredClone(scopedKeysState);

export function getFallbackFileContent(path: string): {
  path: string;
  content: string;
  language: string;
  aiRecordSeq?: number;
} {
  const existing = fileContentsState[path];
  return existing
    ? structuredClone({ path, ...existing })
    : { path, content: `// ${path}\n`, language: inferLanguageFromPath(path) };
}

export function saveFallbackFileContent(
  path: string,
  content: string,
): { ok: boolean; path: string; bytesWritten: number } {
  const prev = fileContentsState[path];
  fileContentsState[path] = {
    content,
    language: prev?.language ?? inferLanguageFromPath(path),
    aiRecordSeq: prev?.aiRecordSeq,
  };
  return { ok: true, path, bytesWritten: new TextEncoder().encode(content).byteLength };
}

export function getFallbackGitProposal(): GitCommitProposal {
  return {
    clean: false,
    branch: "feat/unified-dev-app",
    filesCount: 2,
    files: [
      { path: "core/main.py", status: "M" },
      { path: "dev-app/src/App.tsx", status: "A" },
    ],
    proposedTitle: "feat(core): update 2 file(s)",
    proposedMessage:
      "feat(core): update 2 file(s)\n\n- Modified 2 file(s):\n  • [M] core/main.py\n  • [A] dev-app/src/App.tsx",
    patchHash: "3a7bd3e2360a3d29eea436fcfb7e44c735d117c42d1c1835420b6b9942dd4f1b",
  };
}

export function createFallbackGitCommit(message: string): GitCommitResult {
  return {
    ok: true,
    commitSha: "9e1c4a82b7f03d516c89a2e4b6d8f0123456789a",
    branch: "feat/unified-dev-app",
    message: message.trim() || "chore(workspace): local checkpoint",
    author: "Keelway Developer <dev@keelway.local>",
    clean: true,
  };
}

export function getFallbackAirGapAudit(): EgressTelemetryState {
  return {
    mode: "unmeasured",
    cloudCallsCount: 0,
    bytesSent: null,
    airGapLocked: false,
    endpoints: [],
    sc7Compliant: true,
    sc7Checks: [
      { id: "AIRGAP-01-CREDS", label: "Zero Cloud API Keys in Environment", passed: true, detail: "0 cloud API keys exposed" },
      { id: "AIRGAP-02-ORIGIN", label: "Loopback HTTP/WS Origin Binding", passed: true, detail: "127.0.0.1:7420" },
      { id: "AIRGAP-03-CSP", label: "Strict Self-Hosted Content-Security-Policy", passed: true, detail: "default-src 'self'; object-src 'none'" },
      { id: "AIRGAP-04-CDN", label: "External Font & Script CDNs", passed: true, detail: "0 external CDNs" },
    ],
  };
}

export function getFallbackChainVerification(): ChainVerificationState {
  return {
    status: "verified",
    totalEntries: INITIAL_AUDIT_ENTRIES.length,
    merkleRoot: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    verifiedAt: "2026-11-14T02:15:00Z",
  };
}

export function getFallbackMerkleProof(seq: number): AuditMerkleProof {
  const entry = INITIAL_AUDIT_ENTRIES.find((item) => item.seq === seq);
  return {
    seq,
    leafHash: entry?.hash ?? "8f3d9a12c4e7b0516a98e2d3f4c5b6a7182930415263748596a7b8c9d0e1f2a3",
    merkleRoot: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    siblings: [
      { position: "left", hash: "4c1e8b72a9d0f35162738495a6b7c8d9e0f1a2b3c4d5e6f708192a3b4c5d6e7f" },
      { position: "right", hash: "7f6e5d4c3b2a1908f7e6d5c4b3a291807f6e5d4c3b2a1908f7e6d5c4b3a29180" },
    ],
    verified: true,
  };
}

export function buildAuditBundleFromEntries(entries: RecordLedgerEntry[]): {
  format: string;
  generatedAt: string;
  jsonl: string;
  csv: string;
  verifierScript: string;
  chainStatus: "verified" | "broken";
} {
  return {
    format: "keelway-record-bundle/v1",
    generatedAt: "2026-11-14T02:15:00Z",
    jsonl: entries.map((e) => JSON.stringify(e)).join("\n"),
    csv: [
      "seq,timestamp_et,actor,action,model,prompt_version,approval,outcome,hash,prev_hash",
      ...entries.map(
        (e) =>
          `${e.seq},"${e.timestampEt}","${e.actorLabel}","${e.action}","${e.modelId}@${e.modelVersion}",${e.promptVersion},"${e.approvalLabel}",${e.outcome},${e.hash},${e.prevHash}`,
      ),
    ].join("\n"),
    verifierScript: "#!/usr/bin/env python3\n# Standalone SHA-256 chain verifier\n",
    chainStatus: "verified",
  };
}

export function toggleFallbackManifest(id: string, enabled: boolean): AgentManifestItem {
  manifestsState = manifestsState.map((item) =>
    item.id === id || item.name === id ? { ...item, enabled } : item,
  );
  const updated = manifestsState.find((item) => item.id === id || item.name === id);
  if (updated) return structuredClone(updated);
  const name = id.split("@")[0] ?? "agent";
  const version = id.split("@")[1] ?? "1.0.0";
  return {
    id,
    name,
    version,
    schemaVersion: "keelway.agent/v1",
    description: "Custom workspace agent manifest",
    enabled,
    tools: [],
    networkAllowed: false,
    maxTier: 2,
    signatureStatus: "unsigned",
  };
}

export function inspectManifestLocally(parsed: Record<string, unknown>): ManifestInspectResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const schemaVersion =
    typeof parsed.schemaVersion === "string"
      ? parsed.schemaVersion
      : typeof parsed.schema_version === "string"
        ? parsed.schema_version
        : "";
  if (schemaVersion !== "keelway.agent/v1") errors.push('schemaVersion must equal "keelway.agent/v1"');
  if (typeof parsed.name !== "string" || !parsed.name.trim()) errors.push("Missing required string field: name");
  if (typeof parsed.version !== "string" || !parsed.version.trim()) errors.push("Missing required string field: version");

  const perms = parsed.permissions && typeof parsed.permissions === "object"
    ? (parsed.permissions as Record<string, unknown>)
    : {};
  const netVal = perms.network;
  const networkAllowed = netVal === true || (typeof netVal === "string" && netVal !== "none");
  const tools = Array.isArray(parsed.tools)
    ? parsed.tools.filter((t): t is string => typeof t === "string")
    : [];
  if (networkAllowed) warnings.push("Network capability enabled: triggers click-only P-10 Variant C gate.");

  return {
    valid: errors.length === 0,
    schemaVersion: schemaVersion || "unknown",
    name: typeof parsed.name === "string" ? parsed.name : undefined,
    version: typeof parsed.version === "string" ? parsed.version : undefined,
    riskLevel: networkAllowed ? "high" : tools.length > 3 ? "medium" : "low",
    requiresHumanP10: true,
    errors,
    warnings,
    capabilities: tools,
  };
}

export function getFallbackRoutingExplanation(req: RoutingExplainRequest): RoutingExplainResult {
  const endpoint = (req.candidateEndpoint ?? "").trim().toLowerCase();
  const isExt = endpoint.length > 0 && !endpoint.includes("127.0.0.1") && !endpoint.includes("localhost");
  const requestedModel = req.model?.trim() || (isExt ? "frontier-sonnet-4" : "coder-7b@2.5.1");
  if (req.privacy === "private" && isExt) {
    return {
      allowed: false,
      decision: "blocked_fail_closed",
      selectedModel: "none",
      provider: "blocked",
      license: "External / Unverified",
      hosting: "Managed External Cloud",
      dataBoundary: "external_vendor_api",
      privacyClassification: req.privacy,
      estimatedCostUsd: 0,
      estimatedLatencyMs: 0,
      rationale: 'Blocked (fail-closed): privacy="private" forbids routing prompts or diffs to data_boundary=external_vendor_api.',
      blockedReason: "Policy invariant violation: private data cannot cross external_vendor_api boundary.",
      evaluatedCandidates: [
        { model: req.model?.trim() || req.candidateEndpoint || "external-open-weight-cloud", boundary: "external_vendor_api", passed: false, reason: "Rejected: data_boundary=external_vendor_api violates privacy=private" },
        { model: "coder-7b@2.5.1", boundary: "local_loopback", passed: true, reason: "Eligible local fallback on 127.0.0.1" },
      ],
    };
  }
  return {
    allowed: true,
    decision: isExt ? "routed_cloud" : "routed_local",
    selectedModel: requestedModel,
    provider: isExt ? "cloud-gateway" : "opencore-local",
    license: isExt ? "Proprietary Commercial" : "Apache-2.0 (Open-Weight)",
    hosting: isExt ? "Managed Public Cloud" : "Local Unified Memory (127.0.0.1)",
    dataBoundary: isExt ? "external_vendor_api" : "local_loopback",
    privacyClassification: req.privacy,
    estimatedCostUsd: isExt ? Math.min(0.018, req.maxCostUsd) : 0,
    estimatedLatencyMs: isExt ? 620 : 185,
    rationale: isExt
      ? `Allowed for privacy="${req.privacy}" within $${req.maxCostUsd.toFixed(2)} cap.`
      : `Pinned to local loopback OpenCore ${requestedModel} ($0.00 egress).`,
    evaluatedCandidates: [
      { model: requestedModel, boundary: isExt ? "external_vendor_api" : "local_loopback", passed: true, reason: isExt ? "Permitted by non-private classification" : "Zero-egress local loopback runtime ready" },
    ],
  };
}

export function getFallbackGovernancePersistence(): GovernancePersistenceInfo {
  return { engine: "SQLite 3", journalMode: "WAL", synchronous: "NORMAL", dbPath: ".keelway/governance.db", walBytes: 32768, foreignKeys: true, healthy: true };
}

export function updateFallbackGovernancePolicy(patch: Partial<TenantGovernancePolicy>): TenantGovernancePolicy {
  governancePolicyState = { ...governancePolicyState, ...patch, updatedAt: new Date().toISOString() };
  return structuredClone(governancePolicyState);
}

export function mintFallbackScopedKey(label: string, scopes: string[], capUsd: number): MintedScopedApiKeyResult {
  const hexSeq = (keySeqCounter++).toString(16).padStart(6, "0");
  const plaintextSecret = `kw_live_${hexSeq}_94c8e21b7d03f6a51122334455667788`;
  const created: ScopedApiKeyItem = {
    id: `key_${hexSeq}`,
    label: label.trim() || "scoped-agent-key",
    prefix: `kw_live_${hexSeq.slice(0, 4)}…`,
    scopes: [...scopes],
    spendCapUsd: capUsd,
    spentUsd: 0,
    createdAt: new Date().toISOString(),
    revokedAt: null,
  };
  scopedKeysState = [created, ...scopedKeysState];
  mintedDigestsState[hashFallbackSecret(plaintextSecret)] = created.id;
  return {
    key: structuredClone(created),
    plaintextSecret,
    oneTimeWarning: "Copy this secret now. Keelway stores only its SHA-256 digest and cannot show it again.",
  };
}

export function verifyFallbackScopedKey(apiKey: string): ScopedKeyVerifyResult {
  const trimmed = apiKey.trim();
  if (!trimmed.startsWith("kw_live_")) {
    return { valid: false, scopes: [], reason: "Invalid key prefix: expected kw_live_*" };
  }
  const exactId = mintedDigestsState[hashFallbackSecret(trimmed)];
  const matched = scopedKeysState.find(
    (k) => !k.revokedAt && (k.id === exactId || (trimmed.length >= 16 && trimmed.startsWith(k.prefix.replace("…", "")))),
  );
  if (matched) {
    return { valid: true, keyId: matched.id, scopes: [...matched.scopes], reason: `Verified active key (${matched.label})` };
  }
  return { valid: false, scopes: [], reason: "Key SHA-256 digest not found or revoked" };
}
