import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type { AutomationWorkflowItem } from "@/lib/platformData";
import {
  canRbacApproveP10Dag, canRbacRunKflowOrCrdt, fetchKflowRuns, fetchKspacesState,
  postExecuteKflowDag, postSyncKspacesCrdt,
  type CrdtOpKind, type KflowDagRunResult, type KflowNodeInput, type KspacesCrdtState,
} from "@/lib/platformKflowApi";
import type { RbacRoleId } from "@/lib/platformRuntimeApi";

export interface KSpacesCrdtAndKflowPanelProps {
  workspaceId?: string;
  activeRbacRole?: RbacRoleId;
  activeWorkflow?: AutomationWorkflowItem;
}

const DEFAULT_DAG_NODES: KflowNodeInput[] = [
  { id: "n-1", label: "Scan dependencies & SBOM", agent_id: "security-auditor", depends_on: [], requires_p10: false },
  { id: "n-2", label: "Verify SHA-256 Record chain", agent_id: "qa-ci-runner", depends_on: ["n-1"], requires_p10: true },
];

export function KSpacesCrdtAndKflowPanel({
  workspaceId = "default", activeRbacRole = "owner", activeWorkflow,
}: KSpacesCrdtAndKflowPanelProps): React.JSX.Element {
  const canMutate = canRbacRunKflowOrCrdt(activeRbacRole);
  const canApproveP10 = canRbacApproveP10Dag(activeRbacRole);

  const baseNodes = useMemo<KflowNodeInput[]>(() => {
    if (!activeWorkflow || activeWorkflow.nodes.length === 0) return DEFAULT_DAG_NODES;
    return activeWorkflow.nodes.map((n) => ({
      id: n.id, label: n.label, agent_id: n.agentId, depends_on: n.dependsOn, requires_p10: Boolean(n.requiresP10),
    }));
  }, [activeWorkflow]);

  const [requireFinalP10, setRequireFinalP10] = useState<boolean>(Boolean(baseNodes[baseNodes.length - 1]?.requires_p10 ?? true));
  const [approvedNodeIds, setApprovedNodeIds] = useState<string[]>([]);
  const [dagRun, setDagRun] = useState<KflowDagRunResult | null>(null);
  const [dagBusy, setDagBusy] = useState(false);

  const [peerId, setPeerId] = useState("peer-local-ide");
  const [entryKey, setEntryKey] = useState("sprint.active_focus");
  const [entryValue, setEntryValue] = useState("KEEL-GA-015");
  const [opKind, setOpKind] = useState<CrdtOpKind>("set");
  const [crdtState, setCrdtState] = useState<KspacesCrdtState | null>(null);
  const [crdtBusy, setCrdtBusy] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const workflowId = activeWorkflow?.id ?? "WF-01";
  const tokenBudget = activeWorkflow?.tokenBudget ?? 25_000;
  const triggerLabel = activeWorkflow ? `${activeWorkflow.triggerKind}:${activeWorkflow.triggerSpec}` : "cron:0 2 * * *";

  useEffect(() => {
    setRequireFinalP10(Boolean(baseNodes[baseNodes.length - 1]?.requires_p10 ?? true));
  }, [workflowId, baseNodes]);

  useEffect(() => {
    let cancelled = false;
    void fetchKspacesState(workspaceId, activeRbacRole).then((s) => { if (!cancelled) setCrdtState(s); }).catch((err) => { if (!cancelled) setErrorBanner(err instanceof Error ? err.message : "Failed to load KSpaces CRDT state."); });
    void fetchKflowRuns(workspaceId, workflowId, activeRbacRole).then((r) => { if (!cancelled && r[0]) setDagRun(r[0]); }).catch((err) => { if (!cancelled) setErrorBanner(err instanceof Error ? err.message : "Failed to load KFlow DAG runs."); });
    return () => { cancelled = true; };
  }, [activeRbacRole, workflowId, workspaceId]);

  const effectiveNodes = useMemo<KflowNodeInput[]>(
    () => baseNodes.map((node, idx) => (idx === baseNodes.length - 1 ? { ...node, requires_p10: requireFinalP10 } : node)),
    [baseNodes, requireFinalP10],
  );

  const runDagWithApprovals = async (nextApproved: string[]) => {
    setDagBusy(true);
    setErrorBanner(null);
    try {
      const res = await postExecuteKflowDag({
        workspaceId, workflowId, nodes: effectiveNodes, trigger: triggerLabel, tokenBudget,
        approvedNodeIds: nextApproved, role: activeRbacRole,
      });
      setApprovedNodeIds(nextApproved);
      setDagRun(res);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to execute topological KFlow DAG.");
    } finally {
      setDagBusy(false);
    }
  };

  const handleSyncCrdt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canMutate || !entryKey.trim()) return;
    setCrdtBusy(true);
    setErrorBanner(null);
    try {
      const res = await postSyncKspacesCrdt({
        workspaceId, peerId: peerId.trim() || "peer-local-ide", role: activeRbacRole,
        operations: [{ op: opKind, namespace: "workspace", key: entryKey.trim(), value: opKind === "remove" ? null : entryValue }],
      });
      setCrdtState(res);
    } catch (err) {
      setErrorBanner(err instanceof Error ? err.message : "Failed to synchronize KSpaces CRDT operation.");
    } finally {
      setCrdtBusy(false);
    }
  };

  const vectorEntries = Object.entries(crdtState?.vector_clock ?? {});

  return (
    <section aria-label="Topological KFlow DAG runner and KSpaces CRDT sync" className="space-y-3 rounded-md border border-border-strong bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
        <div>
          <h2 className="text-sm font-semibold text-fg">Live KFlow Topological DAG Runner &amp; KSpaces CRDT Sync</h2>
          <p className="text-xs text-fg-muted">
            Execute dependency-ordered wave graphs with P-10 human-only gates alongside multi-peer LWW-Element-Set CRDT state replication.
          </p>
        </div>
        <SemanticBadge kind="opencore" detail={`Workspace · ${workspaceId}`} />
      </div>

      {errorBanner ? (
        <div role="alert" className="rounded-xs border border-danger/50 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">{errorBanner}</div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3 rounded-sm border border-border bg-chrome p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-xs font-semibold text-fg">{`Topological KFlow Execution (${workflowId})`}</h3>
              <p className="font-mono text-[11px] text-fg-muted">{`${effectiveNodes.length} DAG nodes · Budget ${tokenBudget} tok`}</p>
            </div>
            {dagRun ? (
              <SemanticBadge
                kind={dagRun.status === "completed" ? "passed" : dagRun.status === "awaiting_p10" ? "needs-approval" : "failed"}
                labelOverride={dagRun.status}
              />
            ) : null}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xs border border-border bg-canvas px-2.5 py-2 text-xs text-fg">
            <label className="inline-flex items-center gap-1.5">
              <input type="checkbox" aria-label="Require P-10 gate on final DAG step" checked={requireFinalP10} onChange={(e) => setRequireFinalP10(e.target.checked)} />
              <span>Require P-10 gate on final DAG step</span>
            </label>
            <Button size="sm" variant="primary" loading={dagBusy} disabled={!canMutate} onClick={() => { void runDagWithApprovals([]); }}>
              Execute Topological DAG
            </Button>
          </div>

          {dagRun ? (
            <div className="space-y-2.5 rounded-xs border border-border bg-canvas p-2.5 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[11px]">
                <span className="text-fg">{dagRun.waves.map((_, idx) => `Wave ${idx}`).join(" -> ")}</span>
                <span className="text-fg-muted">{`${dagRun.tokens_used} / ${dagRun.token_budget}`}</span>
              </div>
              <div className="flex items-center justify-between gap-2 font-mono text-[11px]">
                <span className="text-fg-muted">Receipt:</span>
                <code className="max-w-[240px] truncate font-mono text-xs text-accent">{dagRun.receipt_sha256}</code>
              </div>

              {dagRun.status === "awaiting_p10" && dagRun.held_node_id ? (
                <div role="status" className="space-y-2 rounded-xs border border-ochre/45 bg-ochre-subtle p-2.5 text-xs text-fg">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono font-semibold text-ochre">{`Held at P-10 node: ${dagRun.held_node_id}`}</span>
                    <Button
                      size="sm" variant="warning-cta" clickOnly loading={dagBusy} disabled={!canApproveP10}
                      onClick={() => { void runDagWithApprovals(Array.from(new Set([...approvedNodeIds, dagRun.held_node_id!]))); }}
                    >
                      Approve Held DAG Node
                    </Button>
                  </div>
                  {!canApproveP10 ? (
                    <p className="font-mono text-[11px] text-fg-muted">
                      {`RBAC Lock (${activeRbacRole}): Only owner or operator can approve P-10 DAG checkpoints (builder, admin, and viewer are denied).`}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <div role="region" aria-label="KSpaces CRDT state synchronization" className="space-y-3 rounded-sm border border-border bg-chrome p-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-xs font-semibold text-fg">KSpaces Multi-Peer CRDT State Sync</h3>
            <span className="font-mono text-[11px] text-accent">{`Active CRDT Keys: ${crdtState?.active_keys_count ?? 0}`}</span>
          </div>

          <form onSubmit={(e) => { void handleSyncCrdt(e); }} className="grid gap-2 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
              <span>Peer ID</span>
              <input type="text" aria-label="CRDT peer ID" value={peerId} onChange={(e) => setPeerId(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
              <span>Operation</span>
              <select aria-label="CRDT operation kind" value={opKind} onChange={(e) => setOpKind(e.target.value as CrdtOpKind)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg">
                <option value="set">set</option>
                <option value="remove">remove</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
              <span>Entry key</span>
              <input type="text" aria-label="CRDT entry key" value={entryKey} onChange={(e) => setEntryKey(e.target.value)} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-fg-muted">
              <span>Entry value</span>
              <input type="text" aria-label="CRDT entry value" value={entryValue} onChange={(e) => setEntryValue(e.target.value)} disabled={opKind === "remove"} className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
            </label>
            <div className="sm:col-span-2 flex justify-end">
              <Button type="submit" size="sm" variant="secondary" loading={crdtBusy} disabled={!canMutate}>Sync CRDT Operation</Button>
            </div>
          </form>

          <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 text-xs">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-mono text-[11px] text-fg-muted">Vector Clock:</span>
              {vectorEntries.length === 0 ? (
                <span className="font-mono text-[11px] text-fg-dim">0 peers synced</span>
              ) : (
                vectorEntries.map(([peer, lamport]) => (
                  <span key={peer} className="rounded-xs border border-accent/40 bg-accent-subtle px-1.5 py-0.5 font-mono text-[10px] text-accent">{`${peer}: ${lamport}`}</span>
                ))
              )}
            </div>
            <div className="flex items-center justify-between gap-2 font-mono text-[11px]">
              <span className="text-fg-muted">State Digest:</span>
              <code className="max-w-[240px] truncate font-mono text-xs text-accent">{crdtState?.state_digest_sha256 ?? "sha256:pending"}</code>
            </div>
            {crdtState && crdtState.entries.length > 0 ? (
              <ul aria-label="Synced CRDT entries" className="space-y-1 border-t border-border pt-1.5 font-mono text-[11px]">
                {crdtState.entries.map((entry) => (
                  <li key={`${entry.namespace}:${entry.key}`} className="flex items-center justify-between gap-2 text-fg">
                    <span className="truncate">{`${entry.key} = ${entry.tombstone ? "[TOMBSTONE]" : String(entry.value ?? "")}`}</span>
                    <span className="shrink-0 text-[10px] text-fg-muted">{`${entry.peer_id}@L${entry.lamport_ts}`}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
