import Link from "next/link";
import { Chip } from "@/components/ui/chip";
import { ReceiptTable, type ReceiptRow } from "@/components/site/receipt-table";
import { PolicyDemo } from "@/components/site/policy-demo";
import { FigureTabs } from "@/components/site/figure-tabs";

const INSTRUMENTS = [
  {
    label: "The gateway",
    body: "One endpoint for every model — local Ollama or vLLM, or frontier APIs under your key. Routing decided at policy time, not runtime.",
    chip: { variant: "neutral", text: "local · byom · frontier" },
  },
  {
    label: "The policy",
    body: "Privacy, cost, and capability rules evaluated before the prompt leaves the machine. Air-gap blocks egress — the attempt is sealed, not silent.",
    chip: { variant: "gate", text: "P-4 · P-10 gates" },
  },
  {
    label: "The tape",
    body: "Hash-chained Merkle flight recorder. Every action a signed receipt — read, edit, route, gate — verifiable offline.",
    chip: { variant: "sealed", text: "receipt-signed" },
  },
] as const;

const RECEIPTS: ReceiptRow[] = [
  { id: "#1201", action: "read", target: "core/main.py", route: "local", state: "sealed" },
  { id: "#1202", action: "edit", target: "core/routes.py", route: "local", state: "sealed" },
  { id: "#1203", action: "route", target: "claude-sonnet-4.6", route: "byom", state: "sealed" },
  { id: "#1204", action: "gate", target: "P-10 human sign-off", route: "—", state: "awaiting" },
];

export default function Product() {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-16 sm:px-8 sm:py-24">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">
        Product — the control plane
      </p>
      <h1 className="mt-6 max-w-3xl text-5xl font-semibold tracking-tight text-fg sm:text-6xl">
        Every action on the tape. Yours to replay.
      </h1>
      <p className="mt-6 max-w-lg text-base leading-7 text-fg-muted">
        Keelway is not a chat window. It is the instrument that decides where
        each agent call runs, gates what may act, and seals the evidence.
      </p>

      <div className="mt-16 grid gap-10 border-t border-border pt-12 sm:grid-cols-3">
        {INSTRUMENTS.map((i) => (
          <div key={i.label}>
            <Chip variant={i.chip.variant}>{i.chip.text}</Chip>
            <h2 className="mt-4 font-mono text-[11px] uppercase tracking-[0.2em] text-fg">{i.label}</h2>
            <p className="mt-3 max-w-xs text-sm leading-6 text-fg-muted">{i.body}</p>
          </div>
        ))}
      </div>

      <div className="mt-16">
        <FigureTabs />
      </div>

      <div className="mt-20">
        <ReceiptTable rows={RECEIPTS} caption="Fig 1.2 — execution receipts, sample render" />
      </div>

      <div className="mt-20 border-t border-border pt-12">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">
          Fig 1.3 — policy verdict, try it
        </p>
        <h2 className="mt-4 text-2xl font-semibold tracking-tight text-fg">
          Route decided at policy time, not runtime.
        </h2>
        <p className="mt-3 max-w-lg text-sm leading-6 text-fg-muted">
          A live model of the egress check — runs locally in this page. Toggle
          the request conditions and evaluate; no call leaves your browser.
        </p>
        <div className="mt-8">
          <PolicyDemo />
        </div>
      </div>

      <div className="mt-16 flex flex-wrap items-center gap-5 border-t border-border pt-10">
        <Link href="/pricing" className="text-sm text-fg-muted transition-colors hover:text-fg">
          See pricing →
        </Link>
        <a
          href="https://github.com/creova-gif/keelway#readme"
          target="_blank"
          rel="noopener"
          className="text-sm text-fg-muted transition-colors hover:text-fg"
        >
          Install from source →
        </a>
      </div>
    </main>
  );
}
