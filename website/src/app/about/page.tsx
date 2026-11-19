import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description: "Keelway is built by Sorvex Labs — a sovereign agent platform, Apache-2.0 open core.",
};

const PRINCIPLES = [
  { id: "P-01", title: "Sovereignty is a feature", body: "Your models, your keys, your tapes. Keelway never holds your prompts hostage — the platform runs where you put it, including air-gapped." },
  { id: "P-02", title: "Every action is accountable", body: "The execution tape is a hash-chained Merkle record. Denials are sealed too — nothing fails silently." },
  { id: "P-03", title: "Governance before egress", body: "Policy decides where a call runs before the prompt leaves the machine. Fail-closed, not best-effort." },
  { id: "P-04", title: "Honest economics", body: "0% token markup on paid tiers. You pay providers at their published rate card; we bill per seat." },
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-4xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="kw-label">About</p>
      <h1 className="kw-h1 mt-5">Built by Sorvex Labs.</h1>
      <p className="kw-body mt-6 max-w-2xl">
        Keelway exists because agent systems asked for trust they hadn&apos;t earned.
        We build the instrument that answers with receipts — an Apache-2.0 open core
        with commercial tiers for teams that need governed routing at scale.
      </p>
      <div className="mt-14 border-t border-[var(--rule)]">
        {PRINCIPLES.map((p) => (
          <div key={p.id} className="kw-row-hover flex flex-col gap-2 border-b border-[var(--rule)] py-7 sm:flex-row sm:gap-10">
            <p className="kw-label w-16 shrink-0 pt-1">{p.id}</p>
            <div>
              <h2 className="kw-h3">{p.title}</h2>
              <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-[var(--muted)]">{p.body}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
