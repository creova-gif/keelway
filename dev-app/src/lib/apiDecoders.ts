import type {
  AgentManifestItem, AuditMerkleProof, ChainVerificationState, CodeSymbolItem, DataResidencyZone,
  DoctorCheckItem, EgressTelemetryState, FileDiffHunk, GitCommitProposal, GitCommitResult,
  GovernancePersistenceInfo, ManifestInspectResult, MintedScopedApiKeyResult, OpenCoreWeightItem,
  P10DiffLine, RecordLedgerEntry, RoutingExplainRequest, RoutingExplainResult, ScopedApiKeyItem,
  TenantGovernancePolicy, WorkspaceFileNode,
} from "./types";
import { inferLanguageFromPath } from "./apiFallbacks";

export function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

export function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function normalizeDoctorStatus(rawStatus: unknown): DoctorCheckItem["status"] {
  const upper = asString(rawStatus, "OK").toUpperCase();
  if (upper === "OK" || upper === "PASS" || upper === "HEALTHY") return "ok";
  if (upper === "WARN" || upper === "WARNING" || upper === "DEGRADED") return "warning";
  return "failed";
}

export function decodeDoctorChecks(raw: unknown): DoctorCheckItem[] | null {
  const items = Array.isArray(raw)
    ? raw
    : isRecord(raw) && Array.isArray(raw.checks)
      ? raw.checks
      : isRecord(raw) && Array.isArray(raw.sections)
        ? raw.sections
        : null;
  if (!items) return null;

  return items.filter(isRecord).map((item, idx): DoctorCheckItem => {
    const label = asString(item.label) || asString(item.name) || `Diagnostic #${idx + 1}`;
    const id =
      asString(item.id) ||
      label
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");
    let detail = asString(item.detail);
    if (!detail && isRecord(item.details)) {
      detail = Object.entries(item.details)
        .slice(0, 3)
        .map(([k, v]) => `${k}=${String(v)}`)
        .join(" · ");
    }
    return {
      id: id || `check-${idx}`,
      label,
      status:
        item.status === "ok" || item.status === "warning" || item.status === "failed"
          ? item.status
          : normalizeDoctorStatus(item.status),
      detail: detail || "Verified",
      remediation: typeof item.remediation === "string" ? item.remediation : undefined,
    };
  });
}

function decodeFileNode(raw: unknown): WorkspaceFileNode | null {
  if (!isRecord(raw)) return null;
  const path = asString(raw.path);
  const name = asString(raw.name) || path.split("/").pop() || "";
  if (!name && !path) return null;
  const rawType = asString(raw.type, Array.isArray(raw.children) ? "directory" : "file");
  const type: WorkspaceFileNode["type"] =
    rawType === "directory" || rawType === "dir" ? "directory" : "file";
  const rawGit = asString(raw.gitStatus || raw.git_status);
  const gitStatus =
    rawGit === "M" || rawGit === "A" || rawGit === "D" || rawGit === "U" ? rawGit : undefined;
  const children = Array.isArray(raw.children)
    ? raw.children.map(decodeFileNode).filter((n): n is WorkspaceFileNode => n !== null)
    : undefined;

  return {
    path: path || name,
    name,
    type,
    language:
      typeof raw.language === "string"
        ? raw.language
        : type === "file"
          ? inferLanguageFromPath(path || name)
          : undefined,
    gitStatus,
    dirty: typeof raw.dirty === "boolean" ? raw.dirty : undefined,
    saveError: typeof raw.saveError === "string" ? raw.saveError : undefined,
    aiRecordSeq:
      typeof raw.aiRecordSeq === "number"
        ? raw.aiRecordSeq
        : typeof raw.ai_record_seq === "number"
          ? raw.ai_record_seq
          : undefined,
    children,
  };
}

