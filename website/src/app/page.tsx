import React from "react";
import { evaluate } from "flags/next";
import { expHomeGateFlag, expQuickstartCliFlag } from "@/flags";
import { ExperimentFlagValues } from "@/components/experiments/ExperimentFlagValues";
import { HeroCtaLinks } from "@/components/home/HeroCtaLinks";
import { HeroControlCockpit } from "@/components/home/HeroControlCockpit";
import { CustomerJourneyGrid } from "@/components/home/CustomerJourneyGrid";
import { GoldenThreadStudioShowcase } from "@/components/home/GoldenThreadStudioShowcase";
import { ApprovalGateStepper } from "@/components/home/ApprovalGateStepper";
import { P10InteractiveDeck } from "@/components/home/P10InteractiveDeck";
import { QuickstartTerminal } from "@/components/home/QuickstartTerminal";
import { ProductShowcase } from "@/components/home/ProductShowcase";
import { Reveal } from "@/components/motion/Reveal";
import { SettlementRails } from "@/components/home/SettlementRails";
import { EarlyAccessForm } from "@/components/home/EarlyAccessForm";
import { SITE_URL } from "@/lib/utils";

const softwareSchema = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Keelway",
  url: SITE_URL,
  applicationCategory: "DeveloperApplication",
  operatingSystem: "macOS, Linux, Windows, Docker",
  license: "https://www.apache.org/licenses/LICENSE-2.0",
  offers: {
    "@type": "Offer",
    price: "0",
    priceCurrency: "USD",
  },
  description:
    "Local-first AI agent runtime with deterministic 4D routing, human-in-the-loop P-10 governance, and zero-markup BYOM cloud bursting.",
};

export default async function HomePage() {
  const [homeGateVariant, quickstartVariant] = await evaluate([
    expHomeGateFlag,
    expQuickstartCliFlag,
  ]);

  return (
    <div>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareSchema) }}
      />
      <ExperimentFlagValues
        surface="home"
        values={{
          "exp-home-gate-v1": homeGateVariant,
          "exp-quickstart-cli-v1": quickstartVariant,
        }}
      />

      <section
        aria-labelledby="hero-heading"
        className="blueprint-surface relative border-b border-border-subtle py-16 sm:py-24"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-12">
            <div className="lg:col-span-6">
              <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-border-strong bg-surface/90 px-3.5 py-1.5 font-mono text-xs">
                <span
                  className="h-2 w-2 rounded-full bg-teal-accent"
                  aria-hidden="true"
                />
                <span className="font-semibold text-fg">
                  APACHE-2.0 OPEN-CORE
                </span>
                <span className="text-fg-dim">·</span>
                <span className="text-fg-muted">
                  Sovereign Runtime · 4D Router · Signed Marketplace
                </span>
              </div>

              <h1
                id="hero-heading"
                className="kw-display mt-6 text-fg"
              >
                Local-first AI agent runtime with{" "}
                <span className="text-teal-accent">
                  cryptographic governance.
                </span>
              </h1>

              <p className="mt-4 max-w-xl text-base leading-relaxed text-fg-muted sm:text-lg">
                Execute routine agent loops locally at $0 token COGS, burst to
                Frontier APIs at 0% markup, and enforce human-signed approvals
                before every production mutation.
              </p>

              <HeroCtaLinks />

              <dl className="mt-10 grid grid-cols-2 gap-4 border-t border-border-subtle pt-6 font-mono sm:grid-cols-4">
                <div>
                  <dt className="text-[11px] uppercase text-fg-muted">
                    Local Traces
                  </dt>
                  <dd className="mt-1 text-lg font-bold tabular-nums text-fg">
                    $0
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase text-fg-muted">
                    BYOM Markup
                  </dt>
                  <dd className="mt-1 text-lg font-bold tabular-nums text-fg">
                    0%
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase text-fg-muted">
                    Team Seat
                  </dt>
                  <dd className="mt-1 text-lg font-bold tabular-nums text-fg">
                    $29/seat
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] uppercase text-fg-muted">
                    Marketplace
                  </dt>
                  <dd className="mt-1 text-lg font-bold tabular-nums text-fg">
                    85/15
                  </dd>
                </div>
              </dl>
            </div>

            <div className="lg:col-span-6">
              <HeroControlCockpit />
            </div>
          </div>
        </div>
      </section>

      <CustomerJourneyGrid />

      <GoldenThreadStudioShowcase />

      {homeGateVariant === "interactive-p10-deck" ? (
        <P10InteractiveDeck />
      ) : (
        <ApprovalGateStepper />
      )}

      <QuickstartTerminal variant={quickstartVariant} />

      <Reveal>
        <ProductShowcase />
      </Reveal>

      <section
        aria-labelledby="proof-strip-heading"
        className="border-t border-border-subtle py-10"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <h2 id="proof-strip-heading" className="sr-only">
            Verifiable platform facts
          </h2>
          <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {[
              { k: "LICENSE", v: "Apache-2.0 open core" },
              { k: "SDK PARITY", v: "Python · TypeScript · Go" },
              { k: "EVAL HARNESS", v: "16-probe golden suite" },
              { k: "TOKEN MARKUP", v: "0% — BYOM pass-through" },
            ].map((f) => (
              <div
                key={f.k}
                className="rounded-md border border-border-subtle bg-surface px-4 py-3"
              >
                <dt className="font-mono text-[10px] uppercase tracking-wider text-fg-dim">
                  {f.k}
                </dt>
                <dd className="mt-1 font-mono text-xs font-semibold text-fg">
                  {f.v}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      <SettlementRails />

      <div className="border-t border-border-subtle bg-canvas py-8">
        <div className="mx-auto flex max-w-container flex-col items-start justify-between gap-3 px-4 sm:flex-row sm:items-center sm:px-6">
          <p className="font-mono text-xs font-semibold uppercase tracking-wider text-fg">
            ENTERPRISE VPC &amp; DESIGN-PARTNER DEPLOYMENTS
          </p>
          <p className="text-sm text-fg-muted">
            Air-gapped AWS, GCP, and on-prem deployments with enterprise SSO (OIDC), SCIM 2.0, and SOC2/HIPAA audit exports.
          </p>
        </div>
      </div>
      <EarlyAccessForm />
    </div>
  );
}
