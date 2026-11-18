import React, { useEffect, useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import {
  canRbacMutateSupplyChain, fetchConformanceBenchmarks, fetchMcpLockfiles,
  fetchMcpLockVerifications, pinMcpLockfile, PlatformSupplyChainHttpError,
  runConformanceBenchmark, verifyMcpLockfile,
  type BenchVerdict, type ConformanceBenchmarkRecord, type LockStatus,
  type LockVerifyVerdict, type McpLockfileRecord, type McpLockVerificationRecord,
  type SimulateMode, type SupplyChainRbacRole, type TargetKind,
} from "@/lib/platformSupplyChainApi";

export type ActiveTab = "lockfile_firewall" | "conformance_bench";

export interface McpLockfileAndBenchPanelProps {
  workspaceId?: string;
  activeRbacRole?: SupplyChainRbacRole;
}

const SIMULATE_MODES: ReadonlyArray<SimulateMode> = ["clean", "rug_pull", "poisoning"];
const TARGET_KINDS: ReadonlyArray<TargetKind> = ["mcp_server", "skill_package", "opencore_model"];
const CTRL_CLS = "min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg";

function formatDigestPrefix(digest: string): string {
  return (digest.startsWith("sha256:") ? digest : `sha256:${digest}`).slice(0, 23);
}

function resolveLockStatusBadge(status: LockStatus): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (status) {
    case "PINNED": return { kind: "passed", labelOverride: "PINNED" };
    case "POISONING_BLOCKED": return { kind: "failed", labelOverride: "POISONING_BLOCKED" };
    default: { const _exhaustive: never = status; return _exhaustive; }
  }
}

function resolveLockVerifyVerdictBadge(verdict: LockVerifyVerdict): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (verdict) {
    case "LOCK_VERIFIED": return { kind: "passed", labelOverride: "LOCK_VERIFIED" };
    case "DRIFT_RUG_PULL_BLOCKED": return { kind: "failed", labelOverride: "DRIFT_RUG_PULL_BLOCKED" };
    case "POISONING_BLOCKED": return { kind: "failed", labelOverride: "POISONING_BLOCKED" };
    default: { const _exhaustive: never = verdict; return _exhaustive; }
  }
}

function formatSimulateModeLabel(mode: SimulateMode): string {
  switch (mode) {
    case "clean": return "clean · Replay Pinned Tools Verbatim";
    case "rug_pull": return "rug_pull · Silent Tool Schema / Description Drift";
    case "poisoning": return "poisoning · Prompt-Injection + Zero-Width Unicode";
    default: { const _exhaustive: never = mode; return _exhaustive; }
  }
}

function resolveBenchVerdictBadge(verdict: BenchVerdict): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (verdict) {
    case "PASS_CERTIFIED": return { kind: "passed", labelOverride: "PASS_CERTIFIED" };
    case "FAIL_CONFORMANCE": return { kind: "failed", labelOverride: "FAIL_CONFORMANCE" };
    case "FAIL_BUDGET": return { kind: "needs-approval", labelOverride: "FAIL_BUDGET" };
    default: { const _exhaustive: never = verdict; return _exhaustive; }
  }
}

function formatTargetKindLabel(kind: TargetKind): string {
  switch (kind) {
    case "mcp_server": return "mcp_server · MCP Tool Server";
    case "skill_package": return "skill_package · Governed Agent Skill";
    case "opencore_model": return "opencore_model · Local OpenCore Model";
    default: { const _exhaustive: never = kind; return _exhaustive; }
  }
}

function resolveActiveTabPanel(tab: ActiveTab, lockfileNode: React.JSX.Element, benchNode: React.JSX.Element): React.JSX.Element {
  switch (tab) {
    case "lockfile_firewall": return lockfileNode;
    case "conformance_bench": return benchNode;
    default: { const _exhaustive: never = tab; return _exhaustive; }
  }
}

interface LockfileFirewallTabProps {
  uid: string; lockfileName: string; simulateMode: SimulateMode;
  isReadOnlyRole: boolean; busyAction: string | null;
  activeLockfile: McpLockfileRecord | null; latestVerification: McpLockVerificationRecord | null;
  onChangeLockfileName: (v: string) => void; onChangeSimulateMode: (v: SimulateMode) => void;
  onPinLockfile: () => void; onVerifyLockfile: () => void;
}

