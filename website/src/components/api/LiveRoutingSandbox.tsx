"use client";

import React, { useState } from "react";
import { Play, Radio, ShieldCheck, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

const CAP_OPTIONS = ["code", "reasoning", "tools", "vision"] as const;

interface LiveSandboxResponse {
  status: number;
  rttMs: number;
  rateLimitRemaining: string;
  computeMs: string;
  sandboxMode: string;
  payload: Record<string, unknown>;
}

/**
 * OpenRouter-style Live Connected Sandbox Mode (`POST /api/sandbox/routing-explain`).
 * Sends real network requests from the browser to the rate-limited read-only
 * Next.js / Keelway sandbox route, displaying HTTP status, RTT latency,
 * `X-RateLimit-Remaining` headers, secret redaction, and 4D provenance JSON.
 */
export function LiveRoutingSandbox() {
  const [prompt, setPrompt] = useState<string>(
    "Audit src/billing/retry.py for discount rounding bugs. Test key sk-proj-891234567890abcdef and ops@acme.io."
  );
  const [privacyLevel, setPrivacyLevel] = useState<"private" | "standard">(
    "private"
  );
  const [residencyZone, setResidencyZone] = useState<
    "global" | "africa_sovereign" | "eu_sovereign" | "local_only"
  >("global");
  const [caps, setCaps] = useState<string[]>(["code"]);
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<LiveSandboxResponse | null>(null);

  const toggleCap = (cap: string) => {
    setCaps((prev) =>
      prev.includes(cap) ? prev.filter((c) => c !== cap) : [...prev, cap]
    );
  };

  const executeLiveRequest = async () => {
    setLoading(true);
    const t0 = performance.now();
    try {
      const res = await fetch("/api/sandbox/routing-explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt,
          privacy_level: privacyLevel,
          residency_zone: residencyZone,
          required_capabilities: caps,
        }),
      });
      const rttMs = Math.round(performance.now() - t0);
      const data = (await res.json()) as Record<string, unknown>;
      setResult({
        status: res.status,
        rttMs,
        rateLimitRemaining: res.headers.get("X-RateLimit-Remaining") ?? "29",
        computeMs: res.headers.get("X-Keelway-Compute-Ms") ?? "0.4",
        sandboxMode:
          res.headers.get("X-Keelway-Sandbox-Mode") ?? "edge-deterministic",
        payload: data,
      });
      trackEvent("live_sandbox_executed", {
        surface: "api_reference",
        privacy_level: privacyLevel,
        status: res.status,
      });
    } catch {
      setResult({
        status: 503,
        rttMs: Math.round(performance.now() - t0),
        rateLimitRemaining: "-",
        computeMs: "-",
        sandboxMode: "offline",
        payload: { error: "network_unreachable" },
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      id="live-sandbox"
      aria-labelledby="live-sandbox-heading"
      className="frame-crosshair mb-14 rounded-lg border border-border-strong bg-surface p-5 sm:p-6 shadow-xl"
    >
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="chip-neutral inline-flex items-center gap-1.5 rounded-sm px-2.5 py-0.5">
              <Radio className="h-3 w-3 text-teal-accent" aria-hidden="true" />
              LIVE CONNECTED SANDBOX
            </span>
            <span className="font-mono text-xs text-fg-muted">
              POST /api/sandbox/routing-explain · Rate-Limited Read-Only Network
              Runner
            </span>
          </div>
          <h2
            id="live-sandbox-heading"
            className="mt-2 text-xl font-bold text-fg sm:text-2xl"
          >
            Execute a Real 4D Routing &amp; Secret-Redaction Probe Over HTTP
          </h2>
        </div>

        <button
          type="button"
          onClick={executeLiveRequest}
          disabled={loading}
          className="kw-btn kw-btn-primary shrink-0 font-mono text-xs"
        >
          <Play className="h-3.5 w-3.5" aria-hidden="true" />
          <span>
            {loading ? "Dispatching POST…" : "Send Live POST Request"}
          </span>
        </button>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Request Builder */}
        <div className="space-y-4 lg:col-span-6">
          <div>
            <label
              htmlFor="sandbox-prompt-input"
              className="block font-mono text-xs font-semibold text-fg"
            >
              Prompt Payload (Try pasting fake API keys or emails)
            </label>
            <textarea
              id="sandbox-prompt-input"
              rows={3}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="mt-1.5 w-full rounded-md border border-border-strong bg-canvas p-3 font-mono text-xs text-fg focus:border-teal-accent focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <span className="block font-mono text-xs font-semibold text-fg">
                privacy_level
              </span>
              <div className="mt-1.5 grid grid-cols-2 gap-1.5 rounded-sm border border-border-strong bg-canvas p-1">
                {(["private", "standard"] as const).map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    onClick={() => setPrivacyLevel(lvl)}
                    className={cn(
                      "min-h-[38px] rounded-sm px-2.5 font-mono text-xs font-semibold transition-colors",
                      privacyLevel === lvl
                        ? lvl === "private"
                          ? "bg-teal-accent text-teal-ink"
                          : "bg-fg text-canvas"
                        : "text-fg-muted hover:text-fg"
                    )}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label
                htmlFor="sandbox-residency-select"
                className="block font-mono text-xs font-semibold text-fg"
              >
                residency_zone
              </label>
              <select
                id="sandbox-residency-select"
                value={residencyZone}
                onChange={(e) =>
                  setResidencyZone(
                    e.target.value as typeof residencyZone
                  )
                }
                className="mt-1.5 min-h-[46px] w-full rounded-sm border border-border-strong bg-canvas px-3 font-mono text-xs text-fg focus:border-teal-accent focus:outline-none"
              >
                <option value="global">global</option>
                <option value="africa_sovereign">africa_sovereign</option>
                <option value="eu_sovereign">eu_sovereign</option>
                <option value="local_only">local_only</option>
              </select>
            </div>
          </div>

          <div>
            <span className="block font-mono text-xs font-semibold text-fg">
              required_capabilities
            </span>
            <div className="mt-1.5 flex flex-wrap gap-2">
              {CAP_OPTIONS.map((cap) => {
                const active = caps.includes(cap);
                return (
                  <button
                    key={cap}
                    type="button"
                    onClick={() => toggleCap(cap)}
                    className={cn(
                      "min-h-[38px] rounded-sm border px-3 font-mono text-xs transition-colors",
                      active
                        ? "border-teal-accent bg-teal-surface text-teal-accent font-semibold"
                        : "border-border-strong bg-canvas text-fg-muted hover:text-fg"
                    )}
                  >
                    {cap}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Live Network Response Inspector */}
        <div
          aria-live="polite"
          className="flex flex-col rounded-md border border-border-strong bg-canvas lg:col-span-6"
        >
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle bg-surface-elevated/70 px-4 py-2.5 font-mono text-[11px]">
            {result ? (
              <>
                <span
                  className={cn(
                    "rounded-sm px-2 py-0.5 font-semibold",
                    result.status === 200 ? "chip-teal" : "chip-fault"
                  )}
                >
                  HTTP {result.status}
                </span>
                <span className="text-fg-muted">
                  RTT: <strong className="text-fg">{result.rttMs}ms</strong> ·
                  Compute:{" "}
                  <strong className="text-fg">{result.computeMs}ms</strong> ·
                  RateLimit Rem:{" "}
                  <strong className="text-teal-accent">
                    {result.rateLimitRemaining}/30
                  </strong>
                </span>
              </>
            ) : (
              <>
                <span className="inline-flex items-center gap-1.5 text-fg-muted">
                  <ShieldCheck
                    className="h-3.5 w-3.5 text-teal-accent"
                    aria-hidden="true"
                  />
                  Ready — click &ldquo;Send Live POST Request&rdquo;
                </span>
                <span className="inline-flex items-center gap-1 text-fg-dim">
                  <Zap className="h-3 w-3 text-teal-accent" aria-hidden="true" />
                  30 req / min
                </span>
              </>
            )}
          </div>

          <pre className="max-h-[300px] flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed text-fg">
            {result
              ? JSON.stringify(result.payload, null, 2)
              : `// Click "Send Live POST Request" above to inspect a real network response:
// - Pre-egress secret scrubbing (OpenAI/Gemini/Keelway keys, DSNs, emails)
// - Deterministic 4D provenance (license, topology, operator, data_boundary)
// - Live SHA-256 routing decision receipt & HTTP rate-limit headers`}
          </pre>
        </div>
      </div>
    </section>
  );
}