export function decodeFilesTree(raw: unknown): WorkspaceFileNode[] | null {
  if (Array.isArray(raw)) {
    return raw.map(decodeFileNode).filter((n): n is WorkspaceFileNode => n !== null);
  }
  if (isRecord(raw)) {
    const source = Array.isArray(raw.children)
      ? raw.children
      : Array.isArray(raw.tree)
        ? raw.tree
        : null;
    if (source) {
      return source.map(decodeFileNode).filter((n): n is WorkspaceFileNode => n !== null);
    }
  }
  return null;
}

function decodeDiffHunk(raw: unknown): FileDiffHunk | null {
  if (!isRecord(raw) || typeof raw.path !== "string") return null;
  const rawLines = Array.isArray(raw.lines) ? raw.lines : [];
  const lines: P10DiffLine[] = rawLines.filter(isRecord).map((line) => {
    const rawType = asString(line.type, "context");
    const type: P10DiffLine["type"] =
      rawType === "add" || rawType === "del" || rawType === "hunk" ? rawType : "context";
    return {
      type,
      oldLine:
        typeof line.oldLine === "number"
          ? line.oldLine
          : typeof line.old === "number"
            ? line.old
            : undefined,
      newLine:
        typeof line.newLine === "number"
          ? line.newLine
          : typeof line.new === "number"
            ? line.new
            : undefined,
      content: typeof line.content === "string" ? line.content : asString(line.text),
    };
  });

  return {
    path: raw.path,
    oldStart: asNumber(raw.oldStart ?? raw.old_start, 1),
    newStart: asNumber(raw.newStart ?? raw.new_start, 1),
    additions: asNumber(raw.additions, 0),
    deletions: asNumber(raw.deletions, 0),
    aiRecordSeq:
      typeof raw.aiRecordSeq === "number"
        ? raw.aiRecordSeq
        : typeof raw.ai_record_seq === "number"
          ? raw.ai_record_seq
          : undefined,
    lines,
  };
}

export function decodeStudioDiff(raw: unknown): FileDiffHunk[] | null {
  const source = Array.isArray(raw)
    ? raw
    : isRecord(raw) && Array.isArray(raw.files)
      ? raw.files
      : null;
  return source ? source.map(decodeDiffHunk).filter((h): h is FileDiffHunk => h !== null) : null;
}

export function decodeSymbols(raw: unknown): CodeSymbolItem[] | null {
  const list = Array.isArray(raw)
    ? raw
    : isRecord(raw) && Array.isArray(raw.results)
      ? raw.results
      : isRecord(raw) && Array.isArray(raw.symbols)
        ? raw.symbols
        : null;
  if (!list) return null;

  const validKinds = new Set(["function", "class", "interface", "variable", "method", "type"]);
  return list
    .filter(isRecord)
    .map((item): CodeSymbolItem | null => {
      const name = asString(item.name || item.symbol);
      const path = asString(item.path || item.file_path || item.file);
      if (!name || !path) return null;
      const rawKind = asString(item.kind, "function").toLowerCase();
      return {
        name,
        kind: (validKinds.has(rawKind) ? rawKind : "function") as CodeSymbolItem["kind"],
        path,
        line: asNumber(item.line ?? item.start_line, 1),
        signature: typeof item.signature === "string" ? item.signature : undefined,
      };
    })
    .filter((s): s is CodeSymbolItem => s !== null);
}

export function decodeGitProposal(raw: unknown): GitCommitProposal | null {
  if (!isRecord(raw)) return null;
  const files = Array.isArray(raw.files)
    ? raw.files
        .filter(isRecord)
        .map((f) => ({ path: asString(f.path), status: asString(f.status, "M") }))
        .filter((f) => f.path.length > 0)
    : [];
  const proposedMessage = asString(raw.proposedMessage || raw.proposed_message || raw.message);
  return {
    clean: Boolean(raw.clean),
    branch: asString(raw.branch, "HEAD"),
    filesCount: asNumber(raw.filesCount ?? raw.files_count, files.length),
    files,
    proposedTitle:
      asString(raw.proposedTitle || raw.proposed_title) || proposedMessage.split("\n")[0] || "",
    proposedMessage,
    patchHash: asString(raw.patchHash || raw.patch_hash),
    diffPreview:
      typeof raw.diffPreview === "string"
        ? raw.diffPreview
        : typeof raw.diff_preview === "string"
          ? raw.diff_preview
          : undefined,
  };
}

