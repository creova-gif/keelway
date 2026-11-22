"use client";

import { useState } from "react";

// Illustrative blended frontier list rate, labeled as such in the UI.
const RATE_PER_MTOK = 10; // USD per 1M tokens, provider list price — BYOM pays this directly, 0% markup

export function CostCompare() {
  const [mtok, setMtok] = useState(20); // millions of tokens per day

  const frontier = Math.round(mtok * RATE_PER_MTOK * 30);
  const local = 0;

  return (
    <div className="kw-figure bg-[var(--fog-4)]" role="group" aria-label="Interactive cost comparison: slide daily token volume and compare marginal cost on open-weight local inference versus frontier provider rates.">
      <div className="flex items-center justify-between border-b border-[var(--rule)] px-4 py-2.5">
        <span className="kw-label">Marginal token cost · per month</span>
        <span className="kw-data text-[10px] text-[var(--dim)]">illustrative</span>
      </div>
      <div className="px-4 py-4 sm:px-5">
        <label className="kw-data flex items-center gap-3 text-[11px] text-[var(--muted)]">
          <span className="shrink-0">workload</span>
          <input
            type="range"
            min={1}
            max={100}
            value={mtok}
            onChange={(e) => setMtok(Number(e.target.value))}
            className="min-w-0 flex-1 accent-[var(--accent)]"
            aria-label="Daily token volume in millions"
          />
          <span className="shrink-0 text-[var(--ink)]">{mtok}M tok/day</span>
        </label>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <div className="kw-card p-4">
            <p className="kw-data text-[10px] text-[var(--dim)]">open_weight · ollama/vllm</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-[var(--green)]">${local}</p>
            <p className="kw-data mt-1 text-[10px] text-[var(--muted)]">marginal token cost — your hardware</p>
          </div>
          <div className="kw-card p-4">
            <p className="kw-data text-[10px] text-[var(--dim)]">frontier · BYOM · 0% markup</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-[var(--ink)]">≈ ${frontier.toLocaleString()}</p>
            <p className="kw-data mt-1 text-[10px] text-[var(--muted)]">provider list rate ≈ $10/1M tok — your key</p>
          </div>
        </div>
        <p className="kw-data mt-4 text-[10px] text-[var(--dim)]">
          every routed call lands on the cost ledger — savings are measured, not claimed
        </p>
      </div>
    </div>
  );
}
