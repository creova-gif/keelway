import React from "react";
import type { Metadata } from "next";
import { EarlyAccessForm } from "@/components/home/EarlyAccessForm";
import { SITE_URL } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Contact & Request Demo",
  description:
    "Contact Sorvex Labs — request a Keelway demo, enterprise VPC/air-gapped review, or early access to the platform.",
  alternates: { canonical: "/contact" },
  openGraph: {
    title: "Contact & Request Demo · Keelway",
    description:
      "Request a Keelway demo or enterprise review from Sorvex Labs.",
    url: `${SITE_URL}/contact`,
  },
};

/**
 * Contact & Request Demo (/contact) — routes into the early-access intake.
 */
export default function ContactPage() {
  return (
    <div>
      <section
        aria-labelledby="contact-heading"
        className="blueprint-surface border-b border-border-subtle py-14 sm:py-20"
      >
        <div className="mx-auto max-w-container px-4 sm:px-6">
          <div className="inline-flex flex-wrap items-center gap-2 rounded-full border border-border-strong bg-surface/90 px-3.5 py-1.5 font-mono text-xs">
            <span className="h-2 w-2 rounded-full bg-teal-accent" aria-hidden="true" />
            <span className="font-semibold text-fg">CONTACT SORVEX LABS</span>
            <span className="text-fg-dim">·</span>
            <span className="text-fg-muted">Demo &amp; enterprise review</span>
          </div>
          <h1
            id="contact-heading"
            className="mt-4 text-3xl font-extrabold tracking-tight text-fg sm:text-5xl"
          >
            Talk to us about
            <br className="hidden sm:block" /> <span className="text-teal-accent">Keelway</span>.
          </h1>
          <p className="mt-4 max-w-2xl text-base leading-relaxed text-fg-muted sm:text-lg">
            Tell us who you are and what you&apos;re building — early access,
            a guided demo, or an enterprise VPC/air-gapped review all route
            through the same intake.
          </p>
        </div>
      </section>

      <section className="py-14 sm:py-16">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <EarlyAccessForm />
        </div>
      </section>
    </div>
  );
}
