"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

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
    <div
      className="overflow-hidden rounded-md border border-border bg-surface-raised"
      role="group"
      aria-label="Interactive policy engine demo: toggle request conditions, evaluate, and see the route the engine picks before any egress."
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-2.5">
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">
          Policy engine · pre-egress evaluation
        </span>
        <span className="font-mono text-[10px] text-fg-muted">try the rules</span>
      </div>
      <div className="px-4 py-4 sm:px-5">
        <div className="flex flex-wrap gap-x-6 gap-y-2">
          {TOGGLES.map((t) => (
            <label key={t.key} className="flex cursor-pointer items-center gap-2 font-mono text-[11px] text-fg-muted">
              <input
                type="checkbox"
                checked={flags[t.key]}
                onChange={() => setFlags({ ...flags, [t.key]: !flags[t.key] })}
                className="accent-accent"
              />
              {t.label}
            </label>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button size="sm" onClick={decide}>
            ▸ evaluate
          </Button>
          <span className="font-mono text-[10px] text-fg-muted">
            evaluated before the prompt leaves the machine
          </span>
        </div>
        {verdict && (
          <div key={run} className="mt-4 border-t border-border pt-3" aria-live="polite">
            <p className="font-mono text-[11px] text-fg-muted">
              rule matched → <span className="text-fg">{verdict.rule}</span>
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <span className="font-mono text-[11px] text-fg-muted">route: {verdict.route}</span>
              <span
                className={`rounded-sm px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wide ${
                  verdict.ok ? "bg-ok-subtle text-ok" : "bg-danger-subtle text-danger"
                }`}
              >
                {verdict.ok ? "✓ Allow" : "✗ Deny"}
              </span>
              <span className="font-mono text-[10px] text-fg-muted">decision sealed to tape</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
