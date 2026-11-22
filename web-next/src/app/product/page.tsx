import type { Metadata } from "next";
import { PolicyDemo } from "@/components/site/policy-demo";
import { FigureTabs } from "@/components/site/figure-tabs";

export const metadata: Metadata = {
  title: "Product — Keelway",
  description: "Gateway, policy engine, and flight recorder — one sovereign platform for AI agents.",
};

const INSTRUMENTS = [
  {
    label: "01 — Gateway",
    title: "Model gateway",
    body: "One endpoint over Ollama, vLLM, TGI, and your provider keys. Open-weight local inference next to governed frontier routing — BYOM at 0% markup.",
  },
  {
    label: "02 — Policy",
    title: "Policy engine",
    body: "Privacy, cost, and capability rules evaluated before egress. P-10 human gates pause for sign-off; air-gap mode fails closed.",
  },
  {
    label: "03 — Tape",
    title: "Flight recorder",
    body: "Every action sealed onto a hash-chained Merkle tape. Receipts verify offline; the chain detects tampering on sight.",
  },
] as const;

export default function ProductPage() {
  return (
    <main className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-fg-muted">Product</p>
      <h1 className="mt-4 max-w-2xl text-4xl font-semibold tracking-tight text-fg">
        One platform. Three instruments.
      </h1>
      <div className="mt-14 grid gap-4 sm:grid-cols-3">
        {INSTRUMENTS.map((i) => (
          <section
            key={i.label}
            aria-label={i.title}
            className="h-full rounded-md border border-border bg-surface p-6 transition-colors hover:border-border-strong"
          >
            <p className="font-mono text-[11px] uppercase tracking-wide text-accent">{i.label}</p>
            <h2 className="mt-4 text-lg font-semibold tracking-tight text-fg">{i.title}</h2>
            <p className="mt-3 text-sm leading-relaxed text-fg-muted">{i.body}</p>
          </section>
        ))}
      </div>
      <div className="mt-12">
        <FigureTabs />
      </div>
      <figure className="mt-12">
        <PolicyDemo />
        <figcaption className="mt-3 font-mono text-[10px] text-fg-muted">
          FIG 1.3 — Policy evaluator, interactive. Set the request conditions; the engine decides before egress.
        </figcaption>
      </figure>
    </main>
  );
}