export function decodeGitCommitResult(raw: unknown, fallbackMsg: string): GitCommitResult | null {
  if (!isRecord(raw)) return null;
  const commitSha = asString(raw.commitSha || raw.commit_sha);
  if (!commitSha) return null;
  return {
    ok: typeof raw.ok === "boolean" ? raw.ok : raw.status === "committed",
    commitSha,
    branch: asString(raw.branch, "HEAD"),
    message: asString(raw.message, fallbackMsg),
    author: asString(raw.author, "Keelway Developer"),
    clean: typeof raw.clean === "boolean" ? raw.clean : true,
  };
}

export function decodeManifestItem(raw: unknown): AgentManifestItem | null {
  if (!isRecord(raw)) return null;
  const name = asString(raw.name);
  const version = asString(raw.version, "1.0.0");
  const id = asString(raw.id) || (name ? `${name}@${version}` : "");
  if (!id) return null;

  const gov = isRecord(raw.governance_summary) ? raw.governance_summary : {};
  const rawTools = Array.isArray(raw.tools)
    ? raw.tools
    : Array.isArray(gov.tools)
      ? gov.tools
      : [];
  const networkAllowed =
    typeof raw.networkAllowed === "boolean"
      ? raw.networkAllowed
      : typeof raw.network_allowed === "boolean"
        ? raw.network_allowed
        : typeof gov.network === "string"
          ? gov.network !== "none"
          : Boolean(gov.network);
  const rawSig = asString(raw.signatureStatus || raw.signature_status, "unsigned");
  const signatureStatus: AgentManifestItem["signatureStatus"] =
    rawSig === "verified" || rawSig === "valid"
      ? "verified"
      : rawSig.startsWith("invalid")
        ? "invalid"
        : "unsigned";
  const tierNum = asNumber(raw.maxTier ?? raw.max_tier ?? gov.max_tier, 2);
  const rawWarnings = Array.isArray(raw.securityWarnings)
    ? raw.securityWarnings
    : Array.isArray(raw.security_warnings)
      ? raw.security_warnings
      : undefined;

  return {
    id,
    name: name || id,
    version,
    schemaVersion: "keelway.agent/v1",
    description: asString(raw.description),
    enabled: typeof raw.enabled === "boolean" ? raw.enabled : true,
    tools: rawTools.filter((t): t is string => typeof t === "string"),
    networkAllowed,
    maxTier: tierNum <= 1 ? 1 : tierNum >= 3 ? 3 : 2,
    signatureStatus,
    securityWarnings: rawWarnings
      ? rawWarnings.filter((w): w is string => typeof w === "string")
      : undefined,
    rawJson:
      typeof raw.rawJson === "string"
        ? raw.rawJson
        : typeof raw.canonical_json === "string"
          ? raw.canonical_json
          : undefined,
  };
}

export function decodeManifestList(raw: unknown): AgentManifestItem[] | null {
  const list = Array.isArray(raw)
    ? raw
    : isRecord(raw) && Array.isArray(raw.manifests)
      ? raw.manifests
      : null;
  return list ? list.map(decodeManifestItem).filter((m): m is AgentManifestItem => m !== null) : null;
}

