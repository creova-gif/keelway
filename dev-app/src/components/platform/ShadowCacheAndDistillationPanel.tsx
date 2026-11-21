import React, { useEffect, useId, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import {
  canRbacMutateDistill, compileDistillationDataset, evaluateDistillationPromotion,
  evaluateShadowPrompt, fetchDistillationDatasets, fetchSemanticCacheStats,
  fetchShadowPairs, PlatformDistillHttpError,
  type DistillationDatasetRecord, type DistillationPromotionEvaluation,
  type DistillRbacRole, type ExportFormat, type PromotionVerdict,
  type SemanticCacheStatsResponse, type ShadowDistillPairRecord,
  type ShadowEvaluationRecord, type ShadowVerdict,
} from "@/lib/platformDistillApi";

export type ActiveTab = "shadow_router" | "qlora_distill";

export interface ShadowCacheAndDistillationPanelProps {
  workspaceId?: string;
  activeRbacRole?: DistillRbacRole;
}

const DEFAULT_PROMPT = "Refactor retry loop with bounded exponential backoff in Python";
const DEFAULT_CODE_OUTPUT = "def retry_with_backoff(max_attempts: int = 3, base_delay: float = 0.25) -> float: return min(4.0, base_delay * (2 ** max_attempts))";
const EXPORT_FORMATS: ReadonlyArray<ExportFormat> = ["dpo_preference", "sft_jsonl"];
const CTRL_CLS = "min-h-ctrl-sm rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg";

function formatDigestPrefix(digest: string): string {
  return (digest.startsWith("sha256:") ? digest : `sha256:${digest}`).slice(0, 23);
}

function resolveShadowVerdictBadge(verdict: ShadowVerdict): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (verdict) {
    case "CACHE_HIT": return { kind: "passed", labelOverride: "CACHE_HIT" };
    case "LOCAL_PARITY_READY": return { kind: "opencore", labelOverride: "LOCAL_PARITY_READY" };
    case "SHADOW_CAPTURED": return { kind: "needs-approval", labelOverride: "SHADOW_CAPTURED" };
    default: { const _exhaustive: never = verdict; return _exhaustive; }
  }
}

function formatExportFormatLabel(format: ExportFormat): string {
  switch (format) {
    case "dpo_preference": return "dpo_preference · DPO Chosen/Rejected Preference";
    case "sft_jsonl": return "sft_jsonl · Supervised Fine-Tuning JSONL";
    default: { const _exhaustive: never = format; return _exhaustive; }
  }
}

function resolvePromotionVerdictBadge(verdict: PromotionVerdict): { kind: SemanticBadgeKind; labelOverride: string } {
  switch (verdict) {
    case "PROMOTE_TO_OPENCORE": return { kind: "passed", labelOverride: "PROMOTE_TO_OPENCORE" };
    case "NEEDS_MORE_PAIRS": return { kind: "needs-approval", labelOverride: "NEEDS_MORE_PAIRS" };
    case "HOLD_ON_FRONTIER": return { kind: "failed", labelOverride: "HOLD_ON_FRONTIER" };
    default: { const _exhaustive: never = verdict; return _exhaustive; }
  }
}

function resolveActiveTabPanel(tab: ActiveTab, shadowNode: React.JSX.Element, distillNode: React.JSX.Element): React.JSX.Element {
  switch (tab) {
    case "shadow_router": return shadowNode;
    case "qlora_distill": return distillNode;
    default: { const _exhaustive: never = tab; return _exhaustive; }
  }
}

interface ShadowRouterTabProps {
  uid: string; taskTag: string; prompt: string; frontierModel: string; localModel: string;
  frontierOutput: string; localOutput: string; similarityThreshold: string;
  isReadOnlyRole: boolean; busyAction: string | null;
  shadowEval: ShadowEvaluationRecord | null; shadowPairs: ShadowDistillPairRecord[];
  onChangeTaskTag: (v: string) => void; onChangePrompt: (v: string) => void;
  onChangeFrontierModel: (v: string) => void; onChangeLocalModel: (v: string) => void;
  onChangeFrontierOutput: (v: string) => void; onChangeLocalOutput: (v: string) => void;
  onChangeThreshold: (v: string) => void; onEvaluateShadow: () => void;
}

