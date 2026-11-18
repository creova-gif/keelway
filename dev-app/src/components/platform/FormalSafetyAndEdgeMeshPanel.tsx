import React, { useEffect, useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import {
  canRbacMutateSafetyMesh, dispatchMeshHandoff, listMeshHandoffs, listMeshNodes,
  listSafetyVerifications, PlatformSafetyMeshHttpError, verifyWorkflowSafety,
  type DataClassification, type MeshHandoffRecord, type MeshHandoffStatus,
  type MeshHardwareHal, type MeshNodeRecord, type MeshTier,
  type SafetyMeshRbacRole, type SafetyVerificationRecord, type SafetyVerificationStatus,
} from "@/lib/platformSafetyMeshApi";

export interface FormalSafetyAndEdgeMeshPanelProps {
  workspaceId?: string;
  activeRbacRole?: SafetyMeshRbacRole;
}

interface WorkflowPresetOption { workflowName: string; workflowId: string; label: string; }

const WORKFLOW_PRESETS: ReadonlyArray<WorkflowPresetOption> = [
  { workflowName: "treasury-wire-approver", workflowId: "WF-TREASURY-01", label: "treasury-wire-approver (WF-TREASURY-01)" },
  { workflowName: "clinical-phi-exporter", workflowId: "WF-CLINICAL-02", label: "clinical-phi-exporter (WF-CLINICAL-02)" },
];

const DATA_CLASSIFICATIONS: ReadonlyArray<DataClassification> = ["restricted_pii", "internal", "public"];

function formatDigestPrefix(digest: string): string {
  const normalized = digest.startsWith("sha256:") ? digest : `sha256:${digest}`;
  return normalized.slice(0, 23);
}

function resolveSafetyStatusBadge(status: SafetyVerificationStatus | "IDLE"): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (status) {
    case "VERIFIED_SAFE": return { kind: "passed", labelOverride: "VERIFIED_SAFE" };
    case "VIOLATION_FOUND": return { kind: "failed", labelOverride: "VIOLATION_FOUND" };
    case "IDLE": return { kind: "ready", labelOverride: "AWAITING_PROOF" };
    default: { const _exhaustive: never = status; return _exhaustive; }
  }
}

function resolveMeshTierBadge(tier: MeshTier): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (tier) {
    case "edge_local": return { kind: "opencore", labelOverride: "edge_local" };
    case "cluster_burst": return { kind: "frontier", labelOverride: "cluster_burst" };
    default: { const _exhaustive: never = tier; return _exhaustive; }
  }
}

function resolveHalBadge(hal: MeshHardwareHal | string): { kind: SemanticBadgeKind; labelOverride: string } {
  if (hal === "apple_metal_secure_enclave") return { kind: "locked", labelOverride: "apple_metal_secure_enclave" };
  if (hal === "nvidia_h100_cc") return { kind: "ai", labelOverride: "nvidia_h100_cc" };
  if (hal === "linux_tpm2") return { kind: "ready", labelOverride: "linux_tpm2" };
  return { kind: "ready", labelOverride: hal };
}

function resolveHandoffStatusBadge(status: MeshHandoffStatus | "IDLE"): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (status) {
    case "ATTESTED_COMPLETE": return { kind: "passed", labelOverride: "ATTESTED_COMPLETE" };
    case "PINNED_EDGE_ONLY": return { kind: "locked", labelOverride: "PINNED_EDGE_ONLY" };
    case "IDLE": return { kind: "ready", labelOverride: "MESH_READY" };
    default: { const _exhaustive: never = status; return _exhaustive; }
  }
}

interface SafetyVerifierCardProps {
  workflowSelectId: string; airgapCheckboxId: string;
  selectedWorkflowName: string; airgapMode: boolean; canMutate: boolean; busyAction: string | null;
  verification: SafetyVerificationRecord | null;
  onChangeWorkflow: (name: string) => void; onChangeAirgap: (checked: boolean) => void;
  onVerify: (injectP10: boolean) => void;
}

