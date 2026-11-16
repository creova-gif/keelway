"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import * as Tabs from "@radix-ui/react-tabs";
import {
  Check,
  Copy,
  Cpu,
  FilterX,
  Globe2,
  HardDrive,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
  X,
} from "lucide-react";
import {
  CATALOG_MODELS,
  LORA_ADAPTERS,
  type CatalogModel,
} from "@/data/models";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

type CategoryFilter = "all" | "opencore" | "ecosystem_open" | "frontier";
type QuantizationMode = "Q4_K_M" | "Q8_0" | "FP16";

interface HardwareProfile {
  id: string;
  label: string;
  vramGb: number;
  note: string;
}

const HARDWARE_PROFILES: HardwareProfile[] = [
  {
    id: "edge8",
    label: "8 GB Edge / Air",
    vramGb: 6.2,
    note: "~6.2 GB usable unified/VRAM budget",
  },
  {
    id: "pro16",
    label: "16 GB Pro Laptop",
    vramGb: 12.5,
    note: "~12.5 GB usable unified/VRAM budget",
  },
  {
    id: "studio32",
    label: "32 GB Studio / 4090",
    vramGb: 26.0,
    note: "~26 GB usable unified/VRAM budget",
  },
  {
    id: "cluster80",
    label: "80 GB vLLM A100/H100",
    vramGb: 76.0,
    note: "Dedicated VPC GPU tensor-parallel node",
  },
];

const QUANT_MULTIPLIER: Record<QuantizationMode, number> = {
  Q4_K_M: 1.0,
  Q8_0: 1.65,
  FP16: 2.85,
};

const CAPABILITY_FILTERS = [
  { id: "tools", label: "Tool Calling" },
  { id: "reasoning", label: "Reasoning" },
  { id: "code", label: "Code Synthesis" },
  { id: "structured_output", label: "Structured JSON" },
  { id: "multilingual", label: "Multilingual" },
  { id: "vision", label: "Vision" },
];

function formatContext(tokens: number): string {
  if (tokens >= 1000000) return `${(tokens / 1000000).toFixed(0)}M`;
  return `${Math.round(tokens / 1024)}K`;
}

function estimateVramGb(
  model: CatalogModel,
  quant: QuantizationMode
): number | null {
  if (model.recommendedVramGb === null) return null;
  return Number((model.recommendedVramGb * QUANT_MULTIPLIER[quant]).toFixed(1));
}

/**
 * Compiles a deterministic Ollama-compatible Modelfile matching
 * `OpenCoreModelfileCompiler` in `core/opencore/runtime.py`.
 */
function compileModelfilePreview(
  model: CatalogModel,
  quant: QuantizationMode,
  ctxTokens: number,
  adapterId: string
): string {
  const adapter = LORA_ADAPTERS.find((a) => a.id === adapterId);
  const lines = [
    `# Keelway OpenCore Deterministic Modelfile`,
    `# Model: ${model.id} · Quantization: ${quant} · License: ${model.license}`,
    `# Weight SHA-256: ${model.manifestSha256 ?? "verified-local-manifest"}`,
    `FROM ${model.baseCheckpoint ?? model.id}`,
    ``,
    `PARAMETER temperature ${model.defaultTemp ?? 0.4}`,
    `PARAMETER top_p 0.9`,
    `PARAMETER num_ctx ${ctxTokens}`,
    `PARAMETER stop "<|im_end|>"`,
    `PARAMETER stop "<|endoftext|>"`,
  ];

  if (adapter) {
    lines.push(
      ``,
      `# Hot-Attached Sovereign QLoRA Adapter (SHA-256: ${adapter.sha256})`,
      `ADAPTER ~/.keelway/adapters/${adapter.id}.gguf`
    );
  }

  if (model.systemPrompt) {
    lines.push(``, `SYSTEM """${model.systemPrompt}"""`);
  }

  return lines.join("\n");
}

function ModelQuerySync({ onQuery }: { onQuery: (q: string) => void }) {
  const searchParams = useSearchParams();
  const urlQuery = searchParams.get("q");
  useEffect(() => {
    if (urlQuery !== null) {
      onQuery(urlQuery);
    }
  }, [urlQuery, onQuery]);
  return null;
}