export function decodeManifestInspectResult(
  raw: unknown,
  parsedManifest: Record<string, unknown>,
): ManifestInspectResult | null {
  if (!isRecord(raw) || typeof raw.valid !== "boolean") return null;
  const gov = isRecord(raw.governance_summary) ? raw.governance_summary : {};
  const errors = Array.isArray(raw.errors)
    ? raw.errors.filter((e): e is string => typeof e === "string")
    : [];
  const warningsSource = Array.isArray(raw.warnings)
    ? raw.warnings
    : Array.isArray(raw.security_warnings)
      ? raw.security_warnings
      : [];
  const capsSource = Array.isArray(raw.capabilities)
    ? raw.capabilities
    : Array.isArray(gov.tools)
      ? gov.tools
      : Array.isArray(parsedManifest.tools)
        ? parsedManifest.tools
        : [];
  const capabilities = capsSource.filter((c): c is string => typeof c === "string");
  const netAllowed =
    typeof gov.network === "string" ? gov.network !== "none" : Boolean(gov.network);
  const rawRisk = asString(raw.riskLevel || gov.risk_level);
  const riskLevel: ManifestInspectResult["riskLevel"] =
    rawRisk === "low" || rawRisk === "medium" || rawRisk === "high"
      ? rawRisk
      : !raw.valid || netAllowed
        ? "high"
        : capabilities.length > 3
          ? "medium"
          : "low";

  return {
    valid: raw.valid,
    schemaVersion: asString(
      raw.schemaVersion || raw.schema_version || parsedManifest.schemaVersion,
      "keelway.agent/v1",
    ),
    name: typeof raw.name === "string" ? raw.name : asString(parsedManifest.name) || undefined,
    version:
      typeof raw.version === "string" ? raw.version : asString(parsedManifest.version) || undefined,
    riskLevel,
    requiresHumanP10: typeof raw.requiresHumanP10 === "boolean" ? raw.requiresHumanP10 : true,
    errors,
    warnings: warningsSource.filter((w): w is string => typeof w === "string"),
    capabilities,
  };
}

export function decodeAuditEntry(raw: unknown, idx: number): RecordLedgerEntry | null {
  if (!isRecord(raw)) return null;
  const seq = typeof raw.seq === "number" ? raw.seq : idx + 1;
  const isoTimestamp = asString(raw.isoTimestamp || raw.timestamp, "2026-11-14T02:00:00Z");
  const rawRole = asString(raw.actorKind || raw.role, "agent").toLowerCase();
  const actorKind: RecordLedgerEntry["actorKind"] =
    rawRole === "human" || rawRole === "engineer" || rawRole === "admin"
      ? "human"
      : rawRole === "policy"
        ? "policy"
        : rawRole === "system"
          ? "system"
          : "agent";

  const allowedBool = typeof raw.allowed === "boolean" ? raw.allowed : true;
  const rawOutcome = asString(raw.outcome, allowedBool ? "allowed" : "denied");
  const validOutcomes = new Set(["passed", "ready", "allowed", "denied", "blocked", "failed"]);

  return {
    seq,
    timestampEt: asString(raw.timestampEt) || isoTimestamp,
    isoTimestamp,
    actorKind,
    actorLabel: asString(raw.actorLabel || raw.actor, "system"),
    action: asString(raw.action, "event"),
    target: asString(raw.target || raw.resource, "-"),
    modelId: asString(raw.modelId || raw.model_id, "coder-7b"),
    modelVersion: asString(raw.modelVersion || raw.model_version, "2.5.1"),
    promptVersion: asString(raw.promptVersion || raw.prompt_version, "p-14"),
    systemPromptHash: asString(
      raw.systemPromptHash || raw.system_prompt_hash,
      "sha256:9f4c2e8a71b0d43e6f92a1c88e051d2b74a1c309e8f1a2b3c4d5e6f708192a3b",
    ),
    approvalLabel: asString(
      raw.approvalLabel || raw.approval_label,
      allowedBool ? "Allow once · you" : "Denied · policy",
    ),
    approvedByHuman: typeof raw.approvedByHuman === "boolean" ? raw.approvedByHuman : allowedBool,
    outcome: (
      validOutcomes.has(rawOutcome) ? rawOutcome : allowedBool ? "allowed" : "denied"
    ) as RecordLedgerEntry["outcome"],
    hash: asString(raw.hash || raw.entry_hash, ""),
    prevHash: asString(raw.prevHash || raw.prev_hash, ""),
    prevSeq:
      typeof raw.prevSeq === "number"
        ? raw.prevSeq
        : typeof raw.prev_seq === "number"
          ? raw.prev_seq
          : seq > 1
            ? seq - 1
            : null,
    merkleRoot: asString(raw.merkleRoot || raw.merkle_root) || undefined,
    diffPath: asString(raw.diffPath || raw.diff_path) || undefined,
    fourDRoute: isRecord(raw.fourDRoute)
      ? (raw.fourDRoute as unknown as RecordLedgerEntry["fourDRoute"])
      : undefined,
  };
}

