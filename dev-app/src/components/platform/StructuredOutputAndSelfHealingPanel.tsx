import React, { useEffect, useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import {
  AGENT_DECISION_JSON_SCHEMA, applySelfHealingPatch, canRbacMutateHealing,
  diagnoseFailureRootCause, enforceStructuredOutput, FAILURE_SCENARIO_FIXTURES,
  fetchSelfHealingDiagnoses, fetchStructuredOutputRuns, normalizeContentBlocks,
  PlatformHealingHttpError, PROVIDER_WIRE_FIXTURES,
  type ApplySelfHealingResponse, type ContentBlockKind, type FailureRootCauseClass,
  type FailureScenarioKey, type HealingRbacRole, type NormalizedContentEnvelope,
  type ProviderWireFormat, type SelfHealingDiagnosisRecord, type SelfHealingStatus,
  type StructuredOutputRunRecord, type StructuredOutputStatus,
} from "@/lib/platformHealingApi";

export interface StructuredOutputAndSelfHealingPanelProps {
  workspaceId?: string;
  activeRbacRole?: HealingRbacRole;
}

const PROVIDER_FORMATS: ReadonlyArray<ProviderWireFormat> = ["deepseek_opencore", "anthropic", "openai", "gemini"];
const FAILURE_SCENARIOS: ReadonlyArray<FailureScenarioKey> = ["schema_mismatch", "context_truncation", "kbrain_conflict", "airgap_egress_blocked"];

function resolveBlockBadge(kind: ContentBlockKind): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (kind) {
    case "reasoning": return { kind: "ai", labelOverride: "reasoning" };
    case "tool_call": return { kind: "running", labelOverride: "tool_call" };
    case "citation": return { kind: "live", labelOverride: "citation" };
    case "structured_json": return { kind: "passed", labelOverride: "structured_json" };
    case "text": return { kind: "ready", labelOverride: "text" };
    default: { const _exhaustive: never = kind; return _exhaustive; }
  }
}

function resolveStructuredStatusBadge(status: StructuredOutputStatus | "IDLE"): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (status) {
    case "VALID": return { kind: "passed", labelOverride: "VALID" };
    case "REPAIRED_VALID": return { kind: "opencore", labelOverride: "REPAIRED_VALID" };
    case "SCHEMA_REJECTED": return { kind: "failed", labelOverride: "SCHEMA_REJECTED" };
    case "IDLE": return { kind: "ready", labelOverride: "AWAITING_SCHEMA" };
    default: { const _exhaustive: never = status; return _exhaustive; }
  }
}

function resolveFailureClassBadge(failureClass: FailureRootCauseClass): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (failureClass) {
    case "schema_mismatch": return { kind: "reconfirm", labelOverride: "schema_mismatch" };
    case "context_truncation": return { kind: "needs-approval", labelOverride: "context_truncation" };
    case "prompt_ambiguity": return { kind: "estimated", labelOverride: "prompt_ambiguity" };
    case "kbrain_conflict": return { kind: "needs-approval", labelOverride: "kbrain_conflict" };
    case "airgap_egress_blocked": return { kind: "locked", labelOverride: "airgap_egress_blocked" };
    default: { const _exhaustive: never = failureClass; return _exhaustive; }
  }
}

function resolveHealingStatusBadge(status: SelfHealingStatus | "IDLE"): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (status) {
    case "DIAGNOSED": return { kind: "needs-approval", labelOverride: "DIAGNOSED" };
    case "VERIFIED_HEALED": return { kind: "passed", labelOverride: "VERIFIED_HEALED" };
    case "IDLE": return { kind: "ready", labelOverride: "READY_TO_DIAGNOSE" };
    default: { const _exhaustive: never = status; return _exhaustive; }
  }
}

interface NormalizerColumnProps {
  providerSelectId: string; strictCheckboxId: string;
  providerFormat: ProviderWireFormat; strictMode: boolean; canMutate: boolean; busyAction: string | null;
  envelope: NormalizedContentEnvelope | null; activeRun: StructuredOutputRunRecord | null;
  onChangeProvider: (fmt: ProviderWireFormat) => void; onChangeStrictMode: (val: boolean) => void;
  onNormalize: () => void; onEnforceSchema: () => void;
}