export function ModelExplorer() {
  const [query, setQuery] = useState("");
  const [categoryTab, setCategoryTab] = useState<CategoryFilter>("all");
  const [selectedCaps, setSelectedCaps] = useState<string[]>([]);
  const [apacheOnly, setApacheOnly] = useState(false);
  const [hardwareId, setHardwareId] = useState<string>("pro16");
  const [quant, setQuant] = useState<QuantizationMode>("Q4_K_M");

  // Modal Inspector State
  const [inspectedModel, setInspectedModel] = useState<CatalogModel | null>(
    null
  );
  const [selectedAdapterId, setSelectedAdapterId] = useState<string>("none");
  const [modalCtx, setModalCtx] = useState<number>(65536);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const activeHardware =
    HARDWARE_PROFILES.find((h) => h.id === hardwareId) ?? HARDWARE_PROFILES[1];

  const toggleCapability = (cap: string) => {
    setSelectedCaps((prev) => {
      const next = prev.includes(cap)
        ? prev.filter((c) => c !== cap)
        : [...prev, cap];
      trackEvent("model_filter_changed", { capability: cap });
      return next;
    });
  };

  const resetFilters = () => {
    setQuery("");
    setCategoryTab("all");
    setSelectedCaps([]);
    setApacheOnly(false);
  };

  const filteredModels = useMemo(() => {
    const q = query.trim().toLowerCase();
    return CATALOG_MODELS.filter((m) => {
      if (categoryTab === "opencore" && !m.isOpenCoreSuite) return false;
      if (
        categoryTab === "ecosystem_open" &&
        (m.category !== "open_weight" || m.isOpenCoreSuite)
      ) {
        return false;
      }
      if (categoryTab === "frontier" && m.category !== "closed_proprietary") {
        return false;
      }
      if (apacheOnly && !m.licensePermissive) return false;
      if (
        selectedCaps.length > 0 &&
        !selectedCaps.every((cap) => m.capabilities.includes(cap))
      ) {
        return false;
      }
      if (q) {
        const haystack = `${m.id} ${m.name} ${m.family} ${m.license} ${m.description} ${m.capabilities.join(" ")}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [query, categoryTab, selectedCaps, apacheOnly]);

  const handleOpenInspector = (model: CatalogModel) => {
    setInspectedModel(model);
    setModalCtx(Math.min(model.contextWindow, 65536));
    const matchingLora = LORA_ADAPTERS.find((a) => a.targetModel === model.id);
    setSelectedAdapterId(matchingLora ? matchingLora.id : "none");
    trackEvent("model_inspector_opened", { model_id: model.id });
  };

  const copyText = async (key: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedKey(key);
      trackEvent("code_snippet_copied", { tab: key });
      window.setTimeout(() => setCopiedKey(null), 1800);
    } catch {
      // Ignore clipboard errors
    }
  };

  return (
    <div className="space-y-10">
      <Suspense fallback={null}>
        <ModelQuerySync onQuery={setQuery} />
      </Suspense>
      {/* ====================================================================
          1. INTERACTIVE HARDWARE & VRAM FIT INSTRUMENT
          ==================================================================== */}
      <section
        aria-labelledby="vram-calc-heading"
        className="frame-crosshair rounded-lg border border-border-strong bg-surface p-5 sm:p-6"
      >
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
          <div>
            <div className="flex items-center gap-2">
              <HardDrive
                className="h-4 w-4 text-teal-accent"
                aria-hidden="true"
              />
              <h2
                id="vram-calc-heading"
                className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent"
              >
                LIVE HARDWARE &amp; UNIFIED MEMORY FIT CALCULATOR
              </h2>
            </div>
            <p className="mt-1 text-sm text-fg-muted">
              Select your target machine and weight precision to inspect real-time
              VRAM fit across every open-weight model below.
            </p>
          </div>

          {/* Quantization Switcher */}
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-fg-muted">Precision:</span>
            <div
              role="group"
              aria-label="Weight quantization level"
              className="inline-flex rounded-sm border border-border-strong bg-canvas p-0.5"
            >
              {(["Q4_K_M", "Q8_0", "FP16"] as QuantizationMode[]).map((qMode) => (
                <button
                  key={qMode}
                  type="button"
                  onClick={() => setQuant(qMode)}
                  className={cn(
                    "min-h-[38px] rounded-sm px-3 font-mono text-xs font-semibold transition-colors duration-150",
                    quant === qMode
                      ? "bg-teal-accent text-teal-ink"
                      : "text-fg-muted hover:text-fg"
                  )}
                >
                  {qMode}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div
          role="radiogroup"
          aria-label="Hardware memory profile"
          className="mt-4 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4"
        >
          {HARDWARE_PROFILES.map((hw) => {
            const active = hw.id === hardwareId;
            return (
              <button
                key={hw.id}
                type="button"
                role="radio"
                aria-checked={active}
                onClick={() => {
                  setHardwareId(hw.id);
                  trackEvent("model_hardware_profile_changed", {
                    profile: hw.id,
                  });
                }}
                className={cn(
                  "flex min-h-[60px] flex-col justify-center rounded-md border px-3.5 py-2.5 text-left transition-all duration-150",
                  active
                    ? "border-teal-accent bg-surface-elevated"
                    : "border-border-subtle bg-canvas hover:border-border-strong"
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs font-bold text-fg">
                    {hw.label}
                  </span>
                  {active && (
                    <span className="chip-teal rounded-sm px-1.5 py-0.5 text-[10px]">
                      ACTIVE
                    </span>
                  )}
                </div>
                <span className="mt-1 text-[11px] text-fg-muted">{hw.note}</span>
              </button>
            );
          })}
        </div>
      </section>

      {/* ====================================================================
          2. SEARCH, CATEGORY TABS & CAPABILITY FILTERS
          ==================================================================== */}
      <section aria-label="Catalog search and filters" className="space-y-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
          {/* Search Input */}
          <div className="relative lg:col-span-5">
            <label htmlFor="model-search" className="sr-only">
              Search models by ID, family, capability, or license
            </label>
            <Search
              className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-dim"
              aria-hidden="true"
            />
            <input
              id="model-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search keelway-core, qwen, gemini, Apache-2.0…"
              className="min-h-[44px] w-full rounded-md border border-border-strong bg-surface pl-10 pr-4 text-sm text-fg placeholder:text-fg-dim focus:border-teal-accent"
            />
          </div>

          {/* Category Filter Tabs */}
          <div className="lg:col-span-7">
            <Tabs.Root
              value={categoryTab}
              onValueChange={(v) => setCategoryTab(v as CategoryFilter)}
            >
              <Tabs.List
                aria-label="Model categories"
                className="grid grid-cols-2 gap-1.5 rounded-md border border-border-strong bg-surface p-1 sm:grid-cols-4"
              >
                <Tabs.Trigger
                  value="all"
                  className={cn(
                    "min-h-[38px] rounded-sm px-2.5 font-mono text-xs font-semibold transition-colors duration-150",
                    categoryTab === "all"
                      ? "bg-teal-accent text-teal-ink"
                      : "text-fg-muted hover:text-fg"
                  )}
                >
                  All (15)
                </Tabs.Trigger>
                <Tabs.Trigger
                  value="opencore"
                  className={cn(
                    "min-h-[38px] rounded-sm px-2.5 font-mono text-xs font-semibold transition-colors duration-150",
                    categoryTab === "opencore"
                      ? "bg-teal-accent text-teal-ink"
                      : "text-fg-muted hover:text-fg"
                  )}
                >
                  OpenCore (4)
                </Tabs.Trigger>
                <Tabs.Trigger
                  value="ecosystem_open"
                  className={cn(
                    "min-h-[38px] rounded-sm px-2.5 font-mono text-xs font-semibold transition-colors duration-150",
                    categoryTab === "ecosystem_open"
                      ? "bg-teal-accent text-teal-ink"
                      : "text-fg-muted hover:text-fg"
                  )}
                >
                  Open Ecosystem (5)
                </Tabs.Trigger>
                <Tabs.Trigger
                  value="frontier"
                  className={cn(
                    "min-h-[38px] rounded-sm px-2.5 font-mono text-xs font-semibold transition-colors duration-150",
                    categoryTab === "frontier"
                      ? "bg-amber-alert text-amber-ink"
                      : "text-fg-muted hover:text-fg"
                  )}
                >
                  Frontier APIs (6)
                </Tabs.Trigger>
              </Tabs.List>
            </Tabs.Root>
          </div>
        </div>

        {/* Capability & License Pill Row */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {CAPABILITY_FILTERS.map((cap) => {
              const active = selectedCaps.includes(cap.id);
              return (
                <button
                  key={cap.id}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleCapability(cap.id)}
                  className={cn(
                    "min-h-[40px] rounded-sm border px-3 font-mono text-xs font-medium transition-colors duration-150",
                    active
                      ? "border-teal-accent bg-teal-surface text-teal-accent"
                      : "border-border-strong bg-surface text-fg-muted hover:text-fg"
                  )}
                >
                  {cap.label}
                </button>
              );
            })}

            <button
              type="button"
              aria-pressed={apacheOnly}
              onClick={() => setApacheOnly((v) => !v)}
              className={cn(
                "min-h-[40px] rounded-sm border px-3 font-mono text-xs font-semibold transition-colors duration-150",
                apacheOnly
                  ? "border-teal-accent bg-teal-accent text-teal-ink"
                  : "border-border-strong bg-surface text-fg-muted hover:text-fg"
              )}
            >
              Apache-2.0 / MIT Only
            </button>
          </div>

          <div
            aria-live="polite"
            className="font-mono text-xs text-fg-muted"
          >
            Showing <strong className="text-fg">{filteredModels.length}</strong>{" "}
            of {CATALOG_MODELS.length} registered models
          </div>
        </div>
      </section>

      {/* ====================================================================
          3. MODEL CARDS GRID (OR ACCESSIBLE EMPTY STATE)
          ==================================================================== */}
      {filteredModels.length === 0 ? (
        <div className="rounded-lg border border-border-strong bg-surface p-12 text-center">
          <FilterX
            className="mx-auto h-8 w-8 text-fg-muted"
            aria-hidden="true"
          />
          <h3 className="mt-3 text-lg font-bold text-fg">
            No models match the active filter combination
          </h3>
          <p className="mx-auto mt-1 max-w-md text-sm text-fg-muted">
            Try clearing a capability constraint or switching from Apache-2.0
            only to inspect commercial Frontier providers as well.
          </p>
          <button
            type="button"
            onClick={resetFilters}
            className="kw-btn kw-btn-primary mt-5"
          >
            Reset All Filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {filteredModels.map((model) => {
            const estVram = estimateVramGb(model, quant);
            const fitsHardware =
              estVram !== null ? estVram <= activeHardware.vramGb : null;
            const vramPct =
              estVram !== null
                ? Math.min(100, Math.round((estVram / activeHardware.vramGb) * 100))
                : 0;

            return (
              <article
                key={model.id}
                className={cn(
                  "flex flex-col justify-between rounded-lg border bg-surface p-5 transition-colors duration-150",
                  model.isOpenCoreSuite
                    ? "border-teal-accent/60 hover:border-teal-accent"
                    : "border-border-strong hover:border-teal-accent/50"
                )}
              >
                <div>
                  {/* Top Category & License Badges */}
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    {model.isOpenCoreSuite ? (
                      <span className="chip-teal rounded-sm px-2 py-0.5">
                        KEELWAY OPENCORE
                      </span>
                    ) : model.category === "open_weight" ? (
                      <span className="chip-neutral rounded-sm px-2 py-0.5 text-teal-accent">
                        OPEN-WEIGHT
                      </span>
                    ) : (
                      <span className="chip-amber rounded-sm px-2 py-0.5">
                        FRONTIER CLOUD
                      </span>
                    )}

                    <span className="font-mono text-[11px] text-fg-muted">
                      {model.licensePermissive ? model.license : model.providerLabel}
                    </span>
                  </div>

                  {/* Model Title & Canonical ID */}
                  <h3 className="mt-3 text-lg font-bold text-fg">
                    {model.name}
                  </h3>
                  <code className="mt-0.5 inline-block font-mono text-xs text-teal-accent">
                    {model.id}
                  </code>

                  <p className="mt-2.5 text-xs leading-relaxed text-fg-muted">
                    {model.description}
                  </p>

                  {/* Telemetry Metrics Row */}
                  <dl className="mt-4 grid grid-cols-3 gap-2 rounded-md border border-border-subtle bg-canvas p-2.5 font-mono text-[11px]">
                    <div>
                      <dt className="text-[10px] uppercase text-fg-dim">
                        Context
                      </dt>
                      <dd className="mt-0.5 font-semibold tabular-nums text-fg">
                        {formatContext(model.contextWindow)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[10px] uppercase text-fg-dim">
                        Input/1M
                      </dt>
                      <dd className="mt-0.5 font-semibold tabular-nums text-fg">
                        {model.pricingInputPerMtok === 0
                          ? "$0.00"
                          : `$${model.pricingInputPerMtok.toFixed(2)}`}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-[10px] uppercase text-fg-dim">
                        Output/1M
                      </dt>
                      <dd className="mt-0.5 font-semibold tabular-nums text-fg">
                        {model.pricingOutputPerMtok === 0
                          ? "$0.00"
                          : `$${model.pricingOutputPerMtok.toFixed(2)}`}
                      </dd>
                    </div>
                  </dl>

                  {/* Live VRAM Gauge (Open-Weight) or Cloud Boundary Indicator */}
                  {estVram !== null ? (
                    <div className="mt-3.5 rounded-md border border-border-subtle bg-canvas/70 p-2.5 font-mono text-[11px]">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-fg-muted">
                          {quant} Est: <strong className="text-fg">{estVram} GB</strong>
                        </span>
                        <span
                          className={cn(
                            "font-semibold",
                            fitsHardware ? "text-teal-accent" : "text-amber-alert"
                          )}
                        >
                          {fitsHardware ? "FITS MEMORY ✓" : "NEEDS BIGGER GPU"}
                        </span>
                      </div>
                      <div
                        className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-elevated"
                        aria-hidden="true"
                      >
                        <div
                          className={cn(
                            "h-full transition-all duration-150",
                            fitsHardware ? "bg-teal-accent" : "bg-amber-alert"
                          )}
                          style={{ width: `${vramPct}%` }}
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3.5 flex items-center justify-between rounded-md border border-border-subtle bg-canvas/70 p-2.5 font-mono text-[11px] text-fg-muted">
                      <span>Hosted Commercial Inference</span>
                      <span className="text-amber-alert">0 GB Local VRAM</span>
                    </div>
                  )}

                  {/* Capability Tags */}
                  <div className="mt-3.5 flex flex-wrap gap-1.5">
                    {model.capabilities.slice(0, 5).map((cap) => (
                      <span
                        key={cap}
                        className="rounded-sm border border-border-subtle bg-canvas px-2 py-0.5 font-mono text-[10px] text-fg-muted"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Action Button */}
                <div className="mt-5 border-t border-border-subtle pt-4">
                  <button
                    type="button"
                    onClick={() => handleOpenInspector(model)}
                    className="kw-btn kw-btn-secondary w-full font-mono text-xs"
                  >
                    {model.category === "open_weight" ? (
                      <>
                        <Cpu
                          className="h-3.5 w-3.5 text-teal-accent"
                          aria-hidden="true"
                        />
                        <span>Compile Modelfile &amp; Pull</span>
                      </>
                    ) : (
                      <>
                        <Sparkles
                          className="h-3.5 w-3.5 text-amber-alert"
                          aria-hidden="true"
                        />
                        <span>Inspect Unified SDK Route</span>
                      </>
                    )}
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* ====================================================================
          4. SOVEREIGN AFRICAN & DOMAIN QLORA ADAPTER REGISTRY
          ==================================================================== */}
      <section
        aria-labelledby="lora-heading"
        className="border-t border-border-subtle pt-14"
      >
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              HOT-SWAPPABLE PEFT / GGUF ADAPTERS
            </p>
            <h2
              id="lora-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg"
            >
              Cryptographically Verified QLoRA Registry — Built for Global &amp;
              African Markets
            </h2>
          </div>
          <p className="max-w-md text-xs leading-relaxed text-fg-muted">
            Every LoRA checkpoint in{" "}
            <code className="font-mono text-fg">LoRAAdapterRegistry</code> is
            SHA-256 verified on disk before hot-attachment, preventing tampered
            adapter injection.
          </p>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-3">
          {LORA_ADAPTERS.map((adapter) => (
            <article
              key={adapter.id}
              className="rounded-lg border border-border-strong bg-surface p-5"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="chip-teal inline-flex items-center gap-1 rounded-sm px-2 py-0.5">
                  <Globe2 className="h-3 w-3" aria-hidden="true" />
                  r={adapter.rank} · α={adapter.alpha}
                </span>
                <span className="font-mono text-xs text-fg-muted">
                  {adapter.sizeMb} MB
                </span>
              </div>

              <h3 className="mt-3 text-base font-bold text-fg">
                {adapter.name}
              </h3>
              <code className="mt-0.5 block font-mono text-xs text-teal-accent">
                {adapter.id} → {adapter.targetModel}
              </code>

              <p className="mt-2.5 text-xs leading-relaxed text-fg-muted">
                {adapter.summary}
              </p>

              <div className="mt-4 flex flex-wrap gap-1.5">
                {adapter.languages.map((lang) => (
                  <span
                    key={lang}
                    className="rounded-sm border border-border-strong bg-canvas px-2 py-0.5 font-mono text-[10px] text-fg"
                  >
                    {lang}
                  </span>
                ))}
              </div>

              <div className="mt-4 flex items-center gap-1.5 border-t border-border-subtle pt-3 font-mono text-[11px] text-fg-dim">
                <ShieldCheck
                  className="h-3.5 w-3.5 shrink-0 text-teal-accent"
                  aria-hidden="true"
                />
                <span className="truncate">sha256:{adapter.sha256}</span>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* ====================================================================
          5. RADIX ACCESSIBLE MODELFILE COMPILER & SDK INSPECTOR MODAL
          ==================================================================== */}
      <Dialog.Root
        open={inspectedModel !== null}
        onOpenChange={(open) => {
          if (!open) setInspectedModel(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm" />
          <Dialog.Content className="fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[94vw] max-w-2xl -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border border-border-strong bg-surface p-6 shadow-2xl focus:outline-none">
            {inspectedModel && (
              <div>
                <div className="flex items-start justify-between gap-4 border-b border-border-subtle pb-4">
                  <div>
                    <span
                      className={cn(
                        "inline-block rounded-sm px-2 py-0.5",
                        inspectedModel.category === "open_weight"
                          ? "chip-teal"
                          : "chip-amber"
                      )}
                    >
                      {inspectedModel.category === "open_weight"
                        ? "OPEN-WEIGHT MODFILE COMPILER"
                        : "GOVERNED CLOUD ROUTE"}
                    </span>
                    <Dialog.Title className="mt-2 text-xl font-bold text-fg">
                      {inspectedModel.name}
                    </Dialog.Title>
                    <Dialog.Description className="font-mono text-xs text-fg-muted">
                      {inspectedModel.id} · License: {inspectedModel.license}
                    </Dialog.Description>
                  </div>

                  <Dialog.Close
                    aria-label="Close model inspector"
                    className="inline-flex h-11 w-11 items-center justify-center rounded-sm border border-border-strong bg-canvas text-fg-muted hover:border-teal-accent hover:text-fg"
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </Dialog.Close>
                </div>

                {inspectedModel.category === "open_weight" ? (
                  <div className="mt-5 space-y-4">
                    {/* Interactive Compiler Controls */}
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                      <div>
                        <label
                          htmlFor="modal-lora-select"
                          className="block font-mono text-xs font-semibold text-fg"
                        >
                          Hot-Attach QLoRA Adapter
                        </label>
                        <select
                          id="modal-lora-select"
                          value={selectedAdapterId}
                          onChange={(e) => {
                            setSelectedAdapterId(e.target.value);
                            trackEvent("lora_adapter_toggled", {
                              adapter: e.target.value,
                            });
                          }}
                          className="mt-1 min-h-[44px] w-full rounded-md border border-border-strong bg-canvas px-3 font-mono text-xs text-fg"
                        >
                          <option value="none">None (Base Checkpoint)</option>
                          {LORA_ADAPTERS.map((a) => (
                            <option key={a.id} value={a.id}>
                              {a.id} ({a.languages.slice(0, 3).join("/")})
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label
                          htmlFor="modal-ctx-select"
                          className="block font-mono text-xs font-semibold text-fg"
                        >
                          Context Window (num_ctx)
                        </label>
                        <select
                          id="modal-ctx-select"
                          value={modalCtx}
                          onChange={(e) => setModalCtx(Number(e.target.value))}
                          className="mt-1 min-h-[44px] w-full rounded-md border border-border-strong bg-canvas px-3 font-mono text-xs text-fg"
                        >
                          <option value={16384}>16,384 tokens</option>
                          <option value={32768}>32,768 tokens</option>
                          {inspectedModel.contextWindow >= 65536 && (
                            <option value={65536}>65,536 tokens</option>
                          )}
                          {inspectedModel.contextWindow >= 128000 && (
                            <option value={131072}>131,072 tokens</option>
                          )}
                        </select>
                      </div>
                    </div>

                    {/* Compiled Modelfile Output */}
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-semibold text-fg">
                          Compiled Ollama Modelfile ({quant})
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            copyText(
                              "modelfile",
                              compileModelfilePreview(
                                inspectedModel,
                                quant,
                                modalCtx,
                                selectedAdapterId
                              )
                            )
                          }
                          className="inline-flex min-h-[38px] items-center gap-1.5 rounded-sm border border-border-strong bg-canvas px-2.5 font-mono text-xs text-fg hover:border-teal-accent"
                        >
                          {copiedKey === "modelfile" ? (
                            <>
                              <Check
                                className="h-3.5 w-3.5 text-teal-accent"
                                aria-hidden="true"
                              />
                              <span>Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                              <span>Copy Modelfile</span>
                            </>
                          )}
                        </button>
                      </div>
                      <pre className="mt-2 overflow-x-auto rounded-md border border-border-strong bg-canvas p-3.5 font-mono text-xs leading-relaxed text-fg">
                        {compileModelfilePreview(
                          inspectedModel,
                          quant,
                          modalCtx,
                          selectedAdapterId
                        )}
                      </pre>
                    </div>

                    {/* CLI Registration Command */}
                    <div>
                      <div className="flex items-center justify-between">
                        <span className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold text-fg">
                          <Terminal
                            className="h-3.5 w-3.5 text-teal-accent"
                            aria-hidden="true"
                          />
                          Register &amp; Run via Keelway CLI
                        </span>
                      </div>
                      <pre className="mt-2 overflow-x-auto rounded-md border border-border-strong bg-canvas p-3.5 font-mono text-xs leading-relaxed text-teal-accent">
                        {`python3 cli.py opencore --modelfile ${inspectedModel.id} > Modelfile
ollama create '${inspectedModel.id}' -f './Modelfile'
python3 cli.py route --model '${inspectedModel.id}' --privacy private`}
                      </pre>
                    </div>
                  </div>
                ) : (
                  <div className="mt-5 space-y-4">
                    <div className="rounded-md border border-amber-alert/40 bg-amber-surface p-3.5 text-xs text-fg">
                      <strong>Commercial API Governance:</strong> Requests to{" "}
                      <code>{inspectedModel.id}</code> require explicit tenant
                      opt-in (<code>allowed_providers</code>), redact secrets
                      before egress, and transmit API credentials exclusively in
                      HTTP headers (never URL query parameters).
                    </div>

                    <div>
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-semibold text-fg">
                          Keelway Python SDK v1 (with Automatic Local Fallback)
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            copyText(
                              "frontier-sdk",
                              `from core.sdk import KeelwayClient\n\nclient = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_team")\nres = client.responses.create(\n    model="${inspectedModel.id}",\n    input="Synthesize architecture trade-offs across 12 worker reports.",\n    fallback_model="keelway-core:7b",\n)\nprint(res.output_text, res.usage)`
                            )
                          }
                          className="inline-flex min-h-[38px] items-center gap-1.5 rounded-sm border border-border-strong bg-canvas px-2.5 font-mono text-xs text-fg hover:border-teal-accent"
                        >
                          {copiedKey === "frontier-sdk" ? (
                            <>
                              <Check
                                className="h-3.5 w-3.5 text-teal-accent"
                                aria-hidden="true"
                              />
                              <span>Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                              <span>Copy Snippet</span>
                            </>
                          )}
                        </button>
                      </div>
                      <pre className="mt-2 overflow-x-auto rounded-md border border-border-strong bg-canvas p-4 font-mono text-xs leading-relaxed text-fg">
                        {`from core.sdk import KeelwayClient

client = KeelwayClient(base_url="http://127.0.0.1:8000", api_key="kw_live_team")
res = client.responses.create(
    model="${inspectedModel.id}",
    input="Synthesize architecture trade-offs across 12 worker reports.",
    fallback_model="keelway-core:7b",
)
print(res.output_text, res.usage)`}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            )}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