function ShadowRouterTabContent(props: ShadowRouterTabProps): React.JSX.Element {
  const { uid, taskTag, prompt, frontierModel, localModel, frontierOutput, localOutput, similarityThreshold, isReadOnlyRole, busyAction, shadowEval, shadowPairs } = props;
  const verdictBadge = shadowEval ? resolveShadowVerdictBadge(shadowEval.verdict) : null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-2.5 rounded-sm border border-border bg-chrome p-3">
        <h3 className="text-xs font-semibold text-fg">Semantic Shingle Cache &amp; Dual-Run Shadow Inputs</h3>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-task-tag`} className="font-medium text-fg">Task Tag</label>
            <input id={`${uid}-task-tag`} type="text" aria-label="Task Tag" value={taskTag} onChange={(e) => props.onChangeTaskTag(e.target.value)} className={CTRL_CLS} />
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-sim-threshold`} className="font-medium text-fg">Similarity Threshold</label>
            <input id={`${uid}-sim-threshold`} type="number" step="0.01" min="0.5" max="1" aria-label="Similarity Threshold" value={similarityThreshold} onChange={(e) => props.onChangeThreshold(e.target.value)} className={CTRL_CLS} />
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-frontier-model`} className="font-medium text-fg">Frontier Model</label>
            <input id={`${uid}-frontier-model`} type="text" aria-label="Frontier Model" value={frontierModel} onChange={(e) => props.onChangeFrontierModel(e.target.value)} className={CTRL_CLS} />
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-local-model`} className="font-medium text-fg">Local Candidate</label>
            <input id={`${uid}-local-model`} type="text" aria-label="Local Candidate" value={localModel} onChange={(e) => props.onChangeLocalModel(e.target.value)} className={CTRL_CLS} />
          </div>
        </div>
        <div className="flex flex-col gap-1 text-xs text-fg-muted">
          <label htmlFor={`${uid}-prompt`} className="font-medium text-fg">Prompt</label>
          <textarea id={`${uid}-prompt`} rows={2} aria-label="Prompt" value={prompt} onChange={(e) => props.onChangePrompt(e.target.value)} className="rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg" />
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-frontier-out`} className="font-medium text-fg">Frontier Reference Output</label>
            <textarea id={`${uid}-frontier-out`} rows={2} aria-label="Frontier Reference Output" value={frontierOutput} onChange={(e) => props.onChangeFrontierOutput(e.target.value)} className="rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-[11px] text-fg" />
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-local-out`} className="font-medium text-fg">Local Candidate Output</label>
            <textarea id={`${uid}-local-out`} rows={2} aria-label="Local Candidate Output" value={localOutput} onChange={(e) => props.onChangeLocalOutput(e.target.value)} className="rounded-sm border border-border-control bg-canvas px-2 py-1 font-mono text-[11px] text-fg" />
          </div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          <span className="font-mono text-[10px] text-fg-muted">Workspace + task isolated · Pre-storage DLP scrubbed</span>
          <Button type="button" size="sm" variant="primary" aria-label="Evaluate shadow prompt" loading={busyAction === "shadow_eval"} disabled={isReadOnlyRole || busyAction !== null} onClick={props.onEvaluateShadow}>
            Evaluate shadow prompt
          </Button>
        </div>
      </div>

      <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-xs font-semibold text-fg">Shadow Evaluation Receipt &amp; Captured Pairs</h3>
          {verdictBadge ? <SemanticBadge kind={verdictBadge.kind} labelOverride={verdictBadge.labelOverride} /> : <SemanticBadge kind="ready" labelOverride="CACHE_READY" />}
        </div>
        {shadowEval ? (
          <div className="space-y-1.5 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-fg" data-testid="shadow-match-type">{`match_type: ${shadowEval.match_type}`}</span>
              <span className="text-accent" data-testid="shadow-cost-saved-usd">{`cost_saved_usd: $${shadowEval.cost_saved_usd.toFixed(4)}`}</span>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 text-[10px]">
              <span className="text-fg" data-testid="shadow-parity-score">{`parity_score: ${shadowEval.parity_score.toFixed(2)} · sim: ${shadowEval.similarity_score.toFixed(2)}`}</span>
              <span className="text-fg-muted">{`dlp_redactions: ${shadowEval.dlp_redactions}`}</span>
            </div>
            <div className="truncate text-[10px] text-fg-muted" data-testid="shadow-scrubbed-prompt">{`prompt: ${shadowEval.scrubbed_prompt}`}</div>
            <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[10px]">
              <span className="text-fg-muted">event_sha256:</span>
              <code data-testid="shadow-event-sha256" title={shadowEval.event_sha256} className="max-w-[220px] truncate text-accent">{formatDigestPrefix(shadowEval.event_sha256)}</code>
            </div>
          </div>
        ) : (
          <div className="rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px] text-fg-muted">
            Evaluate a prompt to benchmark Frontier vs OpenCore parity, capture DLP-scrubbed preference pairs, and serve repeat/3-gram near-duplicate prompts at $0.00.
          </div>
        )}
        <ul aria-label="Captured shadow distillation pairs" className="space-y-1.5 rounded-xs border border-border bg-canvas p-2 font-mono text-[10px]">
          {shadowPairs.length > 0 ? shadowPairs.slice(0, 4).map((pair) => (
            <li key={pair.pair_id} className="space-y-0.5 border-b border-border pb-1.5 last:border-b-0 last:pb-0">
              <div className="flex flex-wrap items-center justify-between gap-1.5">
                <span className="font-semibold text-fg">{`${pair.pair_id} · ${pair.task_tag}`}</span>
                <span className="text-accent">{`parity ${pair.parity_score.toFixed(2)} · ${pair.local_model}`}</span>
              </div>
              <div className="truncate text-fg-muted">{pair.scrubbed_prompt}</div>
            </li>
          )) : <li className="text-fg-muted">No shadow pairs captured in this workspace yet.</li>}
        </ul>
      </div>
    </div>
  );
}