function StructuredNormalizerColumn({
  providerSelectId, strictCheckboxId, providerFormat, strictMode, canMutate, busyAction,
  envelope, activeRun, onChangeProvider, onChangeStrictMode, onNormalize, onEnforceSchema,
}: NormalizerColumnProps): React.JSX.Element {
  const runBadge = resolveStructuredStatusBadge(activeRun?.status ?? "IDLE");

  return (
    <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-fg">Typed Structured-Output &amp; Content-Block Normalizer</h3>
        <SemanticBadge kind={runBadge.kind} labelOverride={runBadge.labelOverride} />
      </div>

      <div className="space-y-2">
        <div className="flex flex-col gap-1 text-xs text-fg-muted">
          <label htmlFor={providerSelectId} className="font-medium text-fg">Provider Wire Format</label>
          <select
            id={providerSelectId}
            value={providerFormat}
            onChange={(e) => onChangeProvider(e.target.value as ProviderWireFormat)}
            className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
          >
            {PROVIDER_FORMATS.map((fmt) => (
              <option key={fmt} value={fmt}>{PROVIDER_WIRE_FIXTURES[fmt].label}</option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-2 pt-0.5">
          <input
            id={strictCheckboxId}
            type="checkbox"
            checked={strictMode}
            onChange={(e) => onChangeStrictMode(e.target.checked)}
            className="h-3.5 w-3.5 rounded-xs border border-border-control"
          />
          <label htmlFor={strictCheckboxId} className="text-xs text-fg">
            Strict Schema Mode (No Repair)
          </label>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="secondary" loading={busyAction === "normalize"} disabled={busyAction !== null} onClick={onNormalize}>
          Normalize Content Blocks
        </Button>
        <Button type="button" size="sm" variant="primary" loading={busyAction === "enforce"} disabled={!canMutate || busyAction !== null} onClick={onEnforceSchema}>
          Enforce JSON Schema Contract
        </Button>
      </div>

      <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
        {envelope ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-fg">{`${envelope.provider_format} · ${envelope.block_count} blocks`}</span>
              <span className="text-teal-accent">{`dlp_redactions: ${envelope.dlp_redactions}`}</span>
            </div>
            <ul aria-label="Normalized content blocks" className="space-y-1 border-t border-border pt-1.5">
              {envelope.content_blocks.map((blk) => {
                const spec = resolveBlockBadge(blk.kind);
                return (
                  <li key={`${blk.index}-${blk.kind}`} className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-fg">
                    <SemanticBadge kind={spec.kind} labelOverride={spec.labelOverride} />
                    <span className="max-w-[260px] truncate text-fg-muted">{blk.content}</span>
                  </li>
                );
              })}
            </ul>
            <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[10px]">
              <span className="text-fg-muted">envelope_sha256:</span>
              <code data-testid="healing-envelope-sha256" title={envelope.envelope_sha256} className="max-w-[200px] truncate text-teal-accent">
                {envelope.envelope_sha256}
              </code>
            </div>
          </>
        ) : (
          <div className="text-fg-muted">
            Select a provider wire format and click Normalize Content Blocks to extract canonical reasoning, tool_call, citation, structured_json, and text blocks.
          </div>
        )}
      </div>

      {activeRun ? (
        <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-fg">{`${activeRun.schema_name} (${activeRun.model_id})`}</span>
            <SemanticBadge kind={runBadge.kind} labelOverride={runBadge.labelOverride} />
          </div>
          {activeRun.repair_actions.length > 0 ? (
            <div className="text-[10px] text-teal-accent">{`repair_actions: ${activeRun.repair_actions.join(", ")}`}</div>
          ) : null}
          {activeRun.validation_errors.length > 0 ? (
            <div className="text-[10px] text-danger">{`validation_errors: ${activeRun.validation_errors.join(" | ")}`}</div>
          ) : null}
          {activeRun.validated_data ? (
            <pre aria-label="Validated JSON contract preview" className="overflow-x-auto rounded-xs border border-border bg-code p-2 text-[10px] text-fg">
              <code>{JSON.stringify(activeRun.validated_data, null, 2)}</code>
            </pre>
          ) : null}
          <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[10px]">
            <span className="text-fg-muted">run_sha256:</span>
            <code data-testid="structured-run-sha256" title={activeRun.run_sha256} className="max-w-[200px] truncate text-teal-accent">
              {activeRun.run_sha256}
            </code>
          </div>
        </div>
      ) : null}
    </div>
  );
}

interface RootCauserColumnProps {
  scenarioSelectId: string;
  selectedScenario: FailureScenarioKey; canMutate: boolean; busyAction: string | null;
  diagnosis: SelfHealingDiagnosisRecord | null; applyReceipt: ApplySelfHealingResponse | null;
  onChangeScenario: (key: FailureScenarioKey) => void;
  onDiagnose: () => void; onApplyAndPromote: () => void;
}

function SelfHealingRootCauserColumn({
  scenarioSelectId, selectedScenario, canMutate, busyAction, diagnosis, applyReceipt,
  onChangeScenario, onDiagnose, onApplyAndPromote,
}: RootCauserColumnProps): React.JSX.Element {
  const statusBadge = resolveHealingStatusBadge(diagnosis?.status ?? "IDLE");
  const failureBadge = diagnosis ? resolveFailureClassBadge(diagnosis.failure_class) : null;
  const confidencePct = diagnosis ? (diagnosis.confidence <= 1 ? Math.round(diagnosis.confidence * 100) : Math.round(diagnosis.confidence)) : 0;
  const promotedCaseId = applyReceipt?.promoted_eval_case?.case_id ?? diagnosis?.promoted_eval_case_id ?? null;

  return (
    <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-semibold text-fg">Autonomous Self-Healing Failure Root-Causer</h3>
        <SemanticBadge kind={statusBadge.kind} labelOverride={statusBadge.labelOverride} />
      </div>

      <div className="flex flex-col gap-1 text-xs text-fg-muted">
        <label htmlFor={scenarioSelectId} className="font-medium text-fg">Failure Trace Scenario</label>
        <select
          id={scenarioSelectId}
          value={selectedScenario}
          onChange={(e) => onChangeScenario(e.target.value as FailureScenarioKey)}
          className="min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
        >
          {FAILURE_SCENARIOS.map((sc) => (
            <option key={sc} value={sc}>{FAILURE_SCENARIO_FIXTURES[sc].label}</option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="secondary" loading={busyAction === "diagnose"} disabled={!canMutate || busyAction !== null} onClick={onDiagnose}>
          Diagnose Root Cause
        </Button>
        <Button type="button" size="sm" variant="primary" loading={busyAction === "apply_heal"} disabled={!canMutate || busyAction !== null} onClick={onApplyAndPromote}>
          Apply Patch &amp; Promote Golden Eval
        </Button>
      </div>

      {diagnosis ? (
        <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1.5">
              {failureBadge ? <SemanticBadge kind={failureBadge.kind} labelOverride={failureBadge.labelOverride} /> : null}
              <SemanticBadge kind={statusBadge.kind} labelOverride={statusBadge.labelOverride} />
            </div>
            <span className="font-semibold text-teal-accent">{`${confidencePct}% confidence`}</span>
          </div>

          <p className="font-sans text-xs text-fg">{diagnosis.summary}</p>

          <pre aria-label="Proposed self-healing unified diff" className="overflow-x-auto rounded-xs border border-border bg-code p-2 text-[10px] text-fg">
            <code>{diagnosis.proposed_patch.unified_diff}</code>
          </pre>

          {diagnosis.status === "VERIFIED_HEALED" || applyReceipt ? (
            <div role="status" className="space-y-1 rounded-xs border border-ok/40 bg-ok-subtle px-2.5 py-1.5 text-[10px] text-fg">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-ok">VERIFIED_HEALED · Counterfactual Replay Verified</span>
                <span>{`$${(applyReceipt?.replay_cost_usd ?? 0).toFixed(2)} cached replay (${applyReceipt?.cached_steps_reused ?? 2} steps reused)`}</span>
              </div>
              {promotedCaseId ? (
                <div className="flex items-center justify-between gap-2">
                  <span className="text-fg-muted">Promoted Golden Eval Case:</span>
                  <code data-testid="promoted-healing-eval-case-id" className="font-semibold text-teal-accent">{promotedCaseId}</code>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[10px]">
            <span className="text-fg-muted">diagnosis_sha256:</span>
            <code data-testid="healing-diagnosis-sha256" title={diagnosis.diagnosis_sha256} className="max-w-[200px] truncate text-teal-accent">
              {diagnosis.diagnosis_sha256}
            </code>
          </div>
        </div>
      ) : (
        <div className="rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px] text-fg-muted">
          Choose a failed Flight-Tape scenario and click Diagnose Root Cause to synthesize a verified prompt/schema/routing diff and promote a Golden Eval regression case.
        </div>
      )}
    </div>
  );
}

export function StructuredOutputAndSelfHealingPanel({
  workspaceId = "default", activeRbacRole = "owner",
}: StructuredOutputAndSelfHealingPanelProps): React.JSX.Element {
  const uid = useId();
  const canMutate = canRbacMutateHealing(activeRbacRole);
  const [providerFormat, setProviderFormat] = useState<ProviderWireFormat>("deepseek_opencore");
  const [strictMode, setStrictMode] = useState<boolean>(false);
  const [selectedScenario, setSelectedScenario] = useState<FailureScenarioKey>("schema_mismatch");
  const [diagnosedScenario, setDiagnosedScenario] = useState<FailureScenarioKey | null>(null);
  const [envelope, setEnvelope] = useState<NormalizedContentEnvelope | null>(null);
  const [activeRun, setActiveRun] = useState<StructuredOutputRunRecord | null>(null);
  const [diagnosis, setDiagnosis] = useState<SelfHealingDiagnosisRecord | null>(null);
  const [applyReceipt, setApplyReceipt] = useState<ApplySelfHealingResponse | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [errorAlert, setErrorAlert] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchStructuredOutputRuns(workspaceId, 10, activeRbacRole).then((runs) => { if (!cancelled && runs.length > 0) setActiveRun(runs[0] ?? null); }).catch((err) => { if (!cancelled) setErrorAlert(formatErr(err, "Failed to load structured output runs.")); });
    void fetchSelfHealingDiagnoses(workspaceId, 10, activeRbacRole).then((diags) => { if (!cancelled && diags.length > 0) setDiagnosis(diags[0] ?? null); }).catch((err) => { if (!cancelled) setErrorAlert(formatErr(err, "Failed to load self-healing diagnoses.")); });
    return () => { cancelled = true; };
  }, [activeRbacRole, workspaceId]);

  const formatErr = (err: unknown, fallback: string): string =>
    err instanceof PlatformHealingHttpError ? `HTTP ${err.status} · ${err.message}` : err instanceof Error ? err.message : fallback;

  const handleNormalize = async () => {
    setBusyAction("normalize"); setErrorAlert(null);
    try {
      const fx = PROVIDER_WIRE_FIXTURES[providerFormat];
      setEnvelope(await normalizeContentBlocks({ workspace_id: workspaceId, provider_format: providerFormat, model_id: fx.model_id, raw_payload: fx.raw_payload }, activeRbacRole));
    } catch (err) {
      setErrorAlert(formatErr(err, "Failed to normalize provider content blocks."));
    } finally { setBusyAction(null); }
  };

  const handleEnforceSchema = async () => {
    if (!canMutate) return;
    setBusyAction("enforce"); setErrorAlert(null);
    try {
      const fx = PROVIDER_WIRE_FIXTURES[providerFormat];
      const run = await enforceStructuredOutput(
        { workspace_id: workspaceId, schema_name: "AgentDecisionContract", provider_format: providerFormat, model_id: fx.model_id, json_schema: AGENT_DECISION_JSON_SCHEMA, raw_output: fx.sample_raw_output, strict_mode: strictMode, fail_closed: false },
        activeRbacRole,
      );
      setActiveRun(run);
    } catch (err) {
      if (err instanceof PlatformHealingHttpError && err.run) setActiveRun(err.run);
      setErrorAlert(formatErr(err, "Failed to enforce structured JSON Schema contract."));
    } finally { setBusyAction(null); }
  };

  const runDiagnosisForScenario = async (scenario: FailureScenarioKey): Promise<SelfHealingDiagnosisRecord> => {
    const fx = FAILURE_SCENARIO_FIXTURES[scenario];
    const created = await diagnoseFailureRootCause({ workspace_id: workspaceId, workflow_name: fx.workflow_name, failed_step: fx.failed_step }, activeRbacRole);
    setDiagnosis(created);
    setDiagnosedScenario(scenario);
    setApplyReceipt(null);
    return created;
  };

  const handleDiagnose = async () => {
    if (!canMutate) return;
    setBusyAction("diagnose"); setErrorAlert(null);
    try { await runDiagnosisForScenario(selectedScenario); }
    catch (err) { setErrorAlert(formatErr(err, "Failed to diagnose Flight-Tape root cause.")); }
    finally { setBusyAction(null); }
  };

  const handleApplyAndPromote = async () => {
    if (!canMutate) return;
    setBusyAction("apply_heal"); setErrorAlert(null);
    try {
      const target = diagnosis && diagnosedScenario === selectedScenario && diagnosis.status !== "VERIFIED_HEALED"
        ? diagnosis
        : await runDiagnosisForScenario(selectedScenario);
      const res = await applySelfHealingPatch(target.diagnosis_id, { workspace_id: workspaceId, promote_to_eval: true, eval_title: `Self-Healed Regression · ${target.failure_class}` }, activeRbacRole);
      setDiagnosis(res.diagnosis);
      setApplyReceipt(res);
    } catch (err) {
      setErrorAlert(formatErr(err, "Failed to apply self-healing patch and promote Golden Eval."));
    } finally { setBusyAction(null); }
  };

  return (
    <section id="structured-output-self-healing-panel" aria-label="Structured-output normalizer and self-healing root-causer" className="space-y-4 rounded-md border border-border-strong bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-border pb-3">
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-fg">Structured-Output Normalizer &amp; Self-Healing Root-Causer</h2>
            <SemanticBadge kind="opencore" labelOverride="SQLite WAL · Zero-Egress Repair" />
            {!canMutate ? (
              <span className="rounded-xs border border-border-strong bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
                {`RBAC: ${activeRbacRole} (read-only)`}
              </span>
            ) : null}
          </div>
          <p className="text-xs text-fg-muted">
            Normalize OpenCore, Anthropic, OpenAI, and Gemini wire payloads into DLP-scrubbed content blocks, enforce deterministic JSON-Schema contracts, and root-cause failed traces into verified Golden Evals.
          </p>
        </div>
      </div>

      {errorAlert ? (
        <div role="alert" className="rounded-xs border border-danger/55 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg">
          <span className="font-semibold text-danger">{errorAlert}</span>
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <StructuredNormalizerColumn
          providerSelectId={`${uid}-provider-format`} strictCheckboxId={`${uid}-strict-mode`}
          providerFormat={providerFormat} strictMode={strictMode} canMutate={canMutate} busyAction={busyAction}
          envelope={envelope} activeRun={activeRun}
          onChangeProvider={setProviderFormat} onChangeStrictMode={setStrictMode}
          onNormalize={() => { void handleNormalize(); }} onEnforceSchema={() => { void handleEnforceSchema(); }}
        />
        <SelfHealingRootCauserColumn
          scenarioSelectId={`${uid}-failure-scenario`}
          selectedScenario={selectedScenario} canMutate={canMutate} busyAction={busyAction}
          diagnosis={diagnosis} applyReceipt={applyReceipt}
          onChangeScenario={setSelectedScenario}
          onDiagnose={() => { void handleDiagnose(); }} onApplyAndPromote={() => { void handleApplyAndPromote(); }}
        />
      </div>
    </section>
  );
}