export function decodeChainVerification(raw: unknown): ChainVerificationState | null {
  if (!isRecord(raw)) return null;
  const status: ChainVerificationState["status"] =
    raw.status === "verified" || raw.status === "broken" || raw.status === "checking"
      ? raw.status
      : raw.valid === false || raw.ok === false || raw.chain_valid === false
        ? "broken"
        : "verified";
  const rawBroken = raw.brokenAtSeq ?? raw.broken_at_seq ?? raw.broken_at;
  return {
    status,
    totalEntries: asNumber(raw.totalEntries ?? raw.total_entries ?? raw.count, 0),
    brokenAtSeq: typeof rawBroken === "number" ? rawBroken : undefined,
    expectedPrevHash: asString(raw.expectedPrevHash || raw.expected_prev_hash) || undefined,
    actualPrevHash: asString(raw.actualPrevHash || raw.actual_prev_hash) || undefined,
    merkleRoot: asString(raw.merkleRoot || raw.merkle_root || raw.head_hash) || undefined,
    verifiedAt: asString(raw.verifiedAt || raw.verified_at, new Date().toISOString()),
  };
}

export function decodeMerkleProof(raw: unknown, fallbackSeq: number): AuditMerkleProof | null {
  if (!isRecord(raw)) return null;
  const rawSiblings = Array.isArray(raw.siblings) ? raw.siblings : Array.isArray(raw.proof) ? raw.proof : [];
  return {
    seq: asNumber(raw.seq, fallbackSeq),
    leafHash: asString(raw.leafHash || raw.leaf_hash),
    merkleRoot: asString(raw.merkleRoot || raw.merkle_root),
    siblings: rawSiblings.filter(isRecord).map((s) => ({
      position: s.position === "left" ? "left" : "right",
      hash: asString(s.hash),
    })),
    verified: typeof raw.verified === "boolean" ? raw.verified : true,
  };
}

function isEgressBarMode(v: unknown): v is EgressTelemetryState["mode"] {
  return v === "unmeasured" || v === "measured_offline" || v === "air_gapped_verified" || v === "unknown_probe_failed" || v === "connected_warning";
}

