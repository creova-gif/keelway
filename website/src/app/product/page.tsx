import type { Metadata } from "next";
import Image from "next/image";

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
        {INSTRUMENTS.map((i) => (
          <div key={i.label} className="kw-card p-7">
            <p className="kw-label kw-label-brass">{i.label}</p>
            <h2 className="kw-h3 mt-4">{i.title}</h2>
            <p className="mt-3 text-sm leading-relaxed text-[var(--muted)]">{i.body}</p>
          </div>
        ))}
      </div>
      <figure className="mt-16">
        <div className="kw-figure">
          <Image src="/product/app-automation.png" alt="Keelway automation view" width={1440} height={900} className="block h-auto w-full" />
        </div>
        <figcaption className="kw-figcap mt-3">FIG 1.1 — KFlow automation boards. Every run writes to the tape.</figcaption>
      </figure>
      <figure className="mt-12">
        <div className="kw-figure">
          <Image src="/product/app-security.png" alt="Keelway security and policy view" width={1440} height={900} className="block h-auto w-full" />
        </div>
        <figcaption className="kw-figcap mt-3">FIG 1.2 — Policy surface. Gates, vaults, and air-gap state.</figcaption>
      </figure>
    </div>
  );
}
