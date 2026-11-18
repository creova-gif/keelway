"use client";

import React, { useState } from "react";
import {
  Boxes,
  Cpu,
  Database,
  GitBranch,
  Layers,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

interface EngineLayer {
  id: string;
  number: string;
  name: string;
  subtitle: string;
  endpoints: string[];
  invariant: string;
  latencyBudget: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

const LAYERS: EngineLayer[] = [
  {
    id: "l1",
    number: "L1",
    name: "Experience, SDK & CLI Surfaces",
    subtitle: "Keelway Studio · 6-Tab Web Console · Python SDK v1 · CLI",
    endpoints: ["keelway.KeelwayClient()", "python3 cli.py dev", "cli.py swarm"],
    invariant: "Identical offline/online developer ergonomics across IDE, CLI, and Python.",
    latencyBudget: "< 16ms UI frame budget",
    description:
      "Operate locally in Keelway Studio (port 7420), inspect real-time model telemetry in the 6-tab Web Console, or integrate programmatically with typed Python/OpenAI-compatible clients.",
    icon: Layers,
  },
  {
    id: "l2",
    number: "L2",
    name: "Unified AI & Stateful Responses API",
    subtitle: "OpenAI-Compatible Chat + Stateful Multi-Turn Responses",
    endpoints: [
      "POST /v1/chat/completions",
      "POST /v1/responses",
      "GET /v1/models",
      "GET /v1/usage",
    ],
    invariant: "Schema-validated SSE streaming, cancellation, and normalized token metering.",
    latencyBudget: "< 2.5ms gateway overhead",
    description:
      "One contract across every open-weight and commercial model. Switch between stateless chat completions and stateful multi-turn agent responses without rewriting application code.",
    icon: Boxes,
  },
  {
    id: "l3",
    number: "L3",
    name: "Model Provider & OpenCore Runtime Bridge",
    subtitle: "Ollama Metal · vLLM CUDA · Gemini · OpenAI · Anthropic",
    endpoints: [
      "POST /v1/opencore/modelfile",
      "POST /v1/opencore/lora/attach",
      "GET /v1/opencore/runtimes",
    ],
    invariant: "Header-only API key transmission (x-goog-api-key) — zero URL secret leakage.",
    latencyBudget: "335ms local TTFT (Metal)",
    description:
      "First-class runtime bridges for local Ollama, vLLM GPU clusters, hot-swappable SHA-256 QLoRA adapters, and commercial cloud APIs with adaptive reasoning budgets.",
    icon: Cpu,
  },
  {
    id: "l4",
    number: "L4",
    name: "Centralized Hybrid Model Registry",
    subtitle: "Live Health Probes · License & Commercial Guardrails · VRAM Specs",
    endpoints: ["GET /v1/models", "GET /v1/models/local", "GET /v1/opencore/catalog"],
    invariant: "Explicit Apache-2.0 vs. Community vs. Commercial license classification.",
    latencyBudget: "O(1) capability lookup",
    description:
      "Tracks verified context windows, tool-calling support, structured outputs, quantization memory footprints, and commercial licensing rules across OpenCore and Frontier families.",
    icon: Database,
  },
  {
    id: "l5",
    number: "L5",
    name: "Deterministic 4D Hybrid Router",
    subtitle: "License · Hosting · Operator · Data Boundary Provenance",
    endpoints: [
      "POST /v1/routing/explain",
      "GET /v1/routing/decisions",
      "POST /v1/eval/swarm",
    ],
    invariant: "Never silently routes private workloads to an unauthorized cloud provider.",
    latencyBudget: "< 0.8ms deterministic policy solve",
    description:
      "Evaluates capability eligibility, tenant residency rules, live provider health, and USD cost ceilings before every call — emitting a full 4-dimension provenance explanation.",
    icon: GitBranch,
  },
  {
    id: "l6",
    number: "L6",
    name: "Tenant Governance & Hash-Chained Audit",
    subtitle: "Scoped kw_live_* Keys · USD Spend Caps · PII Redaction",
    endpoints: [
      "POST /v1/governance/policies",
      "POST /v1/governance/keys",
      "GET /v1/audit/verify",
    ],
    invariant: "Fail-closed default policy (allowed_providers=['local']) + tamper-evident SHA-256 log.",
    latencyBudget: "100% synchronous pre-flight gate",
    description:
      "Enforce hard tenant spend caps (HTTP 402 or automatic OpenCore local fallback), automatic secret/PII redaction, and cryptographic execution logs verifiable offline.",
    icon: ShieldCheck,
  },
];

/**
 * Interactive 6-Layer Keelway Intelligence Engine Topology:
 * Clicking any architectural layer illuminates its position in the live SVG
 * signal pipeline and inspects its endpoints, latency budget, and security invariant.
 */
export function ArchitectureTopology() {
  const [selectedId, setSelectedId] = useState<string>("l5");
  const active = LAYERS.find((l) => l.id === selectedId) ?? LAYERS[4];
  const activeIndex = LAYERS.findIndex((l) => l.id === selectedId);

  return (
    <section
      id="architecture"
      aria-labelledby="arch-heading"
      className="border-t border-border-subtle py-20"
    >
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              01 // 6-LAYER INTELLIGENCE ENGINE
            </p>
            <h2
              id="arch-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
            >
              One sovereign stack from local Metal weights to governed cloud APIs
            </h2>
          </div>
          <p className="max-w-md text-sm text-fg-muted">
            Select any layer below to inspect its live API contract, latency
            budget, and fail-closed governance invariant.
          </p>
        </div>

        <div className="mt-10 grid grid-cols-1 gap-8 lg:grid-cols-12">
          {/* Left Interactive Layer Stack */}
          <div
            className="space-y-2 lg:col-span-5"
            role="listbox"
            aria-label="Keelway Intelligence Engine layers"
          >
            {LAYERS.map((layer) => {
              const Icon = layer.icon;
              const isSelected = layer.id === selectedId;
              return (
                <button
                  key={layer.id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => {
                    setSelectedId(layer.id);
                    trackEvent("architecture_layer_selected", {
                      layer: layer.id,
                    });
                  }}
                  className={cn(
                    "flex min-h-[64px] w-full items-center justify-between gap-3 rounded-md border px-4 py-3 text-left transition-all duration-150",
                    isSelected
                      ? "border-teal-accent bg-surface-elevated shadow-sm"
                      : "border-border-subtle bg-surface hover:border-border-strong hover:bg-surface-elevated/60"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={cn(
                        "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-sm font-mono text-xs font-bold",
                        isSelected
                          ? "bg-teal-accent text-teal-ink"
                          : "bg-canvas text-fg-muted border border-border-strong"
                      )}
                    >
                      {layer.number}
                    </span>
                    <div>
                      <div className="text-sm font-semibold text-fg">
                        {layer.name}
                      </div>
                      <div className="text-xs text-fg-muted">
                        {layer.subtitle}
                      </div>
                    </div>
                  </div>
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      isSelected ? "text-teal-accent" : "text-fg-dim"
                    )}
                    aria-hidden="true"
                  />
                </button>
              );
            })}
          </div>

          {/* Right Live SVG Circuit & Contract Inspector */}
          <div className="lg:col-span-7">
            <div className="frame-crosshair flex h-full flex-col justify-between rounded-lg border border-border-strong bg-surface p-6">
              {/* Interactive SVG Signal Flow Diagram */}
              <div>
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle pb-4">
                  <div className="flex items-center gap-2">
                    <span className="chip-teal rounded-sm px-2.5 py-1">
                      {active.number} ACTIVE
                    </span>
                    <h3 className="text-lg font-bold text-fg">{active.name}</h3>
                  </div>
                  <span className="font-mono text-xs text-teal-accent">
                    {active.latencyBudget}
                  </span>
                </div>

                {/* Accessible Architectural Signal Graph */}
                <div className="my-5 rounded-md border border-border-subtle bg-canvas p-4">
                  <svg
                    viewBox="0 0 620 118"
                    role="img"
                    aria-label={`Signal topology highlighting ${active.number}: ${active.name}`}
                    className="h-auto w-full"
                  >
                    {/* Horizontal Signal Spine */}
                    <line
                      x1="45"
                      y1="59"
                      x2="575"
                      y2="59"
                      stroke="var(--border-strong)"
                      strokeWidth="2"
                      strokeDasharray="4 4"
                    />
                    <line
                      x1="45"
                      y1="59"
                      x2={45 + activeIndex * 106}
                      y2="59"
                      stroke="var(--teal-accent)"
                      strokeWidth="3"
                    />

                    {LAYERS.map((node, idx) => {
                      const cx = 45 + idx * 106;
                      const isCurrent = idx === activeIndex;
                      const isPassed = idx <= activeIndex;
                      return (
                        <g
                          key={node.id}
                          onClick={() => setSelectedId(node.id)}
                          className="cursor-pointer"
                        >
                          <rect
                            x={cx - 32}
                            y={27}
                            width="64"
                            height="64"
                            rx="8"
                            fill={
                              isCurrent
                                ? "var(--teal-accent)"
                                : "var(--bg-surface)"
                            }
                            stroke={
                              isPassed
                                ? "var(--teal-accent)"
                                : "var(--border-strong)"
                            }
                            strokeWidth={isCurrent ? "2.5" : "1.5"}
                          />
                          <text
                            x={cx}
                            y={55}
                            textAnchor="middle"
                            fontSize="12"
                            fontWeight="700"
                            fontFamily="monospace"
                            fill={
                              isCurrent
                                ? "var(--teal-ink)"
                                : "var(--fg-primary)"
                            }
                          >
                            {node.number}
                          </text>
                          <text
                            x={cx}
                            y={73}
                            textAnchor="middle"
                            fontSize="9"
                            fontFamily="monospace"
                            fill={
                              isCurrent ? "var(--teal-ink)" : "var(--fg-muted)"
                            }
                          >
                            {idx < 2
                              ? "INGRESS"
                              : idx < 4
                              ? "MODELS"
                              : "GOVERN"}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>

                <p className="text-sm leading-relaxed text-fg-muted">
                  {active.description}
                </p>
              </div>

              {/* Contract & Security Invariant Footer */}
              <div className="mt-6 space-y-3 border-t border-border-subtle pt-4">
                <div>
                  <div className="font-mono text-[11px] uppercase tracking-wider text-fg-muted">
                    Verified Surface &amp; Endpoints
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {active.endpoints.map((ep) => (
                      <code
                        key={ep}
                        className="rounded-sm border border-border-strong bg-canvas px-2.5 py-1 font-mono text-xs text-teal-accent"
                      >
                        {ep}
                      </code>
                    ))}
                  </div>
                </div>

                <div className="rounded-sm border border-border-strong bg-canvas px-3.5 py-2.5 font-mono text-xs">
                  <span className="font-semibold text-fg">
                    Security Invariant:{" "}
                  </span>
                  <span className="text-fg-muted">{active.invariant}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