export function decodeAirGapAudit(raw: unknown): EgressTelemetryState | null {
  if (!isRecord(raw)) return null;
  const sc7Compliant =
    typeof raw.overall_compliant === "boolean"
      ? raw.overall_compliant
      : typeof raw.overallCompliant === "boolean"
        ? raw.overallCompliant
        : typeof raw.sc7Compliant === "boolean"
          ? raw.sc7Compliant
          : undefined;
  const checksList = Array.isArray(raw.sc7Checks) ? raw.sc7Checks : Array.isArray(raw.checks) ? raw.checks : null;
  const sc7Checks = checksList
    ? checksList.filter(isRecord).map((c, i) => ({
        id: asString(c.id || c.check_id, `sc7-${i + 1}`),
        label: asString(c.label || c.title || c.name, `SC-7 check #${i + 1}`),
        passed: Boolean(c.passed ?? c.compliant ?? c.ok ?? false),
        detail: asString(c.detail || c.details) || undefined,
      }))
    : isRecord(raw.checks)
      ? Object.entries(raw.checks).map(([k, v]) => ({
          id: k,
          label: isRecord(v) ? asString(v.label || v.title || v.name, k) : k,
          passed: typeof v === "boolean" ? v : isRecord(v) ? Boolean(v.passed ?? v.compliant ?? v.ok ?? false) : false,
          detail: isRecord(v) ? asString(v.detail || v.details) || undefined : undefined,
        }))
      : undefined;
  const endpoints = Array.isArray(raw.endpoints)
    ? raw.endpoints.filter(isRecord).map((e) => {
        const epBytes = e.bytesSent ?? e.bytes_sent ?? e.egressBytes ?? e.egress_bytes;
        return {
          host: asString(e.host || e.url, "unknown"),
          purpose: asString(e.purpose, "egress"),
          calls: asNumber(e.calls, 1),
          bytesSent: typeof epBytes === "number" && Number.isFinite(epBytes) ? epBytes : null,
          ...(typeof e.modelId === "string" ? { modelId: e.modelId } : {}),
        };
      })
    : [];
  const rawBytes = raw.bytes_sent ?? raw.bytesSent ?? raw.egress_bytes ?? raw.egressBytes;
  const bytesSent = typeof rawBytes === "number" && Number.isFinite(rawBytes) ? rawBytes : null;
  const cloudCallsCount = asNumber(raw.cloud_calls_count ?? raw.cloudCallsCount, endpoints.length);
  const airGapLocked = Boolean(raw.air_gap_enabled ?? raw.airGapLocked ?? raw.air_gapped ?? false);
  const mode: EgressTelemetryState["mode"] = isEgressBarMode(raw.mode)
    ? raw.mode
    : raw.mode === "air_gap_locked" || airGapLocked
      ? "air_gapped_verified"
      : cloudCallsCount > 0 || raw.offline === false
        ? "connected_warning"
        : bytesSent !== null
          ? "measured_offline"
          : "unmeasured";
  return {
    mode,
    cloudCallsCount,
    bytesSent,
    airGapLocked,
    endpoints,
    lastCheckedAt: asString(raw.timestamp_utc || raw.lastCheckedAt) || undefined,
    sc7Compliant,
    sc7Checks,
  };
}

export function decodeOpenCoreWeights(raw: unknown): OpenCoreWeightItem[] | null {
  if (!Array.isArray(raw)) return null;
  return raw
    .filter(isRecord)
    .map((w): OpenCoreWeightItem | null => {
      const id = asString(w.id || w.model_id);
      if (!id) return null;
      const status: OpenCoreWeightItem["status"] =
        w.status === "loaded" || w.status === "cached" || w.status === "available"
          ? w.status
          : w.is_cached === true
            ? "cached"
            : "available";
      return {
        id,
        name: asString(w.name, id),
        version: asString(w.version, "1.0.0"),
        quantization: asString(w.quantization || w.default_quantization, "Q4_K_M"),
        sizeGb: asNumber(w.sizeGb ?? w.size_gb, 4.3),
        vramGb: asNumber(w.vramGb ?? w.vram_gb ?? w.min_ram_gb, 4.6),
        status,
        sha256: asString(w.sha256, ""),
        license: asString(w.license, "Apache-2.0"),
        localLoopback: typeof w.localLoopback === "boolean" ? w.localLoopback : true,
        simulated: w.simulated === true,
        runtimeAlias: w.runtime_alias === true || w.runtimeAlias === true,
      };
    })
    .filter((item): item is OpenCoreWeightItem => item !== null);
}

