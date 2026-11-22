"use client";

import { useState } from "react";

type Flags = { tenant: boolean; airgap: boolean; spendcap: boolean };
type Verdict = { route: string; ok: boolean; rule: string } | null;

function evaluate(f: Flags): Verdict {
  if (f.airgap) {
    return f.tenant
      ? { route: "open_weight · local (ollama)", ok: true, rule: "airgap_strict + classified payload → local inference" }
      : { route: "open_weight · local", ok: true, rule: "airgap_strict → all egress denied; local only" };
  }
  if (f.tenant) {
    return { route: "open_weight · local", ok: true, rule: "classified tenant payload → cloud egress denied" };
  }
  if (f.spendcap) {
    return { route: "frontier pool", ok: false, rule: "spend cap $25/day reached" };
  }
  return { route: "frontier · BYOM key · 0% markup", ok: true, rule: "no policy constraint → governed cloud route" };
}

const TOGGLES: { key: keyof Flags; label: string }[] = [
  { key: "tenant", label: "payload contains tenant data" },
  { key: "airgap", label: "airgap_strict profile active" },
  { key: "spendcap", label: "daily spend cap reached" },
];

export function PolicyDemo() {
  const [flags, setFlags] = useState<Flags>({ tenant: true, airgap: false, spendcap: false });
  const [verdict, setVerdict] = useState<Verdict>(null);
  const [run, setRun] = useState(0);

  const decide = () => {
    setVerdict(evaluate(flags));
    setRun((r) => r + 1);
  };

  return (
    <div className="kw-figure bg-[var(--fog-4)]" role="group" aria-label="Interactive policy engine demo: toggle request conditions, evaluate, and see the route the engine picks before any egress.">
      <div className="flex items-center justify-between border-b border-[var(--rule)] px-4 py-2.5">
        <span className="kw-label">Policy engine · pre-egress evaluation</span>
        <span className="kw-data text-[10px] text-[var(--dim)]">try the rules</span>
      </div>
      <div className="px-4 py-4 sm:px-5">
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {TOGGLES.map((t) => (
            <label key={t.key} className="kw-data flex cursor-pointer items-center gap-2 text-[11px] text-[var(--muted)]">
              <input
                type="checkbox"
                checked={flags[t.key]}
                onChange={() => setFlags({ ...flags, [t.key]: !flags[t.key] })}
                className="accent-[var(--accent)]"
              />
              {t.label}
            </label>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            className="kw-fig-btn bg-[var(--accent)] text-[var(--accent-ink)] hover:bg-[var(--accent-deep)]"
            onClick={decide}
          >
            ▸ evaluate
          </button>
          <span className="kw-data text-[10px] text-[var(--dim)]">evaluated before the prompt leaves the machine</span>
        </div>
        {verdict && (
          <div key={run} className="mt-4 border-t border-[var(--rule)] pt-3" aria-live="polite">
            <p className="kw-data kw-land text-[11px] text-[var(--muted)]">
              rule matched → <span className="text-[var(--ink)]">{verdict.rule}</span>
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <span className="kw-data kw-land text-[11px] text-[var(--dim)]">route: {verdict.route}</span>
              <span className={`kw-chip kw-land ${verdict.ok ? "kw-chip-green" : "kw-chip-red"}`}>
                {verdict.ok ? "✓ ALLOW" : "✗ DENY"}
              </span>
              <span className="kw-data kw-land text-[10px] text-[var(--dim)]">decision sealed to tape</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
