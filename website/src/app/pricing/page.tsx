import type { Metadata } from "next";
import Link from "next/link";
import { Reveal } from "@/components/motion/Reveal";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Community free, BYOM from $15/seat/mo, Pro from $29/seat/mo — 0% token markup. Enterprise Sovereign VPC on request.",
};

const TIERS = [
  { name: "Community", price: "$0", cadence: "Apache-2.0 core · offline", features: ["Local inference", "Full tape + receipts", "Air-gap mode"], accent: false },
  { name: "BYOM", price: "$15", cadence: "annual · $19 monthly", features: ["Your provider keys", "0% token markup", "Team policies"], accent: false },
  { name: "Pro", price: "$29", cadence: "annual · $35 monthly", features: ["Frontier routing", "P-10 gates + SSO", "Audit exports"], accent: true },
  { name: "Enterprise", price: "Custom", cadence: "Sovereign VPC · annual", features: ["Air-gap / dedicated VPC", "Dual-human quorum", "SAML/SSO + SLAs"], accent: false },
];

export default function PricingPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-24">
      <p className="kw-label">Pricing</p>
      <h1 className="kw-h1 mt-5">Priced like a ledger.</h1>
      <p className="kw-body mt-5 max-w-xl">
        Seat pricing shown at annual billing. Every paid tier routes at 0% token markup.
      </p>
      <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {TIERS.map((t, idx) => (
          <Reveal key={t.name} delay={Math.min(idx, 2) as 0 | 1 | 2}>
            <div
              className={`kw-card h-full p-6 transition-colors duration-fast ease-state hover:border-[var(--rule-strong)] ${t.accent ? "border-[var(--accent-40)] bg-[var(--accent-8)]" : ""}`}
            >
              <p className={`kw-label ${t.accent ? "kw-label-accent" : ""}`}>{t.name}</p>
              <p className="mt-4 text-3xl font-semibold tracking-tight text-[var(--ink)]">
                {t.price}
                {t.price !== "$0" && <span className="text-sm font-normal text-[var(--dim)]">/seat/mo</span>}
              </p>
              <p className="kw-small mt-2">{t.cadence}</p>
              <ul className="mt-5 space-y-2.5 border-t border-[var(--rule)] pt-4 text-[13px] text-[var(--muted)]">
                {t.features.map((f) => <li key={f}>{f}</li>)}
              </ul>
            </div>
          </Reveal>
        ))}
      </div>
      <div className="mt-10 flex flex-col gap-3 border-t border-[var(--rule)] pt-6 sm:flex-row sm:items-baseline sm:justify-between">
        <p className="text-sm text-[var(--muted)]">Volume seats or a dedicated deployment — annual contract.</p>
        <Link href="/contact" className="kw-data text-[var(--accent)]">Talk to us &rarr;</Link>
      </div>
    </div>
  );
}