interface QloraDistillTabProps {
  uid: string; exportFormat: ExportFormat; targetBaseModel: string; monthlyVolume: string; minPairs: string;
  isReadOnlyRole: boolean; busyAction: string | null;
  compiledDataset: DistillationDatasetRecord | null; promotionEval: DistillationPromotionEvaluation | null;
  onChangeExportFormat: (fmt: ExportFormat) => void; onChangeTargetBaseModel: (v: string) => void;
  onChangeMonthlyVolume: (v: string) => void; onChangeMinPairs: (v: string) => void;
  onCompileDataset: () => void; onEvaluatePromotion: () => void;
}

function QloraDistillTabContent(props: QloraDistillTabProps): React.JSX.Element {
  const { uid, exportFormat, targetBaseModel, monthlyVolume, minPairs, isReadOnlyRole, busyAction, compiledDataset, promotionEval } = props;
  const promoBadge = promotionEval ? resolvePromotionVerdictBadge(promotionEval.verdict) : null;

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
        <h3 className="text-xs font-semibold text-fg">QLoRA Dataset Compiler (SFT / DPO JSONL)</h3>
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="flex flex-col gap-1 text-xs text-fg-muted sm:col-span-2">
            <label htmlFor={`${uid}-export-format`} className="font-medium text-fg">Export Format</label>
            <select id={`${uid}-export-format`} aria-label="Export Format" value={exportFormat} onChange={(e) => props.onChangeExportFormat(e.target.value as ExportFormat)} className={CTRL_CLS}>
              {EXPORT_FORMATS.map((fmt) => <option key={fmt} value={fmt}>{formatExportFormatLabel(fmt)}</option>)}
            </select>
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-target-base-model`} className="font-medium text-fg">Target Base Model</label>
            <input id={`${uid}-target-base-model`} type="text" aria-label="Target Base Model" value={targetBaseModel} onChange={(e) => props.onChangeTargetBaseModel(e.target.value)} className={CTRL_CLS} />
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-monthly-vol`} className="font-medium text-fg">Monthly Request Volume</label>
            <input id={`${uid}-monthly-vol`} type="number" min="100" step="1000" aria-label="Monthly Request Volume" value={monthlyVolume} onChange={(e) => props.onChangeMonthlyVolume(e.target.value)} className={CTRL_CLS} />
          </div>
          <div className="flex flex-col gap-1 text-xs text-fg-muted">
            <label htmlFor={`${uid}-min-pairs`} className="font-medium text-fg">Minimum Shadow Pairs</label>
            <input id={`${uid}-min-pairs`} type="number" min="1" step="1" aria-label="Minimum shadow pairs" value={minPairs} onChange={(e) => props.onChangeMinPairs(e.target.value)} className={CTRL_CLS} />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button type="button" size="sm" variant="secondary" aria-label="Compile QLoRA dataset" loading={busyAction === "compile_dataset"} disabled={isReadOnlyRole || busyAction !== null} onClick={props.onCompileDataset}>
            Compile QLoRA dataset
          </Button>
          <Button type="button" size="sm" variant="primary" aria-label="Evaluate promotion gate" loading={busyAction === "eval_promotion"} disabled={isReadOnlyRole || busyAction !== null} onClick={props.onEvaluatePromotion}>
            Evaluate promotion gate
          </Button>
        </div>

        {compiledDataset ? (
          <div className="space-y-1.5 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-fg" data-testid="distill-dataset-id">{compiledDataset.dataset_id}</span>
              <span className="text-accent" data-testid="distill-export-format">{compiledDataset.export_format}</span>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 text-[10px]">
              <span className="text-fg" data-testid="distill-record-count">{`records: ${compiledDataset.record_count} · avg_parity: ${compiledDataset.avg_parity_score.toFixed(2)}`}</span>
              <span className="text-fg-muted" data-testid="distill-lora-spec">{`LoRA r=${compiledDataset.lora_rank} / alpha=${compiledDataset.lora_alpha}`}</span>
            </div>
            <pre aria-label="Compiled QLoRA JSONL preview" className="max-h-28 overflow-auto rounded-xs border border-border bg-code p-2 text-[10px] text-fg">
              <code>{compiledDataset.jsonl_preview || "// 0 matching shadow pairs"}</code>
            </pre>
            <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[10px]">
              <span className="text-fg-muted">dataset_sha256:</span>
              <code data-testid="distill-dataset-sha256" title={compiledDataset.dataset_sha256} className="max-w-[220px] truncate text-accent">{formatDigestPrefix(compiledDataset.dataset_sha256)}</code>
            </div>
          </div>
        ) : null}
      </div>

      <div className="space-y-3 rounded-sm border border-border bg-chrome p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-xs font-semibold text-fg">OpenCore Canary Promotion Gate</h3>
          {promoBadge ? <SemanticBadge kind={promoBadge.kind} labelOverride={promoBadge.labelOverride} /> : <SemanticBadge kind="ready" labelOverride="GATE_READY" />}
        </div>
        {promotionEval ? (
          <div className="space-y-2 rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-semibold text-fg" data-testid="promo-avg-parity">{`avg_parity_score: ${promotionEval.avg_parity_score.toFixed(2)} (${promotionEval.pair_count}/${promotionEval.min_pairs} pairs)`}</span>
              <span className="font-semibold text-accent" data-testid="promo-monthly-savings">{`$${promotionEval.projected_monthly_savings_usd.toFixed(2)} / mo saved`}</span>
            </div>
            <p className="font-sans text-xs text-fg" data-testid="promo-recommendation">{promotionEval.recommendation}</p>
            <div className="flex items-center justify-between gap-2 border-t border-border pt-1.5 text-[10px]">
              <span className="text-fg-muted">gate_sha256:</span>
              <code data-testid="promo-gate-sha256" title={promotionEval.gate_sha256} className="max-w-[220px] truncate text-accent">{formatDigestPrefix(promotionEval.gate_sha256)}</code>
            </div>
          </div>
        ) : (
          <div className="rounded-xs border border-border bg-canvas p-2.5 font-mono text-[11px] text-fg-muted">
            Compile DLP-scrubbed SFT/DPO QLoRA adapters and evaluate Canary Promotion Gate readiness to cut Frontier token spend to $0.00 on OpenCore.
          </div>
        )}
      </div>
    </div>
  );
}

