"use client";

import React, { useState } from "react";
import { Gauge } from "lucide-react";
import { trackEvent } from "@/lib/analytics";

const MULTIPLIERS: Record<number, string> = {
  1: "1.45x", 2: "1.88x", 3: "2.24x", 4: "2.58x",
  5: "2.84x", 6: "3.02x", 7: "3.15x", 8: "3.22x",
};
const SPEEDS: Record<number, string> = {
  1: "38.4", 2: "49.8", 3: "59.3", 4: "68.4",
  5: "75.2", 6: "80.0", 7: "83.5", 8: "85.3",
};

/**
 * Speculative decoding tandem-velocity explorer — migrated from the legacy
 * Kora landing page. Simulates 0.5B draft + 7B target verification throughput.
 */
export function SpeculativeDecodingLab() {
  const [k, setK] = useState(4);

  return (
    <div className="frame-crosshair rounded-lg border border-border-strong bg-surface p-5 sm:p-8">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-subtle pb-5">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-border-strong bg-canvas px-3.5 py-1 font-mono text-xs text-fg">
            <Gauge className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
            <span className="font-semibold">SPECULATIVE DECODING LAB</span>
          </div>
          <h2 className="mt-3 text-xl font-bold tracking-tight text-fg sm:text-2xl">
            Tandem Velocity Simulator
          </h2>
          <p className="mt-1 text-sm text-fg-muted">
            0.5B Draft Model + 7B Target Model tandem inference.
          </p>
        </div>
        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="text-fg-muted">Measured Speedup:</span>
          <span className="text-lg font-bold tabular-nums text-teal-accent" aria-live="polite">
            {MULTIPLIERS[k]}
          </span>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="rounded-md border border-border-subtle bg-canvas p-4">
          <div className="font-mono text-[11px] font-bold uppercase tracking-wider text-fg-muted">
            Draft Speculation Lookahead (k-tokens)
          </div>
          <div className="mt-3 flex items-center gap-3">
            <input
              type="range"
              min={1}
              max={8}
              value={k}
              aria-label="Draft speculation lookahead tokens"
              onChange={(e) => {
                const v = Number(e.target.value);
                setK(v);
                trackEvent("spec_decoding_k_changed", { k: v });
              }}
              className="h-2 flex-1 cursor-pointer accent-teal-accent"
            />
            <span className="w-8 text-center font-mono text-sm font-bold tabular-nums text-teal-accent" aria-hidden="true">
              {k}
            </span>
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-fg-muted">
            Draft generates k tokens in a single lightweight forward pass; the 7B target
            model verifies all candidate tokens in parallel with 100% output equivalence.
          </p>
        </div>

        <div className="flex flex-col justify-between rounded-md border border-border-subtle bg-canvas p-4">
          <div>
            <div className="font-mono text-[11px] font-bold uppercase tracking-wider text-fg-muted">
              Simulated Throughput
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-extrabold tabular-nums text-fg">
                {SPEEDS[k]}
              </span>
              <span className="font-mono text-xs text-fg-muted">tokens / sec</span>
            </div>
            <div className="mt-1 font-mono text-[11px] text-fg-dim">
              vs 26.5 tok/s unaccelerated target model
            </div>
          </div>
          <div className="mt-4 flex justify-between border-t border-border-subtle pt-3 font-mono text-[11px] text-fg-muted">
            <span>
              VRAM Overhead: <strong className="text-fg">+850 MB</strong>
            </span>
            <span>
              Latency Drop: <strong className="text-teal-accent">-61.2%</strong>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