function SafetyVerifierSubCard({
  workflowSelectId, airgapCheckboxId, selectedWorkflowName, airgapMode,
  canMutate, busyAction, verification, onChangeWorkflow, onChangeAirgap, onVerify,
}: SafetyVerifierCardProps): React.JSX.Element {
  const statusSpec = resolveSafetyStatusBadge(verification?.status ?? "IDLE");

  return (
    <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-fg">Formal Safety State-Machine Verifier</h3>
        <SemanticBadge kind={statusSpec.kind} labelOverride={statusSpec.labelOverride} />
      </div>

      <div className="space-y-2">
        <div className="flex flex-col gap-1 text-xs text-fg-muted">
          <label htmlFor={workflowSelectId} className="font-medium text-fg">Workflow State-Machine Preset</label>
          <select
            id={workflowSelectId}
            value={selectedWorkflowName}
            onChange={(e) => onChangeWorkflow(e.target.value)}
            className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
          >
            {WORKFLOW_PRESETS.map((preset) => (
              <option key={preset.workflowName} value={preset.workflowName}>{preset.label}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2 pt-0.5">
          <input
            id={airgapCheckboxId}
            type="checkbox"
            checked={airgapMode}
            onChange={(e) => onChangeAirgap(e.target.checked)}
            className="h-3.5 w-3.5 rounded-xs border border-border-control"
          />
          <label htmlFor={airgapCheckboxId} className="text-xs text-fg">Air-Gap Zero-Egress Mode</label>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="secondary" loading={busyAction === "verify"} disabled={!canMutate || busyAction !== null} onClick={() => onVerify(false)}>
          Verify State-Machine Safety
        </Button>
        <Button type="button" size="sm" variant="primary" loading={busyAction === "inject_verify"} disabled={!canMutate || busyAction !== null} onClick={() => onVerify(true)}>
          Inject P-10 Guard &amp; Re-Verify
        </Button>
      </div>

      {verification ? (
        <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-fg">{`${verification.workflow_name} · states_explored: ${verification.states_explored}`}</span>
            <SemanticBadge kind={statusSpec.kind} labelOverride={statusSpec.labelOverride} />
          </div>

          <ul aria-label="Formal safety invariants" className="space-y-1 border-t border-border pt-1.5">
            {verification.invariants_checked.map((inv) => (
              <li key={inv.invariant_id} className="flex items-center justify-between gap-2 text-[10px]">
                <span className="text-fg">{inv.invariant_id}</span>
                <span className={`font-semibold uppercase ${inv.passed ? "text-ok" : "text-danger"}`}>{inv.passed ? "PASS" : "FAIL"}</span>
              </li>
            ))}
          </ul>

          {verification.violations.length > 0 ? (
            <div className="space-y-1.5 rounded-xs border border-danger/50 bg-danger-subtle p-2 text-[10px] text-fg">
              {verification.violations.map((v, idx) => (
                <div key={`${v.invariant_id}-${v.offending_node}-${idx}`} className="space-y-0.5">
                  <div className="font-semibold text-danger">{`${v.severity} · ${v.invariant_id} (${v.offending_node})`}</div>
                  <div data-testid="safety-counterexample-path" className="text-fg">{v.counterexample_path.join(" → ")}</div>
                  <div className="font-sans text-[11px] text-fg-muted">{v.remediation}</div>
                </div>
              ))}
            </div>
          ) : (
            <div role="status" className="rounded-xs border border-ok/40 bg-ok-subtle px-2.5 py-1.5 text-[10px] text-fg">
              <div className="font-semibold text-ok">VERIFIED_SAFE · Bounded Reachability Proof Complete</div>
              {verification.p10_guards_injected.length > 0 ? (
                <div className="text-fg">{`p10_guards_injected: ${verification.p10_guards_injected.join(", ")}`}</div>
              ) : null}
            </div>
          )}

          <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[10px]">
            <span className="text-fg-muted">proof_sha256:</span>
            <code data-testid="safety-proof-sha256" title={verification.proof_sha256} className="max-w-[220px] truncate text-teal-accent">
              {formatDigestPrefix(verification.proof_sha256)}
            </code>
          </div>
        </div>
      ) : (
        <div className="rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px] text-fg-muted">
          Run bounded model checking across reachable agent transitions to detect unguarded destructive tools, privilege escalation, unbounded loops, or air-gap egress leaks.
        </div>
      )}
    </div>
  );
}

interface EdgeMeshCardProps {
  dataClassSelectId: string; allowBurstCheckboxId: string;
  meshNodes: MeshNodeRecord[]; dataClassification: DataClassification; allowSanitizedBurst: boolean;
  canMutate: boolean; busyAction: string | null; handoff: MeshHandoffRecord | null;
  onChangeDataClassification: (val: DataClassification) => void;
  onChangeAllowBurst: (val: boolean) => void;
  onDispatch: () => void;
}

function FederatedEdgeMeshSubCard({
  dataClassSelectId, allowBurstCheckboxId, meshNodes, dataClassification,
  allowSanitizedBurst, canMutate, busyAction, handoff,
  onChangeDataClassification, onChangeAllowBurst, onDispatch,
}: EdgeMeshCardProps): React.JSX.Element {
  const handoffBadge = resolveHandoffStatusBadge(handoff?.status ?? "IDLE");
  const allZeroRawPii = handoff ? handoff.stages.every((s) => s.zero_raw_pii_egress) : true;

  return (
    <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-fg">Federated Edge-to-Cluster Agent Mesh</h3>
        <SemanticBadge kind={handoffBadge.kind} labelOverride={handoffBadge.labelOverride} />
      </div>

      <ul aria-label="Attested mesh nodes" className="space-y-1.5 rounded-xs border border-border bg-canvas p-2 font-mono text-[10px]">
        {meshNodes.map((node) => {
          const tierSpec = resolveMeshTierBadge(node.tier);
          const halSpec = resolveHalBadge(node.hardware_hal);
          return (
            <li key={node.node_id} className="flex flex-wrap items-center justify-between gap-1.5 border-b border-border pb-1 last:border-b-0 last:pb-0">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-semibold text-fg">{node.node_id}</span>
                <SemanticBadge kind={tierSpec.kind} labelOverride={tierSpec.labelOverride} />
                <SemanticBadge kind={halSpec.kind} labelOverride={halSpec.labelOverride} />
              </div>
              <div className="flex items-center gap-2 text-fg-muted">
                <span>{`${node.vram_gb} GB VRAM`}</span>
                <code title={node.attestation_sha256} className="text-teal-accent">{formatDigestPrefix(node.attestation_sha256)}</code>
              </div>
            </li>
          );
        })}
      </ul>

      <div className="space-y-2">
        <div className="flex flex-col gap-1 text-xs text-fg-muted">
          <label htmlFor={dataClassSelectId} className="font-medium text-fg">Data Classification</label>
          <select
            id={dataClassSelectId}
            value={dataClassification}
            onChange={(e) => onChangeDataClassification(e.target.value as DataClassification)}
            className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
          >
            {DATA_CLASSIFICATIONS.map((dc) => (
              <option key={dc} value={dc}>{dc}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2 pt-0.5">
          <input
            id={allowBurstCheckboxId}
            type="checkbox"
            checked={allowSanitizedBurst}
            onChange={(e) => onChangeAllowBurst(e.target.checked)}
            className="h-3.5 w-3.5 rounded-xs border border-border-control"
          />
          <label htmlFor={allowBurstCheckboxId} className="text-xs text-fg">Allow Sanitized Cluster Burst</label>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="primary" loading={busyAction === "dispatch_mesh"} disabled={!canMutate || busyAction !== null} onClick={onDispatch}>
          Dispatch Attested Edge-to-Cluster Handoff
        </Button>
      </div>

      {handoff ? (
        <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <SemanticBadge kind={handoffBadge.kind} labelOverride={handoffBadge.labelOverride} />
              {allZeroRawPii ? <SemanticBadge kind="locked" labelOverride="zero_raw_pii_egress" /> : null}
            </div>
            <span className="font-semibold text-teal-accent">{`total_cost_usd: $${handoff.total_cost_usd.toFixed(2)}`}</span>
          </div>

          <ul aria-label="Mesh handoff stage placements" className="space-y-1 border-t border-border pt-1.5 text-[10px]">
            {handoff.stages.map((stage, idx) => {
              const stTier = resolveMeshTierBadge(stage.target_tier);
              return (
                <li key={`${stage.stage_name}-${idx}`} className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <SemanticBadge kind={stTier.kind} labelOverride={stTier.labelOverride} />
                    <span className="text-fg">{`${stage.stage_name} (${stage.node_id})`}</span>
                  </div>
                  <span className="text-fg-muted">{`$${stage.cost_usd.toFixed(2)} · ${stage.hardware_hal}`}</span>
                </li>
              );
            })}
          </ul>

          <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[10px]">
            <span className="text-fg-muted">attestation_sha256:</span>
            <code data-testid="mesh-handoff-attestation-sha256" title={handoff.attestation_sha256} className="max-w-[220px] truncate text-teal-accent">
              {formatDigestPrefix(handoff.attestation_sha256)}
            </code>
          </div>
        </div>
      ) : (
        <div className="rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px] text-fg-muted">
          Scrub restricted PII locally on Apple Metal Secure Enclave ($0.00) before bursting sanitized synthesis to attested Confidential Compute clusters.
        </div>
      )}
    </div>
  );
}

export function FormalSafetyAndEdgeMeshPanel({
  workspaceId = "default", activeRbacRole = "owner",
}: FormalSafetyAndEdgeMeshPanelProps): React.JSX.Element {
  const uid = useId();
  const canMutate = canRbacMutateSafetyMesh(activeRbacRole);
  const [selectedWorkflowName, setSelectedWorkflowName] = useState<string>("treasury-wire-approver");
  const [airgapMode, setAirgapMode] = useState<boolean>(false);
  const [dataClassification, setDataClassification] = useState<DataClassification>("restricted_pii");
  const [allowSanitizedBurst, setAllowSanitizedBurst] = useState<boolean>(true);
  const [verification, setVerification] = useState<SafetyVerificationRecord | null>(null);
  const [meshNodes, setMeshNodes] = useState<MeshNodeRecord[]>([]);
  const [handoff, setHandoff] = useState<MeshHandoffRecord | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [errorAlert, setErrorAlert] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void listSafetyVerifications(workspaceId, 10, activeRbacRole).then((items) => { if (!cancelled && items.length > 0) setVerification(items[0] ?? null); }).catch((err) => { if (!cancelled) setErrorAlert(formatErr(err, "Failed to load safety verifications.")); });
    void listMeshNodes(workspaceId, activeRbacRole).then((nodes) => { if (!cancelled) setMeshNodes(nodes); }).catch((err) => { if (!cancelled) setErrorAlert(formatErr(err, "Failed to load mesh nodes.")); });
    void listMeshHandoffs(workspaceId, 10, activeRbacRole).then((items) => { if (!cancelled && items.length > 0) setHandoff(items[0] ?? null); }).catch((err) => { if (!cancelled) setErrorAlert(formatErr(err, "Failed to load mesh handoffs.")); });
    return () => { cancelled = true; };
  }, [activeRbacRole, workspaceId]);

  const formatErr = (err: unknown, fallback: string): string =>
    err instanceof PlatformSafetyMeshHttpError ? `HTTP ${err.status} · ${err.message}` : err instanceof Error ? err.message : fallback;

  const handleVerify = async (injectP10: boolean) => {
    if (!canMutate) return;
    setBusyAction(injectP10 ? "inject_verify" : "verify"); setErrorAlert(null);
    try {
      const preset = WORKFLOW_PRESETS.find((p) => p.workflowName === selectedWorkflowName) ?? WORKFLOW_PRESETS[0]!;
      setVerification(await verifyWorkflowSafety({ workspace_id: workspaceId, workflow_id: preset.workflowId, workflow_name: preset.workflowName, airgap_mode: airgapMode, inject_p10_guards: injectP10 }, activeRbacRole));
    } catch (err) { setErrorAlert(formatErr(err, "Failed to verify workflow state-machine safety.")); }
    finally { setBusyAction(null); }
  };

  const handleDispatch = async () => {
    if (!canMutate) return;
    setBusyAction("dispatch_mesh"); setErrorAlert(null);
    try {
      setHandoff(await dispatchMeshHandoff({ workspace_id: workspaceId, workflow_name: "clinical-synthesis-pipeline", data_classification: dataClassification, allow_sanitized_burst: allowSanitizedBurst }, activeRbacRole));
    } catch (err) { setErrorAlert(formatErr(err, "Failed to dispatch attested edge-to-cluster mesh handoff.")); }
    finally { setBusyAction(null); }
  };

  return (
    <section id="formal-safety-edge-mesh-panel" aria-label="Formal safety state-machine verifier and federated edge mesh" className="space-y-4 rounded-md border border-border-strong bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-border pb-3">
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-fg">Formal Safety State-Machine Verifier &amp; Federated Edge Mesh</h2>
            <SemanticBadge kind="opencore" labelOverride="SQLite WAL · Hardware Attested" />
            {!canMutate ? (
              <span className="rounded-xs border border-border-strong bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
                {`RBAC: ${activeRbacRole} (read-only)`}
              </span>
            ) : null}
          </div>
          <p className="text-xs text-fg-muted">
            Prove bounded state-machine safety invariants before execution and orchestrate zero-raw-PII workloads across Apple Metal Secure Enclave and Confidential Compute clusters.
          </p>
        </div>
      </div>

      {errorAlert ? (
        <div role="alert" className="rounded-xs border border-danger/55 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          <span className="font-semibold text-danger">{errorAlert}</span>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <SafetyVerifierSubCard
          workflowSelectId={`${uid}-safety-workflow`} airgapCheckboxId={`${uid}-safety-airgap`}
          selectedWorkflowName={selectedWorkflowName} airgapMode={airgapMode} canMutate={canMutate} busyAction={busyAction}
          verification={verification} onChangeWorkflow={setSelectedWorkflowName} onChangeAirgap={setAirgapMode}
          onVerify={(injectP10) => { void handleVerify(injectP10); }}
        />
        <FederatedEdgeMeshSubCard
          dataClassSelectId={`${uid}-mesh-data-class`} allowBurstCheckboxId={`${uid}-mesh-allow-burst`}
          meshNodes={meshNodes} dataClassification={dataClassification} allowSanitizedBurst={allowSanitizedBurst}
          canMutate={canMutate} busyAction={busyAction} handoff={handoff}
          onChangeDataClassification={setDataClassification} onChangeAllowBurst={setAllowSanitizedBurst}
          onDispatch={() => { void handleDispatch(); }}
        />
      </div>
    </section>
  );
}