export function ShadowCacheAndDistillationPanel({
  workspaceId = "default", activeRbacRole = "owner",
}: ShadowCacheAndDistillationPanelProps): React.JSX.Element {
  const uid = useId();
  const isReadOnlyRole = activeRbacRole === "auditor" || activeRbacRole === "viewer" || !canRbacMutateDistill(activeRbacRole);
  const [activeTab, setActiveTab] = useState<ActiveTab>("shadow_router");
  const [taskTag, setTaskTag] = useState("code-patch");
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [frontierModel, setFrontierModel] = useState("claude-3-7-sonnet");
  const [localModel, setLocalModel] = useState("keelway-core:7b");
  const [frontierOutput, setFrontierOutput] = useState(DEFAULT_CODE_OUTPUT);
  const [localOutput, setLocalOutput] = useState(DEFAULT_CODE_OUTPUT);
  const [similarityThreshold, setSimilarityThreshold] = useState("0.82");
  const [exportFormat, setExportFormat] = useState<ExportFormat>("dpo_preference");
  const [targetBaseModel, setTargetBaseModel] = useState("keelway-core:7b");
  const [monthlyVolume, setMonthlyVolume] = useState("50000");
  const [minPairs, setMinPairs] = useState("1");
  const [cacheStats, setCacheStats] = useState<SemanticCacheStatsResponse | null>(null);
  const [shadowPairs, setShadowPairs] = useState<ShadowDistillPairRecord[]>([]);
  const [pairCount, setPairCount] = useState(0);
  const [shadowEval, setShadowEval] = useState<ShadowEvaluationRecord | null>(null);
  const [compiledDataset, setCompiledDataset] = useState<DistillationDatasetRecord | null>(null);
  const [promotionEval, setPromotionEval] = useState<DistillationPromotionEvaluation | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [errorAlert, setErrorAlert] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void fetchSemanticCacheStats(workspaceId, activeRbacRole).then((s) => { if (!cancelled) setCacheStats(s); }).catch((err) => { if (!cancelled) setErrorAlert(formatErr(err, "Failed to load semantic cache stats.")); });
    void fetchShadowPairs(workspaceId, "", 25, activeRbacRole).then((r) => { if (!cancelled) { setShadowPairs(r.pairs); setPairCount(r.count); } }).catch((err) => { if (!cancelled) setErrorAlert(formatErr(err, "Failed to load shadow evaluation pairs.")); });
    void fetchDistillationDatasets(workspaceId, 25, activeRbacRole).then((r) => { if (!cancelled && r.datasets.length > 0) setCompiledDataset((prev) => prev ?? r.datasets[0] ?? null); }).catch((err) => { if (!cancelled) setErrorAlert(formatErr(err, "Failed to load distillation datasets.")); });
    return () => { cancelled = true; };
  }, [activeRbacRole, workspaceId]);

  const formatErr = (err: unknown, fallback: string): string =>
    err instanceof PlatformDistillHttpError ? `HTTP ${err.status} · ${err.message}` : err instanceof Error ? err.message : fallback;

  const handleEvaluateShadow = async () => {
    if (isReadOnlyRole) return;
    setBusyAction("shadow_eval"); setErrorAlert(null);
    try {
      const parsedSim = Number.parseFloat(similarityThreshold);
      const rec = await evaluateShadowPrompt({
        workspace_id: workspaceId, task_tag: taskTag.trim() || "code-patch", prompt,
        frontier_model: frontierModel.trim() || "claude-3-7-sonnet", local_model: localModel.trim() || "keelway-core:7b",
        frontier_response: frontierOutput, local_response: localOutput, similarity_threshold: Number.isFinite(parsedSim) ? parsedSim : 0.82,
      }, activeRbacRole);
      setShadowEval(rec);
      const [stats, pairsRes] = await Promise.all([fetchSemanticCacheStats(workspaceId, activeRbacRole), fetchShadowPairs(workspaceId, "", 25, activeRbacRole)]);
      setCacheStats(stats); setShadowPairs(pairsRes.pairs); setPairCount(pairsRes.count);
    } catch (err) { setErrorAlert(formatErr(err, "Failed to evaluate shadow prompt.")); }
    finally { setBusyAction(null); }
  };

  const handleCompileDataset = async () => {
    if (isReadOnlyRole) return;
    setBusyAction("compile_dataset"); setErrorAlert(null);
    try {
      setCompiledDataset(await compileDistillationDataset({ workspace_id: workspaceId, task_tag: taskTag.trim(), export_format: exportFormat, target_base_model: targetBaseModel.trim() || "keelway-core:7b" }, activeRbacRole));
    } catch (err) { setErrorAlert(formatErr(err, "Failed to compile QLoRA distillation dataset.")); }
    finally { setBusyAction(null); }
  };

  const handleEvaluatePromotion = async () => {
    if (isReadOnlyRole) return;
    setBusyAction("eval_promotion"); setErrorAlert(null);
    try {
      const parsedMin = Number.parseInt(minPairs, 10);
      const parsedVol = Number.parseInt(monthlyVolume, 10);
      setPromotionEval(await evaluateDistillationPromotion({
        workspace_id: workspaceId, task_tag: taskTag.trim() || "code-patch", target_local_model: targetBaseModel.trim() || "keelway-core:7b",
        min_pairs: Number.isFinite(parsedMin) && parsedMin > 0 ? parsedMin : 1, monthly_request_volume: Number.isFinite(parsedVol) && parsedVol > 0 ? parsedVol : 50000,
      }, activeRbacRole));
    } catch (err) { setErrorAlert(formatErr(err, "Failed to evaluate OpenCore promotion gate.")); }
    finally { setBusyAction(null); }
  };

  const rawHitRate = cacheStats?.hit_rate ?? 0;
  const hitRatePct = rawHitRate <= 1 ? rawHitRate * 100 : rawHitRate;
  const shadowTabId = `${uid}-tab-shadow`;
  const distillTabId = `${uid}-tab-distill`;
  const tabPanelId = `${uid}-tabpanel`;

  return (
    <section id="shadow-cache-distillation-panel" aria-label="Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation" className="space-y-4 rounded-md border border-border-strong bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-border pb-3">
        <div className="space-y-0.5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-fg">Semantic Prompt Cache, Shadow Dual-Run &amp; QLoRA Distillation</h2>
            <SemanticBadge kind="opencore" labelOverride="SQLite WAL · 3-Gram Cache + QLoRA" />
            {isReadOnlyRole ? <span className="rounded-xs border border-border-strong bg-chrome px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">{`RBAC: ${activeRbacRole} (read-only)`}</span> : null}
          </div>
          <p className="text-xs text-fg-muted">Serve exact &amp; 3-gram semantic prompt cache hits at $0.00, capture DLP-scrubbed Frontier-vs-OpenCore shadow pairs, and compile SFT/DPO QLoRA adapters with Canary Promotion Gates.</p>
        </div>
      </div>

      {isReadOnlyRole ? <div role="status" className="rounded-xs border border-warning/45 bg-warning-subtle px-3 py-1.5 font-mono text-xs text-fg">{`Read-Only RBAC (${activeRbacRole}): Shadow prompt evaluation, QLoRA dataset compilation, and promotion gate mutations are disabled.`}</div> : null}
      {errorAlert ? <div role="alert" className="rounded-xs border border-danger/55 bg-danger-subtle px-3 py-2 font-mono text-xs text-fg"><span className="font-semibold text-danger">{errorAlert}</span></div> : null}

      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" aria-label="Semantic cache and distillation KPI summary">
        <div className="rounded-xs border border-border bg-chrome px-3 py-2 font-mono"><div className="text-[10px] text-fg-muted">Cache Hit Rate</div><div className="text-xs font-semibold text-accent" data-testid="kpi-cache-hit-rate">{`${hitRatePct.toFixed(1)}%`}</div></div>
        <div className="rounded-xs border border-border bg-chrome px-3 py-2 font-mono"><div className="text-[10px] text-fg-muted">Total USD Saved</div><div className="text-xs font-semibold text-accent" data-testid="kpi-total-usd-saved">{`$${(cacheStats?.total_cost_saved_usd ?? 0).toFixed(4)}`}</div></div>
        <div className="rounded-xs border border-border bg-chrome px-3 py-2 font-mono"><div className="text-[10px] text-fg-muted">Latency Saved</div><div className="text-xs font-semibold text-fg" data-testid="kpi-latency-saved-ms">{`${Math.round(cacheStats?.total_latency_saved_ms ?? 0)} ms`}</div></div>
        <div className="rounded-xs border border-border bg-chrome px-3 py-2 font-mono"><div className="text-[10px] text-fg-muted">Captured Shadow Pairs</div><div className="text-xs font-semibold text-fg" data-testid="kpi-captured-shadow-pairs">{pairCount}</div></div>
      </div>

      <div role="tablist" aria-label="Shadow cache and QLoRA distillation tabs" className="flex flex-wrap gap-2 border-b border-border pb-2">
        <button type="button" role="tab" id={shadowTabId} aria-selected={activeTab === "shadow_router"} aria-controls={tabPanelId} onClick={() => setActiveTab("shadow_router")} className={`rounded-sm border px-3 py-1.5 font-mono text-xs font-medium ${activeTab === "shadow_router" ? "border-accent bg-accent-subtle text-accent" : "border-border bg-chrome text-fg-muted"}`}>
          Semantic Cache &amp; Shadow Router
        </button>
        <button type="button" role="tab" id={distillTabId} aria-selected={activeTab === "qlora_distill"} aria-controls={tabPanelId} onClick={() => setActiveTab("qlora_distill")} className={`rounded-sm border px-3 py-1.5 font-mono text-xs font-medium ${activeTab === "qlora_distill" ? "border-accent bg-accent-subtle text-accent" : "border-border bg-chrome text-fg-muted"}`}>
          QLoRA Distillation &amp; Promotion Gate
        </button>
      </div>

      <div role="tabpanel" id={tabPanelId} aria-labelledby={activeTab === "shadow_router" ? shadowTabId : distillTabId}>
        {resolveActiveTabPanel(
          activeTab,
          <ShadowRouterTabContent uid={uid} taskTag={taskTag} prompt={prompt} frontierModel={frontierModel} localModel={localModel} frontierOutput={frontierOutput} localOutput={localOutput} similarityThreshold={similarityThreshold} isReadOnlyRole={isReadOnlyRole} busyAction={busyAction} shadowEval={shadowEval} shadowPairs={shadowPairs} onChangeTaskTag={setTaskTag} onChangePrompt={setPrompt} onChangeFrontierModel={setFrontierModel} onChangeLocalModel={setLocalModel} onChangeFrontierOutput={setFrontierOutput} onChangeLocalOutput={setLocalOutput} onChangeThreshold={setSimilarityThreshold} onEvaluateShadow={() => { void handleEvaluateShadow(); }} />,
          <QloraDistillTabContent uid={uid} exportFormat={exportFormat} targetBaseModel={targetBaseModel} monthlyVolume={monthlyVolume} minPairs={minPairs} isReadOnlyRole={isReadOnlyRole} busyAction={busyAction} compiledDataset={compiledDataset} promotionEval={promotionEval} onChangeExportFormat={setExportFormat} onChangeTargetBaseModel={setTargetBaseModel} onChangeMonthlyVolume={setMonthlyVolume} onChangeMinPairs={setMinPairs} onCompileDataset={() => { void handleCompileDataset(); }} onEvaluatePromotion={() => { void handleEvaluatePromotion(); }} />,
        )}
      </div>
    </section>
  );
}