function LockfileFirewallTabContent(props: LockfileFirewallTabProps): React.JSX.Element {
  const { uid, lockfileName, simulateMode, isReadOnlyRole, busyAction, activeLockfile, latestVerification } = props;
  const statusBadge = activeLockfile ? resolveLockStatusBadge(activeLockfile.status) : null;
  const verifyBadge = latestVerification ? resolveLockVerifyVerdictBadge(latestVerification.verdict) : null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-xs font-semibold text-fg">Cryptographic Merkle Lockfile (`keelway.lock/v1`)</h3>
          {statusBadge ? <SemanticBadge data-testid="lockfile-status-badge" kind={statusBadge.kind} labelOverride={statusBadge.labelOverride} /> : <SemanticBadge kind="ready" labelOverride="UNPINNED" />}
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-lockfile-name`} className="font-medium text-fg">Lockfile Name</label>
            <input id={`${uid}-lockfile-name`} type="text" aria-label="Lockfile Name" value={lockfileName} onChange={(e) => props.onChangeLockfileName(e.target.value)} className={CTRL_CLS} />
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-sim-mode`} className="font-medium text-fg">Verification Mode</label>
            <select id={`${uid}-sim-mode`} aria-label="Verification Mode" value={simulateMode} onChange={(e) => props.onChangeSimulateMode(e.target.value as SimulateMode)} className={CTRL_CLS}>
              {SIMULATE_MODES.map((m) => <option key={m} value={m}>{formatSimulateModeLabel(m)}</option>)}
            </select>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button type="button" size="sm" variant="primary" aria-label="Pin MCP lockfile" loading={busyAction === "pin_lock"} disabled={isReadOnlyRole || busyAction !== null} onClick={props.onPinLockfile}>
            Pin MCP lockfile
          </Button>
          <Button type="button" size="sm" variant="secondary" aria-label="Verify lockfile integrity" loading={busyAction === "verify_lock"} disabled={isReadOnlyRole || busyAction !== null} onClick={props.onVerifyLockfile}>
            Verify lockfile integrity
          </Button>
        </div>

        {activeLockfile ? (
          <div className="space-y-1.5 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-fg" data-testid="lockfile-id">{`lockfile_id: ${activeLockfile.lockfile_id ?? "blocked"}`}</span>
              <span className="text-teal-accent" data-testid="lockfile-tool-count">{`tool_count: ${activeLockfile.tool_count}`}</span>
            </div>
            <div className="flex items-center justify-between gap-2 text-[10px]">
              <span className="text-fg-muted">merkle_root_sha256:</span>
              <code data-testid="lockfile-merkle-root" title={activeLockfile.merkle_root_sha256} className="max-w-[230px] truncate text-teal-accent">{formatDigestPrefix(activeLockfile.merkle_root_sha256)}</code>
            </div>
            {activeLockfile.findings.length > 0 ? (
              <ul aria-label="Day-1 lockfile poisoning findings" className="list-inside list-disc text-[10px] text-danger">
                {activeLockfile.findings.map((f, idx) => <li key={`${idx}-${f}`}>{f}</li>)}
              </ul>
            ) : null}
            <pre aria-label="Pinned MCP lockfile JSON" tabIndex={0} className="max-h-32 overflow-auto rounded-xs border border-border bg-code p-2 text-[10px] text-fg">
              <code>{activeLockfile.lockfile_json || "// Poisoned lockfile refused pre-storage"}</code>
            </pre>
          </div>
        ) : (
          <div className="rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px] text-fg-muted">
            Pin MCP server tools into a canonical SHA-256 Merkle lockfile with Day-1 prompt-injection &amp; zero-width Unicode refusal.
          </div>
        )}
      </div>

      <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-xs font-semibold text-fg">Post-Install Rug-Pull &amp; Poisoning Firewall Receipt</h3>
          {verifyBadge ? <SemanticBadge data-testid="verify-verdict-badge" kind={verifyBadge.kind} labelOverride={verifyBadge.labelOverride} /> : <SemanticBadge kind="ready" labelOverride="FIREWALL_READY" />}
        </div>
        {latestVerification ? (
          <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
            <div className="flex flex-wrap items-center justify-between gap-2 text-[10px]">
              <span className="text-fg" data-testid="verify-lockfile-ref">{`lockfile: ${latestVerification.lockfile_id}`}</span>
              <span className="text-fg-muted">{`dlp_redactions: ${latestVerification.dlp_redactions}`}</span>
            </div>
            <div className="space-y-1 text-[10px]">
              <div className="text-fg" data-testid="verify-drifted-tools">
                {`drifted_tools: ${latestVerification.drifted_tools.length > 0 ? latestVerification.drifted_tools.join(", ") : "none"}`}
              </div>
              <div className={latestVerification.poisoning_findings.length > 0 ? "text-danger" : "text-fg-muted"} data-testid="verify-poisoning-findings">
                {`poisoning_findings: ${latestVerification.poisoning_findings.length > 0 ? latestVerification.poisoning_findings.join(" | ") : "none"}`}
              </div>
            </div>
            <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[10px]">
              <span className="text-fg-muted">verification_sha256:</span>
              <code data-testid="verify-receipt-sha256" title={latestVerification.verification_sha256} className="max-w-[230px] truncate text-teal-accent">{formatDigestPrefix(latestVerification.verification_sha256)}</code>
            </div>
          </div>
        ) : (
          <div className="rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px] text-fg-muted">
            Verify live MCP tool descriptors against the pinned Merkle root to block silent schema rug-pulls and invisible Unicode prompt poisoning in &lt;5ms.
          </div>
        )}
      </div>
    </div>
  );
}

