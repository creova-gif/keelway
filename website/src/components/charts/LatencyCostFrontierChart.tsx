"use client";

import React, { useMemo, useState } from "react";
import { Activity, Table2, TrendingUp } from "lucide-react";
import { EMPIRICAL_BENCHMARKS, type BenchmarkPoint } from "@/data/benchmarks";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

type ChartMode = "latency_cost" | "quality_speed";

/**
 * Maps blended cost ($0.00 -> $6.00+) onto a readable pseudo-log X axis [0..1]
 * so $0.00 local OpenCore checkpoints and $0.16-$6.00 Frontier endpoints
 * separate cleanly without overlapping.
 */
function costToRatio(usd: number): number {
  if (usd <= 0) return 0.04;
  // log10(1 + usd * 20) / log10(1 + 7 * 20)
  return Math.min(0.96, 0.14 + (Math.log10(1 + usd * 22) / Math.log10(155)) * 0.82);
}

/**
 * Together AI / Artificial Analysis style Empirical Scatter Plot.
 * Visualizes measured Warm TTFT (ms) vs. Blended Cost ($/1M) and
 * Quality Index vs. Throughput (tok/s) with keyboard-accessible SVG points
 * and a toggleable WCAG data table.
 */
export function LatencyCostFrontierChart({
  compact = false,
}: {
  compact?: boolean;
}) {
  const [mode, setMode] = useState<ChartMode>("latency_cost");
  const [selectedId, setSelectedId] = useState<string>("keelway-core:7b");
  const [showTable, setShowTable] = useState<boolean>(false);

  const selected =
    EMPIRICAL_BENCHMARKS.find((b) => b.id === selectedId) ??
    EMPIRICAL_BENCHMARKS[1];

  // SVG Coordinate System: 760 x 380
  const W = 760;
  const H = 380;
  const PAD = { top: 28, right: 34, bottom: 48, left: 66 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;

  const plotted = useMemo(() => {
    return EMPIRICAL_BENCHMARKS.map((pt) => {
      if (mode === "latency_cost") {
        const rx = costToRatio(pt.blendedUsdPerMtok);
        // Y: TTFT 50ms (bottom=fast) -> 1050ms (top=slower) or invert so lower latency is higher/better?
        // Standard engineering convention (Artificial Analysis): X = Cost ($/1M, cheaper left), Y = TTFT (ms, lower = faster at bottom) OR Quality (higher = top).
        // Let's plot X = TTFT Latency (100ms -> 1050ms, faster on left) and Y = Quality Index (65 -> 100, higher on top) OR X = Cost ($/1M) and Y = TTFT (ms, 100ms top = fastest -> 1050ms bottom)!
        // Putting 100ms (Fastest) at TOP and $0.00 (Free) at LEFT makes TOP-LEFT the unmistakable Pareto Sweet Spot!
        const ry = (pt.ttftMs - 80) / (1050 - 80); // 0 near top (80ms), 1 near bottom (1050ms)
        return {
          pt,
          cx: PAD.left + rx * plotW,
          cy: PAD.top + Math.max(0.04, Math.min(0.95, ry)) * plotH,
        };
      } else {
        // Mode 2: X = Throughput (20 -> 160 tok/s, faster right), Y = Quality Index (65 -> 100, higher top)
        const rx = (pt.throughputTokPerSec - 20) / (160 - 20);
        const ry = 1 - (pt.qualityIndex - 64) / (100 - 64);
        return {
          pt,
          cx: PAD.left + Math.max(0.05, Math.min(0.95, rx)) * plotW,
          cy: PAD.top + Math.max(0.05, Math.min(0.95, ry)) * plotH,
        };
      }
    });
  }, [mode, plotW, plotH, PAD.left, PAD.top]);

  const paretoPolyline = useMemo(() => {
    const paretoPts = plotted
      .filter((p) => p.pt.isParetoOptimal)
      .sort((a, b) => a.cx - b.cx);
    return paretoPts.map((p) => `${p.cx.toFixed(1)},${p.cy.toFixed(1)}`).join(" ");
  }, [plotted]);

  const selectedCoord =
    plotted.find((p) => p.pt.id === selected.id) ?? plotted[1];

  return (
    <div className="frame-crosshair rounded-lg border border-border-strong bg-surface p-5 sm:p-6">
      {/* Header & Mode Switcher */}
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div>
          <div className="flex items-center gap-2">
            <Activity
              className="h-4 w-4 text-teal-accent"
              aria-hidden="true"
            />
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              EMPIRICAL LATENCY, COST &amp; QUALITY FRONTIER
            </span>
          </div>
          <h3 className="mt-1 text-xl font-bold text-fg">
            {mode === "latency_cost"
              ? "Measured Warm TTFT (ms) vs. Blended Cost ($ / 1M Tokens)"
              : "Composite Coding & Reasoning Quality vs. Decode Speed (tok/s)"}
          </h3>
          {!compact && (
            <p className="mt-1 text-xs text-fg-muted">
              Benchmarked across local Apple Silicon Metal / vLLM OpenCore
              checkpoints and live Google Gemini, OpenAI, and Anthropic endpoints.
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div
            role="group"
            aria-label="Benchmark chart axes"
            className="inline-flex rounded-sm border border-border-strong bg-canvas p-1"
          >
            <button
              type="button"
              onClick={() => {
                setMode("latency_cost");
                trackEvent("benchmark_chart_inspected", {
                  mode: "latency_cost",
                });
              }}
              className={cn(
                "min-h-[38px] rounded-sm px-3 font-mono text-xs font-semibold transition-colors",
                mode === "latency_cost"
                  ? "bg-teal-accent text-teal-ink"
                  : "text-fg-muted hover:text-fg"
              )}
            >
              TTFT vs. Cost ($/1M)
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("quality_speed");
                trackEvent("benchmark_chart_inspected", {
                  mode: "quality_speed",
                });
              }}
              className={cn(
                "min-h-[38px] rounded-sm px-3 font-mono text-xs font-semibold transition-colors",
                mode === "quality_speed"
                  ? "bg-teal-accent text-teal-ink"
                  : "text-fg-muted hover:text-fg"
              )}
            >
              Quality vs. tok/s
            </button>
          </div>

          <button
            type="button"
            onClick={() => setShowTable((prev) => !prev)}
            aria-expanded={showTable}
            className="inline-flex min-h-[40px] items-center gap-1.5 rounded-sm border border-border-strong bg-canvas px-3 font-mono text-xs text-fg-muted hover:border-teal-accent hover:text-fg"
          >
            <Table2 className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
            <span>{showTable ? "Hide Table" : "Accessible Table"}</span>
          </button>
        </div>
      </div>

      {/* Main Plot + Live Selected Model Inspector */}
      <div className="mt-6 grid grid-cols-1 items-stretch gap-6 lg:grid-cols-12">
        <div className="overflow-x-auto rounded-md border border-border-subtle bg-canvas p-3 lg:col-span-8">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={
              mode === "latency_cost"
                ? "Scatter plot comparing measured Time To First Token in milliseconds against blended USD cost per million tokens across 12 OpenCore and Frontier models."
                : "Scatter plot comparing Coding and Reasoning Quality Index against output tokens per second across 12 OpenCore and Frontier models."
            }
            className="h-auto w-full min-w-[540px] select-none"
          >
            {/* Horizontal Grid Lines */}
            {[0, 0.25, 0.5, 0.75, 1].map((t) => {
              const y = PAD.top + t * plotH;
              const yLabel =
                mode === "latency_cost"
                  ? `${Math.round(80 + t * (1050 - 80))}ms`
                  : `${Math.round(100 - t * (100 - 64))}`;
              return (
                <g key={t}>
                  <line
                    x1={PAD.left}
                    y1={y}
                    x2={W - PAD.right}
                    y2={y}
                    stroke="rgba(148,163,184,0.14)"
                    strokeDasharray="3 4"
                  />
                  <text
                    x={PAD.left - 10}
                    y={y + 4}
                    textAnchor="end"
                    className="fill-fg-muted font-mono text-[10px]"
                  >
                    {yLabel}
                  </text>
                </g>
              );
            })}

            {/* X-Axis Tick Labels */}
            {(mode === "latency_cost"
              ? [
                  { label: "$0.00 (Local)", r: costToRatio(0) },
                  { label: "$0.16", r: costToRatio(0.16) },
                  { label: "$0.50", r: costToRatio(0.5) },
                  { label: "$2.00", r: costToRatio(2.0) },
                  { label: "$6.00", r: costToRatio(6.0) },
                ]
              : [
                  { label: "30 tok/s", r: (30 - 20) / 140 },
                  { label: "60 tok/s", r: (60 - 20) / 140 },
                  { label: "90 tok/s", r: (90 - 20) / 140 },
                  { label: "120 tok/s", r: (120 - 20) / 140 },
                  { label: "150 tok/s", r: (150 - 20) / 140 },
                ]
            ).map((tk) => {
              const x = PAD.left + tk.r * plotW;
              return (
                <g key={tk.label}>
                  <line
                    x1={x}
                    y1={PAD.top}
                    x2={x}
                    y2={H - PAD.bottom}
                    stroke="rgba(148,163,184,0.1)"
                  />
                  <text
                    x={x}
                    y={H - PAD.bottom + 18}
                    textAnchor="middle"
                    className="fill-fg-muted font-mono text-[10px]"
                  >
                    {tk.label}
                  </text>
                </g>
              );
            })}

            {/* Axis Titles */}
            <text
              x={PAD.left + plotW / 2}
              y={H - 8}
              textAnchor="middle"
              className="fill-fg-dim font-mono text-[11px]"
            >
              {mode === "latency_cost"
                ? "Blended Cost per 1M Tokens (Pseudo-Log Scale · Left = Lower Cost)"
                : "Sustained Output Throughput (tok/s · Right = Faster)"}
            </text>

            {/* Sweet-Spot Callout Badge */}
            <rect
              x={PAD.left + 8}
              y={PAD.top + 6}
              width={205}
              height={22}
              rx={3}
              fill="rgba(45, 212, 191, 0.1)"
              stroke="rgba(45, 212, 191, 0.35)"
            />
            <text
              x={PAD.left + 16}
              y={PAD.top + 20}
              className="fill-teal-accent font-mono text-[10px] font-semibold"
            >
              {mode === "latency_cost"
                ? "↖ SOVEREIGN PARETO SWEET SPOT"
                : "↗ HYBRID QUALITY + SPEED FRONTIER"}
            </text>

            {/* Keelway Hybrid Pareto Frontier Curve */}
            <polyline
              fill="none"
              stroke="var(--teal-accent)"
              strokeWidth="1.75"
              strokeDasharray="5 4"
              opacity="0.65"
              points={paretoPolyline}
            />

            {/* Active Selection Crosshair */}
            {selectedCoord && (
              <g>
                <line
                  x1={selectedCoord.cx}
                  y1={PAD.top}
                  x2={selectedCoord.cx}
                  y2={H - PAD.bottom}
                  stroke="rgba(45,212,191,0.35)"
                  strokeDasharray="2 2"
                />
                <line
                  x1={PAD.left}
                  y1={selectedCoord.cy}
                  x2={W - PAD.right}
                  y2={selectedCoord.cy}
                  stroke="rgba(45,212,191,0.35)"
                  strokeDasharray="2 2"
                />
              </g>
            )}

            {/* Plotted Nodes */}
            {plotted.map(({ pt, cx, cy }) => {
              const isOpen = pt.category === "open_weight";
              const isActive = pt.id === selected.id;
              return (
                <g
                  key={pt.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`${pt.label}: TTFT ${pt.ttftMs}ms, Cost $${pt.blendedUsdPerMtok.toFixed(
                    2
                  )} per million tokens, Quality ${pt.qualityIndex}`}
                  onClick={() => {
                    setSelectedId(pt.id);
                    trackEvent("benchmark_chart_inspected", {
                      model_id: pt.id,
                      mode,
                    });
                  }}
                  onMouseEnter={() => setSelectedId(pt.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedId(pt.id);
                    }
                  }}
                  className="cursor-pointer focus:outline-none"
                >
                  {isActive && (
                    <circle
                      cx={cx}
                      cy={cy}
                      r={12}
                      fill="none"
                      stroke={isOpen ? "var(--teal-accent)" : "var(--amber-alert)"}
                      strokeWidth="2"
                      opacity="0.85"
                    />
                  )}
                  <circle
                    cx={cx}
                    cy={cy}
                    r={isActive ? 6.5 : 5}
                    fill={isOpen ? "var(--teal-accent)" : "var(--amber-alert)"}
                    stroke="#0B0F14"
                    strokeWidth="1.5"
                  />
                  <text
                    x={cx + 8}
                    y={cy + 3.5}
                    className={cn(
                      "font-mono text-[10px] transition-opacity",
                      isActive
                        ? "fill-fg font-bold"
                        : "fill-fg-muted opacity-80"
                    )}
                  >
                    {pt.label}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Legend Strip */}
          <div className="mt-2 flex flex-wrap items-center justify-between gap-3 border-t border-border-subtle pt-2.5 font-mono text-[11px] text-fg-muted">
            <div className="flex flex-wrap items-center gap-4">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-teal-accent" />
                Category A: Open-Weight ($0 Local / VPC)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-alert" />
                Category B: Commercial Frontier Cloud
              </span>
            </div>
            <span className="inline-flex items-center gap-1 text-teal-accent">
              <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
              Dashed Line = Keelway Hybrid Pareto Frontier
            </span>
          </div>
        </div>

        {/* Right Selected Point Telemetry Panel */}
        <div
          aria-live="polite"
          className="flex flex-col justify-between rounded-md border border-border-strong bg-canvas p-5 lg:col-span-4"
        >
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span
                className={cn(
                  "rounded-sm px-2.5 py-0.5 text-[10px]",
                  selected.category === "open_weight"
                    ? "chip-teal"
                    : "chip-amber"
                )}
              >
                {selected.category === "open_weight"
                  ? "OPEN-WEIGHT"
                  : "FRONTIER API"}
              </span>
              {selected.isParetoOptimal && (
                <span className="chip-neutral rounded-sm px-2 py-0.5 text-[10px]">
                  PARETO OPTIMAL
                </span>
              )}
            </div>

            <h4 className="mt-3 font-mono text-base font-bold text-fg">
              {selected.label}
            </h4>
            <p className="mt-0.5 font-mono text-xs text-fg-muted">
              {selected.provider} · {selected.hardwareOrEndpoint}
            </p>
            <p className="mt-3 text-xs leading-relaxed text-fg-muted">
              {selected.notes}
            </p>
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-2.5 border-t border-border-subtle pt-4 font-mono text-xs">
            <div className="rounded-sm border border-border-subtle bg-surface p-2.5">
              <dt className="text-[10px] uppercase text-fg-muted">Warm TTFT</dt>
              <dd className="mt-1 text-sm font-bold tabular-nums text-fg">
                {selected.ttftMs} ms
              </dd>
            </div>
            <div className="rounded-sm border border-border-subtle bg-surface p-2.5">
              <dt className="text-[10px] uppercase text-fg-muted">
                Blended / 1M
              </dt>
              <dd className="mt-1 text-sm font-bold tabular-nums text-teal-accent">
                ${selected.blendedUsdPerMtok.toFixed(2)}
              </dd>
            </div>
            <div className="rounded-sm border border-border-subtle bg-surface p-2.5">
              <dt className="text-[10px] uppercase text-fg-muted">
                Throughput
              </dt>
              <dd className="mt-1 text-sm font-bold tabular-nums text-fg">
                {selected.throughputTokPerSec} tok/s
              </dd>
            </div>
            <div className="rounded-sm border border-border-subtle bg-surface p-2.5">
              <dt className="text-[10px] uppercase text-fg-muted">
                Quality Eval
              </dt>
              <dd className="mt-1 text-sm font-bold tabular-nums text-fg">
                {selected.qualityIndex} / 100
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* WCAG Accessible Data Table View */}
      {showTable && (
        <div className="mt-6 overflow-x-auto rounded-md border border-border-strong bg-canvas">
          <table className="w-full text-left font-mono text-xs">
            <thead className="border-b border-border-strong bg-surface-elevated text-fg-muted">
              <tr>
                <th className="px-3 py-2.5">Model ID</th>
                <th className="px-3 py-2.5">Category</th>
                <th className="px-3 py-2.5">Warm TTFT</th>
                <th className="px-3 py-2.5">Throughput</th>
                <th className="px-3 py-2.5">Blended $/1M</th>
                <th className="px-3 py-2.5">Quality Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-subtle">
              {EMPIRICAL_BENCHMARKS.map((row: BenchmarkPoint) => (
                <tr key={row.id} className="hover:bg-surface/60">
                  <td className="px-3 py-2 font-semibold text-fg">
                    {row.label}
                  </td>
                  <td className="px-3 py-2 text-fg-muted">{row.provider}</td>
                  <td className="px-3 py-2 tabular-nums">{row.ttftMs} ms</td>
                  <td className="px-3 py-2 tabular-nums">
                    {row.throughputTokPerSec} tok/s
                  </td>
                  <td className="px-3 py-2 tabular-nums text-teal-accent">
                    ${row.blendedUsdPerMtok.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {row.qualityIndex}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
