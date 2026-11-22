import Link from "next/link";
import { Button } from "@/components/ui/button";
import { TerminalDemo } from "@/components/site/terminal-demo";
import { InstallCommand } from "@/components/site/install-command";

const TASKS = [
  "Harden loopback CSP",
  "Audit Merkle proofs",
  "Migrate tape WAL",
  "Route frontier burst",
];

const RECEIPTS = [
  { id: "#1201", action: "read", target: "core/main.py", state: "sealed" },
  { id: "#1202", action: "edit", target: "core/routes.py", state: "sealed" },
  { id: "#1203", action: "route", target: "ollama/qwen2.5", state: "sealed" },
  { id: "#1204", action: "gate", target: "P-10 human sign-off", state: "awaiting" },
];

const COLUMNS = [
  {
    label: "Your hardware",
    body: "Open-weight models run where they live — Ollama or private vLLM. $0 marginal token.",
  },
  {
    label: "Your policy",
    body: "Privacy, cost, and capability decide where each call runs — before the prompt leaves the machine.",
  },
  {
    label: "Your records",
    body: "Hash-chained tape of every action. P-10 human gates on anything that touches production.",
  },
] as const;

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-16 sm:px-8 sm:py-24">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">
        Keelway — sovereign agent platform
      </p>
      <h1 className="mt-6 max-w-3xl text-5xl font-semibold tracking-tight text-fg sm:text-6xl">
        Agents that answer to you.
      </h1>
      <p className="mt-6 max-w-lg text-base leading-7 text-fg-muted">
        A sovereign platform for AI agents. Local inference, governed cloud
        routing, and a signed receipt for every action.
      </p>
      <div className="mt-8 flex flex-wrap items-center gap-5">
        <Button asChild>
          <a href="https://github.com/creova-gif/keelway#readme" target="_blank" rel="noopener">
            Install Keelway
          </a>
        </Button>
        <Link href="/docs" className="text-sm text-fg-muted transition-colors hover:text-fg">
          Read the docs →
        </Link>
      </div>

      <InstallCommand />

      <figure className="mt-20">
        <div className="overflow-hidden rounded-md border border-border bg-surface-raised">
          <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
            <span className="h-2 w-2 rounded-full bg-border-strong" aria-hidden="true" />
            <span className="h-2 w-2 rounded-full bg-border-strong" aria-hidden="true" />
            <span className="h-2 w-2 rounded-full bg-border-strong" aria-hidden="true" />
            <span className="ml-2 font-mono text-[11px] text-fg-muted">keelway dev — localhost:8787</span>
          </div>
          <div className="grid sm:grid-cols-[220px_1fr]">
            <div className="border-b border-border px-4 py-4 sm:border-b-0 sm:border-r">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-fg-muted">Tasks</p>
              <ul className="mt-3 space-y-2.5 text-[13px] text-fg">
                {TASKS.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </div>
            <div className="px-4 py-4 sm:px-5">
              <div className="flex flex-wrap gap-2">
                <span className="rounded-sm border border-accent/40 bg-accent-subtle px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-accent">
                  P-10 gate · approval pending
                </span>
                <span className="rounded-sm border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-fg-muted">
                  local · $0 token
                </span>
                <span className="rounded-sm border border-border px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-fg-muted">
                  BYOM · 0% markup
                </span>
              </div>
              <p className="mt-5 font-mono text-[10px] uppercase tracking-[0.18em] text-fg-muted">
                Execution receipts
              </p>
              <ul className="mt-2 divide-y divide-border font-mono text-[12px]">
                {RECEIPTS.map((r) => (
                  <li key={r.id} className="flex items-baseline justify-between gap-4 py-2">
                    <span className="text-fg-muted">
                      {r.id} <span className="text-fg">{r.action}</span> {r.target}
                    </span>
                    <span className={r.state === "sealed" ? "text-ok" : "text-accent"}>{r.state}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex flex-wrap gap-x-10 gap-y-2 border-t border-border pt-4 font-mono">
                <div>
                  <p className="text-[10px] uppercase tracking-[0.18em] text-fg-muted">Session cost</p>
                  <p className="mt-1 text-base text-fg">$0.00</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-[0.18em] text-fg-muted">Tape height</p>
                  <p className="mt-1 text-base text-fg">1,204</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-[0.18em] text-fg-muted">Chain</p>
                  <p className="mt-1 text-base text-accent">verified</p>
                </div>
              </div>
            </div>
          </div>
        </div>
        <figcaption className="mt-3 font-mono text-[10px] uppercase tracking-[0.18em] text-fg-muted">
          Fig 0.1 — Keelway control plane, dev app surface
        </figcaption>
      </figure>

      <figure className="mt-16">
        <TerminalDemo />
        <figcaption className="mt-3 font-mono text-[10px] uppercase tracking-[0.18em] text-fg-muted">
          Fig 0.2 — session replay, live: run a task, hit the P-10 gate, decide — the receipt seals either way
        </figcaption>
      </figure>

      <div className="mt-16 grid gap-10 border-t border-border pt-12 sm:grid-cols-3">
        {COLUMNS.map((c) => (
          <div key={c.label}>
            <h2 className="font-mono text-[11px] uppercase tracking-[0.2em] text-accent">{c.label}</h2>
            <p className="mt-3 max-w-xs text-sm leading-6 text-fg-muted">{c.body}</p>
          </div>
        ))}
      </div>
    </main>
  );
}