export function decodeRoutingExplanation(
  raw: unknown,
  req: RoutingExplainRequest,
): RoutingExplainResult | null {
  if (!isRecord(raw)) return null;
  if (
    typeof raw.allowed === "boolean" &&
    typeof raw.decision === "string" &&
    Array.isArray(raw.evaluatedCandidates)
  ) {
    return raw as unknown as RoutingExplainResult;
  }

  if ("privacy_compliant" in raw || "governance_provenance" in raw || "decision_id" in raw) {
    const prov = isRecord(raw.governance_provenance) ? raw.governance_provenance : {};
    const rawBoundary = asString(prov.data_boundary, "zero_external_egress");
    const dataBoundary: RoutingExplainResult["dataBoundary"] =
      rawBoundary === "external_vendor_api"
        ? "external_vendor_api"
        : rawBoundary === "vpc_network_boundary" || rawBoundary === "sovereign_vpc"
          ? "sovereign_vpc"
          : "local_loopback";

    const selectedProvider =
      typeof raw.selected_provider === "string" ? raw.selected_provider : null;
    const privacyCompliant = Boolean(raw.privacy_compliant) && selectedProvider !== null;
    const rationale = asString(raw.reason, "Evaluated by 4D hybrid router.");
    const fallbackChain = Array.isArray(raw.fallback_chain)
      ? raw.fallback_chain.filter((p): p is string => typeof p === "string")
      : [];
    const rawPrivacy = asString(raw.privacy_level, req.privacy);
    const privacyClassification: RoutingExplainResult["privacyClassification"] =
      rawPrivacy === "private" ||
      rawPrivacy === "standard" ||
      rawPrivacy === "internal" ||
      rawPrivacy === "public"
        ? rawPrivacy
        : req.privacy;

    const evaluatedCandidates =
      fallbackChain.length > 0
        ? fallbackChain.map((candidate) => ({
            model: asString(raw.requested_model) || candidate,
            boundary: dataBoundary,
            passed: privacyCompliant,
            reason: rationale,
          }))
        : [
            {
              model:
                asString(raw.requested_model) || req.candidateEndpoint || "candidate-endpoint",
              boundary: dataBoundary,
              passed: privacyCompliant,
              reason: rationale,
            },
          ];

    return {
      allowed: privacyCompliant,
      decision: !privacyCompliant
        ? "blocked_fail_closed"
        : dataBoundary === "external_vendor_api"
          ? "routed_cloud"
          : "routed_local",
      selectedModel: privacyCompliant
        ? asString(raw.requested_model) || req.model || "coder-7b@2.5.1"
        : "none",
      provider: selectedProvider ?? asString(prov.operator, "blocked"),
      license: typeof prov.license === "string" ? prov.license : undefined,
      hosting: typeof prov.hosting === "string" ? prov.hosting : undefined,
      dataBoundary,
      privacyClassification,
      estimatedCostUsd: asNumber(raw.estimated_cost_usd, 0),
      estimatedLatencyMs: dataBoundary === "local_loopback" ? 185 : 620,
      rationale,
      blockedReason: privacyCompliant ? undefined : rationale,
      evaluatedCandidates,
    };
  }
  return null;
}

export function decodeGovernancePersistence(raw: unknown): GovernancePersistenceInfo | null {
  if (!isRecord(raw)) return null;
  if (typeof raw.engine === "string" && typeof raw.journalMode === "string") {
    return raw as unknown as GovernancePersistenceInfo;
  }
  const isSqliteWal = raw.backend === "sqlite_wal";
  return {
    engine: isSqliteWal ? "SQLite 3" : "In-Memory",
    journalMode: isSqliteWal ? "WAL" : "MEMORY",
    synchronous: "NORMAL",
    dbPath: isSqliteWal ? ".keelway/governance.db" : ":memory:",
    walBytes: asNumber(raw.wal_bytes, 32768),
    foreignKeys: true,
    healthy: Boolean(raw.persistent ?? true) && Boolean(raw.chain_verified ?? true),
  };
}

