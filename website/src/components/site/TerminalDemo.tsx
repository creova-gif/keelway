"use client";

import { useEffect, useRef, useState } from "react";

type Phase = "idle" | "typing" | "running" | "gate" | "done";
type Outcome = "sealed" | "denied" | null;

const CMD = 'keelway run "harden loopback CSP"';

const PRE_GATE: { text: string; tone: "dim" | "muted" | "info" }[] = [
  { text: "k′ run 7b02.5.2 · policy local-first · sandbox seatbelt", tone: "dim" },
  { text: "ⓘ step 01 plan    — parsed spec, 4 steps", tone: "muted" },
  { text: "ⓘ step 02 retrieve — read core/main.py, core/middleware.py", tone: "muted" },
  { text: "● step 03 execute  — run pytest -q — P-10 GATE RAISED", tone: "info" },
];

export function TerminalDemo() {
  const [phase, setPhase] = useState<Phase>("idle");
  const [typed, setTyped] = useState(0);
  const [shown, setShown] = useState(0);
  const [outcome, setOutcome] = useState<Outcome>(null);
  const timers = useRef<number[]>([]);

  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  const later = (fn: () => void, ms: number) => {
    timers.current.push(window.setTimeout(fn, reduced ? 0 : ms));
  };

  const run = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    setOutcome(null);
    setShown(0);
    setPhase("typing");
    if (reduced) {
      setTyped(CMD.length);
      setShown(PRE_GATE.length);
      setPhase("gate");
      return;
    }
    for (let i = 1; i <= CMD.length; i++) {
      later(() => setTyped(i), i * 28);
    }
    const base = CMD.length * 28 + 300;
    later(() => setPhase("running"), base);
    PRE_GATE.forEach((_, i) => {
      later(() => setShown(i + 1), base + i * 420);
    });
    later(() => setPhase("gate"), base + PRE_GATE.length * 420 + 500);
  };

  const decide = (o: Exclude<Outcome, null>) => {
    setOutcome(o);
    setPhase("done");
  };

  const replay = () => {
    setPhase("idle");
    setTyped(0);
    setShown(0);
    setOutcome(null);
  };

  const toneCls = { dim: "text-[var(--dim)]", muted: "text-[var(--muted)]", info: "text-[var(--brass)]" };

  return (
    <div className="kw-figure bg-[var(--fog-4)]" role="group" aria-label="Keelway terminal session replay: run a task, hit a P-10 gate, decide, and watch the receipt seal.">
      <div className="flex items-center justify-between border-b border-[var(--rule)] px-4 py-2.5">
        <span className="kw-label">k′ — session replay</span>
        <span className="kw-data text-[10px] text-[var(--dim)]">tty · sandboxed</span>
      </div>
      <div className="px-4 py-4 sm:px-5" aria-live={phase === "running" ? "polite" : "off"}>
        <div className="kw-data text-[12px] text-[var(--ink)]">
          <span className="text-[var(--brass)]">$ </span>
          {phase === "idle" ? <span className="text-[var(--dim)]">ready — press run</span> : CMD.slice(0, typed)}
          {phase === "typing" && <span aria-hidden="true">▍</span>}
        </div>
        <ul className="mt-3 space-y-1.5" role="log">
          {PRE_GATE.slice(0, shown).map((l, i) => (
            <li key={i} className={`kw-data kw-land text-[11px] ${toneCls[l.tone]}`}>
              {l.text}
            </li>
          ))}
          {phase === "done" && outcome === "sealed" && (
            <>
              <li className="kw-data kw-land text-[11px] text-[var(--green)]">✓ approved once — executed in sandbox</li>
              <li className="kw-data kw-land text-[11px] text-[var(--green)]">✓ receipt #1284 sealed · hash ↱#1283</li>
              <li className="kw-data kw-land text-[11px] text-[var(--dim)]">tape verified · chain ok · egress 0 bytes</li>
            </>
          )}
          {phase === "done" && outcome === "denied" && (
            <>
              <li className="kw-data kw-land text-[11px] text-[var(--red)]">✗ denied by operator — run aborted</li>
              <li className="kw-data kw-land text-[11px] text-[var(--red)]">✗ denial sealed to tape #1284 · denials record too</li>
            </>
          )}
        </ul>
        <div className="mt-4 flex items-center gap-3">
          {phase === "idle" && (
            <button type="button" className="kw-fig-btn bg-[var(--brass)] text-[var(--brass-ink)] hover:bg-[var(--brass-deep)]" onClick={run}>
              ▸ run session
            </button>
          )}
          {phase === "typing" || phase === "running" ? (
            <span className="kw-data text-[10px] text-[var(--dim)]">running…</span>
          ) : null}
          {phase === "gate" && (
            <>
              <button type="button" className="kw-fig-btn bg-[var(--brass)] text-[var(--brass-ink)] hover:bg-[var(--brass-deep)]" onClick={() => decide("sealed")}>
                Allow once
              </button>
              <button type="button" className="kw-fig-btn border border-[var(--rule-strong)] text-[var(--ink)] hover:bg-[var(--fog-8)]" onClick={() => decide("denied")}>
                Deny
              </button>
              <span className="kw-data ml-auto text-[10px] text-[var(--dim)]">the gate waits for you</span>
            </>
          )}
          {phase === "done" && (
            <>
              <button type="button" className="kw-fig-btn border border-[var(--rule-strong)] text-[var(--muted)] hover:bg-[var(--fog-8)] hover:text-[var(--ink)]" onClick={replay}>
                ↺ replay
              </button>
              <span className="kw-data ml-auto text-[10px] text-[var(--dim)]">a = allow · d = deny · same keys as the real gate</span>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