interface ConformanceBenchTabProps {
  uid: string; targetId: string; targetKind: TargetKind; modelId: string;
  latencyBudgetMs: string; minConformanceScore: string;
  isReadOnlyRole: boolean; busyAction: string | null;
  latestBench: ConformanceBenchmarkRecord | null; benchRuns: ConformanceBenchmarkRecord[];
  onChangeTargetId: (v: string) => void; onChangeTargetKind: (v: TargetKind) => void;
  onChangeModelId: (v: string) => void; onChangeLatencyBudgetMs: (v: string) => void;
  onChangeMinConformanceScore: (v: string) => void; onRunBenchmark: () => void;
}

function ConformanceBenchTabContent(props: ConformanceBenchTabProps): React.JSX.Element {
  const { uid, targetId, targetKind, modelId, latencyBudgetMs, minConformanceScore, isReadOnlyRole, busyAction, latestBench, benchRuns } = props;
  const benchBadge = latestBench ? resolveBenchVerdictBadge(latestBench.verdict) : null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
        <h3 className="text-xs font-semibold text-fg">Deterministic Conformance Benchmark Harness (`keelway bench`)</h3>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-target-id`} className="font-medium text-fg">Target ID</label>
            <input id={`${uid}-target-id`} type="text" aria-label="Target ID" value={targetId} onChange={(e) => props.onChangeTargetId(e.target.value)} className={CTRL_CLS} />
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-target-kind`} className="font-medium text-fg">Target Kind</label>
            <select id={`${uid}-target-kind`} aria-label="Target Kind" value={targetKind} onChange={(e) => props.onChangeTargetKind(e.target.value as TargetKind)} className={CTRL_CLS}>
              {TARGET_KINDS.map((k) => <option key={k} value={k}>{formatTargetKindLabel(k)}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-model-id`} className="font-medium text-fg">Model ID</label>
            <input id={`${uid}-model-id`} type="text" aria-label="Model ID" value={modelId} onChange={(e) => props.onChangeModelId(e.target.value)} className={CTRL_CLS} />
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-latency-budget`} className="font-medium text-fg">Latency Budget ms</label>
            <input id={`${uid}-latency-budget`} type="number" min="10" step="10" aria-label="Latency Budget ms" value={latencyBudgetMs} onChange={(e) => props.onChangeLatencyBudgetMs(e.target.value)} className={CTRL_CLS} />
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted sm:col-span-2">
            <label htmlFor={`${uid}-min-conformance`} className="font-medium text-fg">Min Conformance Score</label>
            <input id={`${uid}-min-conformance`} type="number" min="0" max="1" step="0.05" aria-label="Min Conformance Score" value={minConformanceScore} onChange={(e) => props.onChangeMinConformanceScore(e.target.value)} className={CTRL_CLS} />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <span className="font-mono text-[10px] text-fg-muted">Schema + determinism + P95 latency SLO certificate</span>
          <Button type="button" size="sm" variant="primary" aria-label="Run conformance benchmark" loading={busyAction === "run_bench"} disabled={isReadOnlyRole || busyAction !== null} onClick={props.onRunBenchmark}>
            Run conformance benchmark
          </Button>
        </div>
      </div>

      <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-xs font-semibold text-fg">Conformance Certificate &amp; Recent Runs</h3>
          {benchBadge ? <SemanticBadge data-testid="bench-verdict-badge" kind={benchBadge.kind} labelOverride={benchBadge.labelOverride} /> : <SemanticBadge kind="ready" labelOverride="BENCH_READY" />}
        </div>
        {latestBench ? (
          <div className="space-y-1.5 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-fg" data-testid="bench-conformance-score">{`conformance_score: ${latestBench.conformance_score.toFixed(2)} (min ${latestBench.min_conformance_score.toFixed(2)})`}</span>
              <span className="text-teal-accent" data-testid="bench-cost-saved-usd">{`frontier_cost_saved_usd: $${latestBench.frontier_cost_saved_usd.toFixed(3)}`}</span>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 text-[10px]">
              <span className="text-fg" data-testid="bench-p95-latency">{`p95_latency_ms: ${latestBench.p95_latency_ms} ms (budget ${latestBench.latency_budget_ms} ms)`}</span>
              <span className="text-fg-muted">{`${latestBench.target_kind} · ${latestBench.model_id}`}</span>
            </div>
            <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[10px]">
              <span className="text-fg-muted">cert_sha256:</span>
              <code data-testid="bench-cert-sha256" title={latestBench.cert_sha256} className="max-w-[230px] truncate text-teal-accent">{formatDigestPrefix(latestBench.cert_sha256)}</code>
            </div>
          </div>
        ) : (
          <div className="rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px] text-fg-muted">
            Run deterministic schema-validity, replay-parity, and P95 latency checks to mint a SHA-256 conformance certificate.
          </div>
        )}
        <ul aria-label="Recent conformance benchmark runs" className="space-y-1.5 rounded-xs border border-border bg-canvas p-2 font-mono text-[10px]">
          {benchRuns.length > 0 ? benchRuns.slice(0, 4).map((run) => (
            <li key={run.benchmark_id} className="flex flex-wrap items-center justify-between gap-1.5 border-b border-border pb-1 last:border-b-0 last:pb-0">
              <span className="font-semibold text-fg">{`${run.target_id} (${run.target_kind})`}</span>
              <span className="text-teal-accent">{`${run.verdict} · ${(run.conformance_score * 100).toFixed(0)}% · ${run.p95_latency_ms}ms`}</span>
            </li>
          )) : <li className="text-fg-muted">No conformance benchmark runs recorded in this workspace yet.</li>}
        </ul>
      </div>
    </div>
  );
}