export function decodeTenantPolicy(raw: unknown): TenantGovernancePolicy | null {
  if (!isRecord(raw)) return null;
  const rawZone = asString(raw.residencyZone || raw.residency_zone, "local_only");
  const validZones = new Set<DataResidencyZone>(["local_only", "africa_sovereign", "eu_sovereign", "global"]);
  const rawDlp = raw.dlpEnabled ?? raw.dlp_enabled ?? raw.log_redacted_prompts;
  const rawFallback = raw.fallbackToOpencoreOnBudgetExceeded ?? raw.fallback_to_opencore_on_budget_exceeded;
  return {
    tenantId: asString(raw.tenantId || raw.tenant_id, "default"),
    name: asString(raw.name, "Local Sovereign Workspace"),
    residencyZone: validZones.has(rawZone as DataResidencyZone) ? (rawZone as DataResidencyZone) : "local_only",
    dlpEnabled: typeof rawDlp === "boolean" ? rawDlp : true,
    dailyBudgetUsd: asNumber(raw.dailyBudgetUsd ?? raw.daily_spend_limit_usd, 10),
    dailySpendUsd: asNumber(raw.dailySpendUsd ?? raw.daily_spend_usd, 1.42),
    monthlyBudgetUsd: asNumber(raw.monthlyBudgetUsd ?? raw.monthly_spend_limit_usd, 150),
    currentSpendUsd: asNumber(raw.currentSpendUsd ?? raw.current_spend_usd, 0),
    warnThresholdPct: asNumber(raw.warnThresholdPct ?? raw.warn_threshold_pct, 80),
    hardCapEnforced: typeof raw.hardCapEnforced === "boolean" ? raw.hardCapEnforced : true,
    fallbackToOpencoreOnBudgetExceeded: typeof rawFallback === "boolean" ? rawFallback : true,
    fallbackModelId: asString(raw.fallbackModelId || raw.fallback_model_id, "keelway-core:7b"),
    requireHumanApprovalForNetwork: typeof raw.requireHumanApprovalForNetwork === "boolean" ? raw.requireHumanApprovalForNetwork : true,
    updatedAt: asString(raw.updatedAt || raw.updated_at, new Date().toISOString()),
  };
}

export function decodeScopedKey(raw: unknown, defaultCapUsd = 10): ScopedApiKeyItem | null {
  if (!isRecord(raw)) return null;
  const id = asString(raw.id || raw.key_id);
  if (!id) return null;
  return {
    id,
    label: asString(raw.label || raw.name, "scoped-key"),
    prefix: asString(raw.prefix || raw.key_prefix, "kw_live_…"),
    scopes: Array.isArray(raw.scopes)
      ? raw.scopes.filter((s): s is string => typeof s === "string")
      : [],
    spendCapUsd: asNumber(raw.spendCapUsd ?? raw.spend_cap_usd, defaultCapUsd),
    spentUsd: asNumber(raw.spentUsd ?? raw.spent_usd, 0),
    createdAt: asString(raw.createdAt || raw.created_at, new Date().toISOString()),
    revokedAt:
      typeof raw.revokedAt === "string"
        ? raw.revokedAt
        : raw.revoked === true
          ? new Date().toISOString()
          : null,
  };
}

export function decodeMintedScopedKey(
  raw: unknown,
  capUsd: number,
): MintedScopedApiKeyResult | null {
  if (!isRecord(raw)) return null;
  if (isRecord(raw.key) && typeof raw.plaintextSecret === "string") {
    const key = decodeScopedKey(raw.key, capUsd);
    return key
      ? {
          key,
          plaintextSecret: raw.plaintextSecret,
          oneTimeWarning: asString(
            raw.oneTimeWarning,
            "Copy this secret now. Keelway stores only its SHA-256 digest and cannot show it again.",
          ),
        }
      : null;
  }
  const plaintextSecret = asString(raw.api_key || raw.plaintextSecret);
  const key = decodeScopedKey(raw, capUsd);
  if (!key || !plaintextSecret) return null;
  return {
    key,
    plaintextSecret,
    oneTimeWarning:
      "Copy this secret now. Keelway stores only its SHA-256 digest and cannot show it again.",
  };
}
