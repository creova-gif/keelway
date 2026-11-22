import type { Metadata } from "next";
import { FigureTabs } from "@/components/site/FigureTabs";
import { PolicyDemo } from "@/components/site/PolicyDemo";
import { Reveal } from "@/components/motion/Reveal";

export const metadata: Metadata = {
  title: "Product",
  description: "Gateway, policy engine, and flight recorder — one sovereign platform for AI agents.",
};

const INSTRUMENTS = [
  {
    label: "01 — GATEWAY",
    title: "Model gateway",
    body: "One endpoint over Ollama, vLLM, TGI, and your provider keys. Open-weight local inference next to governed frontier routing — BYOM at 0% markup.",
  },
  {
    label: "02 — POLICY",
    title: "Policy engine",
    body: "Privacy, cost, and capability rules evaluated before egress. P-10 human gates pause for sign-off; air-gap mode fails closed.",
  },
  {
    label: "03 — TAPE",
    title: "Flight recorder",
    body: "Every action sealed onto a hash-chained Merkle tape. Receipts verify offline; the chain detects tampering on sight.",
  },
];

export default function ProductPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="kw-label">Product</p>
      <h1 className="kw-h1 mt-5 max-w-2xl">One platform. Three instruments.</h1>
      <div className="mt-14 grid gap-5 sm:grid-cols-3">
        {INSTRUMENTS.map((i, idx) => (
          <Reveal key={i.label} delay={idx as 0 | 1 | 2}>
            <div className="kw-card h-full p-7 transition-colors duration-fast ease-state hover:border-[var(--rule-strong)]">
              <p className="kw-label kw-label-brass">{i.label}</p>
              <h2 className="kw-h3 mt-4">{i.title}</h2>
              <p className="mt-3 text-sm leading-relaxed text-[var(--muted)]">{i.body}</p>
            </div>
          </Reveal>
        ))}
      </div>
      <div className="mt-16">
        <FigureTabs />
      </div>
      <div className="mt-10">
        <figure>
          <PolicyDemo />
          <figcaption className="kw-figcap mt-3">
            FIG 1.3 — Policy evaluator, interactive. Set the request conditions; the engine decides before egress.
          </figcaption>
        </figure>
      </div>
    </div>
  );
}
