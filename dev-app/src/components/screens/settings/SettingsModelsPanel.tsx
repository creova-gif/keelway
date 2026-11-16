import React, { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import { explainRouting, fetchOpenCoreWeights } from "@/lib/api";
import type {
  OpenCoreWeightItem,
  RoutingExplainRequest,
  RoutingExplainResult,
} from "@/lib/types";

export interface SettingsModelsPanelProps {
  activeModelId: string;
  onSelectActiveModel: (modelId: string, modelLabel: string) => void;
  fetchWeightsFn?: typeof fetchOpenCoreWeights;
  explainRoutingFn?: typeof explainRouting;
}

const HOST_TOTAL_MEMORY_GB = 16;

export function SettingsModelsPanel({
  activeModelId,
  onSelectActiveModel,
  fetchWeightsFn = fetchOpenCoreWeights,
  explainRoutingFn = explainRouting,
}: SettingsModelsPanelProps): React.JSX.Element {
  const [weights, setWeights] = useState<OpenCoreWeightItem[]>([]);
  const [loadingWeights, setLoadingWeights] = useState(true);

  const [taskPreview, setTaskPreview] = useState(
    "Refactor Studio auth middleware and verify pytest suite.",
  );
  const [candidateModel, setCandidateModel] = useState("coder-7b@2.5.1");
  const [privacy, setPrivacy] = useState<RoutingExplainRequest["privacy"]>("private");
  const [candidateEndpoint, setCandidateEndpoint] = useState("http://127.0.0.1:7420");
  const [maxLatencyMs, setMaxLatencyMs] = useState(500);
  const [maxCostUsd, setMaxCostUsd] = useState(0.05);
  const [explaining, setExplaining] = useState(false);
  const [explainResult, setExplainResult] = useState<RoutingExplainResult | null>(null);

  const taskId = useId();
  const modelSelectId = useId();
  const privacyId = useId();
  const endpointId = useId();
  const latencyId = useId();
  const costId = useId();

  const mountedRef = useRef(true);
  const explainingRef = useRef(false);
  const fetchWeightsRef = useRef(fetchWeightsFn);
  fetchWeightsRef.current = fetchWeightsFn;

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;
    setLoadingWeights(true);
    fetchWeightsRef
      .current()
      .then((items) => {
        if (!cancelled) {
          setWeights(items);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) {
          setLoadingWeights(false);
        }
      });
    return () => {
      cancelled = true;
      mountedRef.current = false;
    };
  }, []);

  const loadedWeight =
    weights.find((w) => w.id === activeModelId || `${w.name} v${w.version}` === activeModelId) ??
    weights.find((w) => w.status === "loaded");
  const usedVramGb = loadedWeight ? loadedWeight.vramGb : 4.6;
  const memoryPct = Math.min(100, Math.round((usedVramGb / HOST_TOTAL_MEMORY_GB) * 100));

  const handleSelectWeight = (weight: OpenCoreWeightItem) => {
    setWeights((prev) =>
      prev.map((w) =>
        w.id === weight.id
          ? { ...w, status: "loaded" }
          : w.status === "loaded"
            ? { ...w, status: "cached" }
            : w,
      ),
    );
    onSelectActiveModel(weight.id, `${weight.name} v${weight.version}`);
  };

  const handleExplainRoute = async (event: React.FormEvent) => {
    event.preventDefault();
    if (explainingRef.current) return;
    explainingRef.current = true;
    setExplaining(true);
    try {
      const result = await explainRoutingFn({
        taskKind: taskPreview,
        model: candidateModel,
        privacy,
        maxLatencyMs,
        maxCostUsd,
        candidateEndpoint: candidateEndpoint.trim(),
        preferLocal: candidateEndpoint.includes("127.0.0.1"),
      });
      if (mountedRef.current) setExplainResult(result);
    } catch {
      // Retain previous dry-run output if explain call fails
    } finally {
      explainingRef.current = false;
      if (mountedRef.current) setExplaining(false);
    }
  };

  const renderDecisionBadge = (res: RoutingExplainResult): React.JSX.Element => {
    if (!res.allowed || res.decision === "blocked_fail_closed") {
      return <SemanticBadge kind="failed" labelOverride="Blocked · fail-closed" />;
    }
    if (res.decision === "routed_cloud") {
      return <SemanticBadge kind="frontier" labelOverride="Routed cloud" />;
    }
    return <SemanticBadge kind="opencore" labelOverride="Routed local" />;
  };

  return (
    <div className="space-y-5 text-ui text-fg">
      <header className="space-y-1 border-b border-border pb-3">
        <h2 className="text-sm font-semibold text-fg">Models &amp; 4D Hybrid Routing</h2>
        <p className="text-xs text-fg-muted">
          Local OpenCore weights on <code dir="ltr" className="unicode-bidi-isolate font-mono">127.0.0.1</code>,
          sovereign VPC boundaries, and zero-token 4D policy dry-run simulation.
        </p>
      </header>

      {/* Card 1: OpenCore Local Runtime */}
      <section
        aria-label="OpenCore local runtime"
        className="space-y-3.5 rounded-md border border-border-strong bg-surface p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-fg">
              OpenCore Local Runtime (<code dir="ltr" className="unicode-bidi-isolate font-mono">/v1/opencore/weights</code>)
            </h3>
            <p className="mt-0.5 text-xs text-fg-muted">
              Executes on local unified memory with zero external network egress.
            </p>
          </div>
          <SemanticBadge kind="opencore" detail="127.0.0.1" />
        </div>

        <div className="space-y-1.5 rounded-sm border border-border bg-canvas p-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-fg">Host Unified Memory / VRAM</span>
            <span className="font-mono tabular-nums text-fg-muted">
              {`${usedVramGb.toFixed(1)} GB / ${HOST_TOTAL_MEMORY_GB.toFixed(1)} GB (${memoryPct}%)`}
            </span>
          </div>
          <div
            role="progressbar"
            aria-label="Host unified memory utilization"
            aria-valuenow={Number(usedVramGb.toFixed(1))}
            aria-valuemin={0}
            aria-valuemax={HOST_TOTAL_MEMORY_GB}
            className="h-2 w-full overflow-hidden rounded-xs border border-border bg-chrome"
          >
            <div
              className="h-full bg-teal-accent transition-all"
              style={{ width: `${memoryPct}%` }}
            />
          </div>
        </div>

        <p className="rounded-sm border border-warning bg-warning-subtle px-3 py-2 text-xs text-fg">
          Changing the active model pauses standing Allow always rules until re-confirmed.
        </p>

        <div className="overflow-x-auto rounded-sm border border-border bg-canvas">
          <table
            aria-label="OpenCore local weights"
            className="w-full border-collapse text-start text-xs"
          >
            <thead className="border-b border-border-strong bg-chrome text-fg-muted">
              <tr>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Weight</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Quantization</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Size / VRAM</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">SHA-256 Digest</th>
                <th scope="col" className="px-3 py-2 text-start font-semibold">Status</th>
                <th scope="col" className="px-3 py-2 text-end font-semibold">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loadingWeights && weights.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-3 font-mono text-fg-muted">
                    Inspecting local OpenCore weights…
                  </td>
                </tr>
              ) : (
                weights.map((weight) => {
                  const isActive =
                    weight.id === activeModelId ||
                    `${weight.name} v${weight.version}` === activeModelId;
                  return (
                    <tr key={weight.id} className="min-h-table-row hover:bg-surface-elevated">
                      <td className="px-3 py-2">
                        <div className="font-mono font-medium text-fg">
                          <code dir="ltr" className="unicode-bidi-isolate">
                            {`${weight.name} v${weight.version}`}
                          </code>
                        </div>
                        <div className="font-mono text-[11px] text-fg-muted">
                          <code dir="ltr" className="unicode-bidi-isolate">{weight.id}</code>
                          {` · ${weight.license}`}
                        </div>
                        {weight.simulated ? (
                          <SemanticBadge kind="simulated" labelOverride="Simulated weights — not real model" />
                        ) : null}
                      </td>
                      <td className="px-3 py-2 font-mono text-fg-muted">
                        <code dir="ltr" className="unicode-bidi-isolate">{weight.quantization}</code>
                      </td>
                      <td className="px-3 py-2 font-mono tabular-nums text-fg-muted">
                        {`${weight.sizeGb.toFixed(1)} GB · ${weight.vramGb.toFixed(1)} GB VRAM`}
                      </td>
                      <td className="px-3 py-2 font-mono text-fg-muted">
                        <code dir="ltr" className="unicode-bidi-isolate">
                          {`${weight.sha256.slice(0, 19)}…`}
                        </code>
                      </td>
                      <td className="px-3 py-2">
                        {isActive ? (
                          <SemanticBadge kind="opencore" labelOverride="Active" />
                        ) : (
                          <SemanticBadge
                            kind="ready"
                            labelOverride={
                              weight.status === "loaded"
                                ? "Loaded"
                                : weight.status === "cached"
                                  ? "Cached"
                                  : "Available"
                            }
                          />
                        )}
                      </td>
                      <td className="px-3 py-2 text-end">
                        {isActive ? (
                          <span className="font-mono text-[11px] text-teal-accent">Selected</span>
                        ) : (
                          <Button
                            size="sm"
                            variant="secondary"
                            aria-label={`Set active ${weight.name}`}
                            onClick={() => handleSelectWeight(weight)}
                          >
                            {weight.status === "available" ? "Load" : "Set active"}
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Card 2: Cloud & Self-Hosted VPC Connectors */}
      <section
        aria-label="Cloud and VPC connectors"
        className="space-y-3 rounded-md border border-border-strong bg-surface p-4"
      >
        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-fg">
            Cloud &amp; Self-Hosted VPC Connectors
          </h3>
          <p className="mt-0.5 text-xs text-fg-muted">
            Explicit operator boundary labels prevent open-weight cloud APIs from masquerading as local sovereign execution.
          </p>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="space-y-2 rounded-sm border border-border-strong bg-canvas p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-semibold text-fg">
                Managed Public Cloud · Leaves this machine
              </span>
              <SemanticBadge kind="reconfirm" labelOverride="External boundary" />
            </div>
            <p className="text-xs text-fg-muted">
              Blocked automatically whenever <code dir="ltr" className="unicode-bidi-isolate font-mono">privacy=&quot;private&quot;</code>{" "}
              or Air-Gap Lock is active.
            </p>
            <div className="font-mono text-[11px] text-fg-dim">
              OS Keychain: Not configured · stays local by default
            </div>
          </div>

          <div className="space-y-2 rounded-sm border border-border-strong bg-canvas p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-semibold text-fg">Self-Hosted VPC</span>
              <SemanticBadge kind="locked" labelOverride="Sovereign VPC" />
            </div>
            <p className="text-xs text-fg-muted">
              Customer-controlled mTLS enclave (<code dir="ltr" className="unicode-bidi-isolate font-mono">sovereign_vpc</code>)
              with zero third-party prompt retention.
            </p>
            <div className="font-mono text-[11px] text-fg-dim">
              OS Keychain: Not configured · stays local by default
            </div>
          </div>
        </div>
      </section>

      {/* Card 3: Zero-Token 4D Dry-Run Simulator */}
      <section
        aria-label="4D hybrid routing dry-run simulator"
        className="space-y-4 rounded-md border border-border-strong bg-surface p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-fg">
              Zero-Token 4D Dry-Run Simulator (<code dir="ltr" className="unicode-bidi-isolate font-mono">POST /v1/routing/explain</code>)
            </h3>
            <p className="mt-0.5 text-xs text-fg-muted">
              Evaluate privacy, latency, cost, and operator data-boundary policy before sending a single prompt token.
            </p>
          </div>
          <SemanticBadge kind="live" labelOverride="$0.00 · 0 tokens" />
        </div>

        <form onSubmit={(e) => void handleExplainRoute(e)} className="space-y-3">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="md:col-span-2 space-y-1">
              <label htmlFor={taskId} className="block text-xs font-medium text-fg">
                Task / Prompt preview
              </label>
              <input
                id={taskId}
                type="text"
                value={taskPreview}
                onChange={(e) => setTaskPreview(e.target.value)}
                className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-2.5 py-1 text-xs text-fg"
              />
            </div>

            <div className="space-y-1">
              <label htmlFor={modelSelectId} className="block text-xs font-medium text-fg">
                Candidate model
              </label>
              <select
                id={modelSelectId}
                value={candidateModel}
                onChange={(e) => setCandidateModel(e.target.value)}
                className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-2 py-1 font-mono text-xs text-fg"
              >
                <option value="coder-7b@2.5.1">coder-7b@2.5.1 (OpenCore)</option>
                <option value="reasoner-14b@1.4.0">reasoner-14b@1.4.0 (OpenCore)</option>
                <option value="llama-3.3-70b">llama-3.3-70b (Open-weight)</option>
                <option value="frontier-sonnet-4">frontier-sonnet-4 (Frontier)</option>
              </select>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="space-y-1">
              <label htmlFor={privacyId} className="block text-xs font-medium text-fg">
                Privacy classification
              </label>
              <select
                id={privacyId}
                value={privacy}
                onChange={(e) => {
                  const v = e.target.value;
                  if (v === "private" || v === "standard" || v === "internal" || v === "public") {
                    setPrivacy(v);
                  }
                }}
                className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-2 py-1 text-xs text-fg"
              >
                <option value="private">private (loopback only)</option>
                <option value="standard">standard (hybrid policy-gated)</option>
                <option value="internal">internal (VPC eligible)</option>
                <option value="public">public (cloud eligible)</option>
              </select>
            </div>

            <div className="space-y-1 md:col-span-2">
              <label htmlFor={endpointId} className="block text-xs font-medium text-fg">
                Candidate endpoint
              </label>
              <input
                id={endpointId}
                type="text"
                dir="ltr"
                value={candidateEndpoint}
                onChange={(e) => setCandidateEndpoint(e.target.value)}
                className="unicode-bidi-isolate min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg"
              />
              <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                <button
                  type="button"
                  onClick={() => setCandidateEndpoint("http://127.0.0.1:7420")}
                  className="rounded-xs border border-border-control bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-fg-muted hover:text-fg"
                >
                  Preset: 127.0.0.1:7420
                </button>
                <button
                  type="button"
                  onClick={() => setCandidateEndpoint("https://api.external-vendor.example/v1")}
                  className="rounded-xs border border-border-control bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-fg-muted hover:text-fg"
                >
                  Preset: external-vendor cloud
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label htmlFor={latencyId} className="block text-xs font-medium text-fg">
                  Max latency (ms)
                </label>
                <input
                  id={latencyId}
                  type="number"
                  min={1}
                  step="any"
                  value={maxLatencyMs}
                  onChange={(e) => setMaxLatencyMs(Number(e.target.value) || 500)}
                  className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-2 py-1 font-mono text-xs tabular-nums text-fg"
                />
              </div>
              <div className="space-y-1">
                <label htmlFor={costId} className="block text-xs font-medium text-fg">
                  Max cost ($ USD)
                </label>
                <input
                  id={costId}
                  type="number"
                  min={0}
                  step={0.01}
                  value={maxCostUsd}
                  onChange={(e) => setMaxCostUsd(Number(e.target.value) || 0)}
                  className="min-h-ctrl-sm w-full rounded-xs border border-border-control bg-canvas px-2 py-1 font-mono text-xs tabular-nums text-fg"
                />
              </div>
            </div>
          </div>

          <div>
            <Button type="submit" size="md" variant="primary" loading={explaining}>
              Explain 4D route ($0.00 · 0 tokens)
            </Button>
          </div>
        </form>

        {explainResult ? (
          <div
            data-testid="routing-explain-receipt"
            role={!explainResult.allowed ? "alert" : "status"}
            className={`space-y-3 rounded-sm border p-3.5 text-xs ${
              !explainResult.allowed
                ? "border-danger bg-danger-subtle text-fg"
                : "border-border-strong bg-canvas text-fg"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                {renderDecisionBadge(explainResult)}
                <span className="font-mono tabular-nums text-fg-muted">
                  {`Est. $${explainResult.estimatedCostUsd.toFixed(3)} · ${explainResult.estimatedLatencyMs}ms`}
                </span>
              </div>
              <code dir="ltr" className="unicode-bidi-isolate rounded-xs border border-border-control bg-code px-1.5 py-0.5 font-mono text-[11px] text-fg">
                {explainResult.dataBoundary}
              </code>
            </div>

            <dl className="grid gap-2 rounded-xs border border-border bg-surface p-2.5 sm:grid-cols-3 md:grid-cols-6">
              <div>
                <dt className="text-[11px] text-fg-muted">Selected Model</dt>
                <dd className="font-mono font-semibold text-fg">
                  <code dir="ltr" className="unicode-bidi-isolate">{explainResult.selectedModel}</code>
                </dd>
              </div>
              <div>
                <dt className="text-[11px] text-fg-muted">License</dt>
                <dd className="font-mono font-semibold text-fg">
                  <code dir="ltr" className="unicode-bidi-isolate">
                    {explainResult.license ?? (explainResult.dataBoundary === "local_loopback" ? "Apache-2.0" : "Proprietary")}
                  </code>
                </dd>
              </div>
              <div>
                <dt className="text-[11px] text-fg-muted">Hosting</dt>
                <dd className="font-mono font-semibold text-fg">
                  <code dir="ltr" className="unicode-bidi-isolate">
                    {explainResult.hosting ?? (explainResult.dataBoundary === "local_loopback" ? "Local Unified Memory" : "Managed Cloud")}
                  </code>
                </dd>
              </div>
              <div>
                <dt className="text-[11px] text-fg-muted">Operator</dt>
                <dd className="font-mono font-semibold text-fg">
                  <code dir="ltr" className="unicode-bidi-isolate">{explainResult.provider}</code>
                </dd>
              </div>
              <div>
                <dt className="text-[11px] text-fg-muted">Data Boundary</dt>
                <dd className="font-mono font-semibold text-fg">
                  <code dir="ltr" className="unicode-bidi-isolate">{explainResult.dataBoundary}</code>
                </dd>
              </div>
              <div>
                <dt className="text-[11px] text-fg-muted">Privacy</dt>
                <dd className="font-mono font-semibold text-fg">
                  <code dir="ltr" className="unicode-bidi-isolate">{explainResult.privacyClassification}</code>
                </dd>
              </div>
            </dl>

            <p className="text-fg">{explainResult.rationale}</p>
            {explainResult.blockedReason ? (
              <p className="font-medium text-danger">{explainResult.blockedReason}</p>
            ) : null}

            {explainResult.evaluatedCandidates.length > 0 ? (
              <div className="overflow-x-auto rounded-xs border border-border bg-surface">
                <table aria-label="Evaluated 4D routing candidates" className="w-full border-collapse text-start text-xs">
                  <thead className="border-b border-border bg-chrome text-fg-muted">
                    <tr>
                      <th scope="col" className="px-2.5 py-1.5 text-start font-semibold">Candidate</th>
                      <th scope="col" className="px-2.5 py-1.5 text-start font-semibold">Boundary</th>
                      <th scope="col" className="px-2.5 py-1.5 text-start font-semibold">Verdict</th>
                      <th scope="col" className="px-2.5 py-1.5 text-start font-semibold">Reason</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {explainResult.evaluatedCandidates.map((cand, idx) => (
                      <tr key={`${cand.model}-${idx}`}>
                        <td className="px-2.5 py-1.5 font-mono text-fg">
                          <code dir="ltr" className="unicode-bidi-isolate">{cand.model}</code>
                        </td>
                        <td className="px-2.5 py-1.5 font-mono text-fg-muted">
                          <code dir="ltr" className="unicode-bidi-isolate">{cand.boundary}</code>
                        </td>
                        <td className="px-2.5 py-1.5">
                          {cand.passed ? (
                            <SemanticBadge kind="passed" labelOverride="Eligible" />
                          ) : (
                            <SemanticBadge kind="failed" labelOverride="Rejected" />
                          )}
                        </td>
                        <td className="px-2.5 py-1.5 text-fg-muted">{cand.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
