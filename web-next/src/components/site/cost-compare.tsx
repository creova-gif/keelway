"use client";

import { useState } from "react";

// Illustrative blended frontier list rate, labeled as such in the UI.
const RATE_PER_MTOK = 10; // USD per 1M tokens, provider list price — BYOM pays this directly, 0% markup

export function CostCompare() {
  const [mtok, setMtok] = useState(20); // millions of tokens per day

  const frontier = Math.round(mtok * RATE_PER_MTOK * 30);
  const local = 0;

  return (
    <div
      className="overflow-hidden rounded-md border border-border bg-surface-raised"
      role="group"
      aria-label="Interactive cost comparison: slide daily token volume and compare marginal cost on open-weight local inference versus frontier provider rates."
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">
          Marginal token cost · per month
        </span>
        <span className="font-mono text-[10px] text-fg-muted">illustrative</span>
      </div>
      <div className="px-4 py-4 sm:px-5">
        <label className="flex items-center gap-3 font-mono text-[11px] text-fg-muted">
          <span className="shrink-0">workload</span>
          <input
            type="range"
            min={1}
            max={100}
            value={mtok}
            onChange={(e) => setMtok(Number(e.target.value))}
            className="min-w-0 flex-1 accent-accent"
            aria-label="Daily token volume in millions"
          />
          <span className="shrink-0 text-fg">{mtok}M tok/day</span>
        </label>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-border bg-surface p-4">
            <p className="font-mono text-[10px] text-fg-muted">open_weight · ollama/vllm</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-ok">${local}</p>
            <p className="mt-1 font-mono text-[10px] text-fg-muted">marginal token cost — your hardware</p>
          </div>
          <div className="rounded-md border border-border bg-surface p-4">
            <p className="font-mono text-[10px] text-fg-muted">frontier · BYOM · 0% markup</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-fg">≈ ${frontier.toLocaleString()}</p>
            <p className="mt-1 font-mono text-[10px] text-fg-muted">provider list rate ≈ $10/1M tok — your key</p>
          </div>
        </div>
        <p className="mt-4 font-mono text-[10px] text-fg-muted">
          every routed call lands on the cost ledger — savings are measured, not claimed
        </p>
      </div>
    </div>
  );
}