export function McpLockfileAndBenchPanel({
  workspaceId = "default", activeRbacRole = "owner",
}: McpLockfileAndBenchPanelProps): React.JSX.Element {
  const uid = useId();
  const isReadOnlyRole = activeRbacRole === "auditor" || activeRbacRole === "viewer" || !canRbacMutateSupplyChain(activeRbacRole);
  const [activeTab, setActiveTab] = useState<ActiveTab>("lockfile_firewall");
  const [lockfileName, setLockfileName] = useState("keelway.lock.json");
  const [simulateMode, setSimulateMode] = useState<SimulateMode>("clean");
  const [targetId, setTargetId] = useState("mcp-git-local");
  const [targetKind, setTargetKind] = useState<TargetKind>("mcp_server");
  const [modelId, setModelId] = useState("keelway-core:7b");
  const [latencyBudgetMs, setLatencyBudgetMs] = useState("250");
  const [minConformanceScore, setMinConformanceScore] = useState("0.90");
  const [lockfiles, setLockfiles] = useState<McpLockfileRecord[]>([]);
  const [activeLockfile, setActiveLockfile] = useState<McpLockfileRecord | null>(null);
  const [verifications, setVerifications] = useState<McpLockVerificationRecord[]>([]);
  const [latestVerification, setLatestVerification] = useState<McpLockVerificationRecord | null>(null);
  const [benchRuns, setBenchRuns] = useState<ConformanceBenchmarkRecord[]>([]);
  const [latestBench, setLatestBench] = useState<ConformanceBenchmarkRecord | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [errorAlert, setErrorAlert] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchMcpLockfiles(workspaceId, 25, activeRbacRole).then((r) => {
      if (!cancelled) { setLockfiles(r.lockfiles); setActiveLockfile(r.lockfiles[0] ?? null); }
    }).catch(() => {});
    void fetchMcpLockVerifications(workspaceId, 25, activeRbacRole).then((r) => {
      if (!cancelled) { setVerifications(r.verifications); setLatestVerification(r.verifications[0] ?? null); }
    }).catch(() => {});
    void fetchConformanceBenchmarks(workspaceId, 25, activeRbacRole).then((r) => {
      if (!cancelled) { setBenchRuns(r.runs); setLatestBench(r.runs[0] ?? null); }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [activeRbacRole, workspaceId]);

  const formatErr = (err: unknown, fallback: string): string =>
    err instanceof PlatformSupplyChainHttpError ? `HTTP ${err.status} · ${err.message}` : err instanceof Error ? err.message : fallback;

  const handlePinLockfile = async () => {
    if (isReadOnlyRole) return;
    setBusyAction("pin_lock"); setErrorAlert(null);
    try {
      const rec = await pinMcpLockfile({ workspace_id: workspaceId, lockfile_name: lockfileName.trim() || "keelway.lock.json" }, activeRbacRole);
      setActiveLockfile(rec);
      const snap = await fetchMcpLockfiles(workspaceId, 25, activeRbacRole);
      setLockfiles(snap.lockfiles);
    } catch (err) { setErrorAlert(formatErr(err, "Failed to pin MCP lockfile.")); }
    finally { setBusyAction(null); }
  };

  const handleVerifyLockfile = async () => {
    if (isReadOnlyRole) return;
    setBusyAction("verify_lock"); setErrorAlert(null);
    try {
      const rec = await verifyMcpLockfile({ workspace_id: workspaceId, lockfile_id: activeLockfile?.lockfile_id ?? null, simulate_mode: simulateMode }, activeRbacRole);
      setLatestVerification(rec);
      const snap = await fetchMcpLockVerifications(workspaceId, 25, activeRbacRole);
      setVerifications(snap.verifications);
    } catch (err) { setErrorAlert(formatErr(err, "Failed to verify MCP lockfile integrity.")); }
    finally { setBusyAction(null); }
  };

  const handleRunBenchmark = async () => {
    if (isReadOnlyRole) return;
    setBusyAction("run_bench"); setErrorAlert(null);
    try {
      const parsedBudget = Number.parseFloat(latencyBudgetMs);
      const parsedMin = Number.parseFloat(minConformanceScore);
      const rec = await runConformanceBenchmark({
        workspace_id: workspaceId, target_id: targetId.trim() || "mcp-git-local", target_kind: targetKind,
        model_id: modelId.trim() || "keelway-core:7b",
        latency_budget_ms: Number.isFinite(parsedBudget) && parsedBudget > 0 ? parsedBudget : 250,
        min_conformance_score: Number.isFinite(parsedMin) ? parsedMin : 0.90,
      }, activeRbacRole);
      setLatestBench(rec);
      const snap = await fetchConformanceBenchmarks(workspaceId, 25, activeRbacRole);
      setBenchRuns(snap.runs);
    } catch (err) { setErrorAlert(formatErr(err, "Failed to run conformance benchmark.")); }
    finally { setBusyAction(null); }
  };

  const latestMerkle = lockfiles[0]?.merkle_root_sha256 ?? (activeLockfile?.status === "PINNED" ? activeLockfile.merkle_root_sha256 : "");
  const certifiedCount = benchRuns.filter((r) => r.verdict === "PASS_CERTIFIED").length;
  const lockTabId = `${uid}-tab-lockfile`;
  const benchTabId = `${uid}-tab-bench`;
  const tabPanelId = `${uid}-tabpanel`;

  return (
    <section id="mcp-lockfile-and-bench-panel" aria-label="Cryptographic MCP Lockfile, Rug-Pull Firewall & Conformance Benchmark" className="space-y-4 rounded-md border border-border-strong bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-border pb-3">
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-fg">Cryptographic MCP Lockfile, Rug-Pull Firewall &amp; Conformance Benchmark</h2>
            <SemanticBadge kind="opencore" labelOverride="SQLite WAL · keelway.lock/v1 + Bench" />
            {isReadOnlyRole ? <span className="rounded-xs border border-border-strong bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">{`RBAC: ${activeRbacRole} (read-only)`}</span> : null}
          </div>
          <p className="text-xs text-fg-muted">Pin MCP tool schemas into SHA-256 Merkle lockfiles, block silent post-install rug-pulls &amp; zero-width Unicode poisoning, and certify deterministic OpenCore conformance.</p>
        </div>
      </div>

      {isReadOnlyRole ? <div role="status" className="rounded-xs border border-warning/45 bg-warning-subtle px-3 py-1.5 font-mono text-xs text-fg">{`Read-Only RBAC (${activeRbacRole}): MCP lockfile pinning, integrity verification, and conformance benchmark mutations are disabled.`}</div> : null}
      {errorAlert ? <div role="alert" className="rounded-xs border border-danger/55 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg"><span className="font-semibold text-danger">{errorAlert}</span></div> : null}

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" aria-label="Supply chain lockfile and benchmark KPI summary">
        <div className="rounded-xs border border-border bg-chrome px-3 py-2 font-mono"><div className="text-[10px] text-fg-muted">Pinned Lockfiles</div><div className="text-xs font-semibold text-fg" data-testid="kpi-pinned-lockfiles">{lockfiles.length}</div></div>
        <div className="rounded-xs border border-border bg-chrome px-3 py-2 font-mono"><div className="text-[10px] text-fg-muted">Latest Merkle Root</div><div className="truncate text-xs font-semibold text-teal-accent" data-testid="kpi-latest-merkle-root">{latestMerkle ? formatDigestPrefix(latestMerkle) : "unpinned"}</div></div>
        <div className="rounded-xs border border-border bg-chrome px-3 py-2 font-mono"><div className="text-[10px] text-fg-muted">Firewall Verifications</div><div className="text-xs font-semibold text-fg" data-testid="kpi-firewall-verifications">{verifications.length}</div></div>
        <div className="rounded-xs border border-border bg-chrome px-3 py-2 font-mono"><div className="text-[10px] text-fg-muted">Certified Benchmarks</div><div className="text-xs font-semibold text-teal-accent" data-testid="kpi-certified-benchmarks">{certifiedCount}</div></div>
      </div>

      <div role="tablist" aria-label="MCP lockfile firewall and conformance benchmark tabs" className="flex flex-wrap gap-2 border-b border-border pb-2">
        <button type="button" role="tab" id={lockTabId} aria-selected={activeTab === "lockfile_firewall"} aria-controls={tabPanelId} onClick={() => setActiveTab("lockfile_firewall")} className={`rounded-sm border px-3 py-1.5 font-mono text-xs font-medium ${activeTab === "lockfile_firewall" ? "border-teal-accent bg-teal-surface text-teal-accent" : "border-border bg-chrome text-fg-muted"}`}>
          MCP Lockfile &amp; Rug-Pull Firewall
        </button>
        <button type="button" role="tab" id={benchTabId} aria-selected={activeTab === "conformance_bench"} aria-controls={tabPanelId} onClick={() => setActiveTab("conformance_bench")} className={`rounded-sm border px-3 py-1.5 font-mono text-xs font-medium ${activeTab === "conformance_bench" ? "border-teal-accent bg-teal-surface text-teal-accent" : "border-border bg-chrome text-fg-muted"}`}>
          Agent &amp; Skill Conformance Benchmark
        </button>
      </div>

      <div role="tabpanel" id={tabPanelId} aria-labelledby={activeTab === "lockfile_firewall" ? lockTabId : benchTabId}>
        {resolveActiveTabPanel(
          activeTab,
          <LockfileFirewallTabContent uid={uid} lockfileName={lockfileName} simulateMode={simulateMode} isReadOnlyRole={isReadOnlyRole} busyAction={busyAction} activeLockfile={activeLockfile} latestVerification={latestVerification} onChangeLockfileName={setLockfileName} onChangeSimulateMode={setSimulateMode} onPinLockfile={() => { void handlePinLockfile(); }} onVerifyLockfile={() => { void handleVerifyLockfile(); }} />,
          <ConformanceBenchTabContent uid={uid} targetId={targetId} targetKind={targetKind} modelId={modelId} latencyBudgetMs={latencyBudgetMs} minConformanceScore={minConformanceScore} isReadOnlyRole={isReadOnlyRole} busyAction={busyAction} latestBench={latestBench} benchRuns={benchRuns} onChangeTargetId={setTargetId} onChangeTargetKind={setTargetKind} onChangeModelId={setModelId} onChangeLatencyBudgetMs={setLatencyBudgetMs} onChangeMinConformanceScore={setMinConformanceScore} onRunBenchmark={() => { void handleRunBenchmark(); }} />,
        )}
      </div>
    </section>
  );
}
