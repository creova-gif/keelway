"use client";

import React, { useState } from "react";
import { Landmark, QrCode, Smartphone, Zap } from "lucide-react";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

type Rail = "mpesa" | "pix" | "upi" | "l402";

const RAILS: {
  id: Rail;
  name: string;
  desc: string;
  icon: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
}[] = [
  { id: "mpesa", name: "M-Pesa (East Africa)", desc: "Safaricom Daraja STK Push", icon: Smartphone },
  { id: "pix", name: "PIX (Brazil)", desc: "Instant EMVCo QR Clearing", icon: QrCode },
  { id: "upi", name: "UPI 2.0 (India)", desc: "NPCI AutoPay & Virtual Private Address", icon: Landmark },
  { id: "l402", name: "L402 Lightning Network", desc: "Global Bitcoin Satoshi Streaming", icon: Zap },
];

const DETAILS: Record<Rail, { title: string; lines: React.ReactNode[] }> = {
  mpesa: {
    title: "M-Pesa STK Push Simulation",
    lines: [
      <>Provider: <span className="text-fg">Safaricom Daraja API</span></>,
      <>
        Typical Amount:{" "}
        <span className="font-bold text-teal-accent">1,000 KES (~$7.70 USD)</span>
      </>,
      <>
        Protocol:{" "}
        <span className="text-fg-muted">Instant STK handset push on phone number</span>
      </>,
    ],
  },
  pix: {
    title: "PIX Instant EMVCo Clearing",
    lines: [
      <>Provider: <span className="text-fg">Banco Central do Brasil</span></>,
      <>
        Typical Amount: <span className="font-bold text-teal-accent">R$ 25.00 BRL (~$4.50 USD)</span>
      </>,
      <>
        Protocol: <span className="text-fg-muted">Dynamic EMVCo QR &amp; Copia-e-Cola token</span>
      </>,
    ],
  },
  upi: {
    title: "UPI 2.0 National Payments",
    lines: [
      <>Provider: <span className="text-fg">NPCI (India)</span></>,
      <>
        Typical Amount: <span className="font-bold text-teal-accent">₹150 INR (~$1.80 USD)</span>
      </>,
      <>
        Protocol: <span className="text-fg-muted">upi://pay?pa=keelway@axis deep-link intent</span>
      </>,
    ],
  },
  l402: {
    title: "L402 Lightning Protocol",
    lines: [
      <>
        Protocol: <span className="text-fg">HTTP 402 + BOLT11 Invoice</span>
      </>,
      <>
        Typical Amount: <span className="font-bold text-teal-accent">1,000 Satoshis (~$0.65 USD)</span>
      </>,
      <>
        Security: <span className="text-fg-muted">HMAC SHA-256 Macaroon cryptographic challenge</span>
      </>,
    ],
  },
};

/**
 * Multi-rail settlement explorer — migrated from the legacy Keelway landing page.
 * Shows how Keelway settles compute, licenses, and agent bounties on regional
 * payment rails for engineers excluded from Stripe/USD card billing.
 */
export function SettlementRails() {
  const [rail, setRail] = useState<Rail>("mpesa");
  const detail = DETAILS[rail];

  return (
    <section
      id="settlement"
      aria-labelledby="settlement-heading"
      className="border-t border-border-subtle py-14 sm:py-16"
    >
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <p className="font-mono text-[11px] font-semibold uppercase tracking-wider text-teal-accent">
            SOVEREIGN ECONOMY
          </p>
          <h2
            id="settlement-heading"
            className="mt-2 text-2xl font-bold tracking-tight text-fg sm:text-3xl"
          >
            Sovereignty Beyond US Credit Cards
          </h2>
          <p className="mt-2 text-sm text-fg-muted sm:text-base">
            Over 70% of developers worldwide are excluded from Stripe and USD cards.
            Keelway natively settles compute, licenses, and agent bounties via
            regional rails.
          </p>
        </div>

        <div className="frame-crosshair grid grid-cols-1 gap-6 rounded-lg border border-border-strong bg-surface p-5 sm:p-8 md:grid-cols-5">
          <div
            role="radiogroup"
            aria-label="Payment rail"
            className="space-y-2 font-mono text-xs md:col-span-2"
          >
            {RAILS.map(({ id, name, desc, icon: Icon }) => {
              const active = rail === id;
              return (
                <button
                  key={id}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  onClick={() => {
                    setRail(id);
                    trackEvent("settlement_rail_selected", { rail: id });
                  }}
                  className={cn(
                    "flex min-h-[58px] w-full items-center gap-3 rounded-md border p-3 text-left transition-colors duration-150",
                    active
                      ? "border-teal-accent bg-teal-surface"
                      : "border-border-subtle bg-canvas hover:border-border-strong"
                  )}
                >
                  <Icon
                    className={cn("h-4 w-4 shrink-0", active ? "text-teal-accent" : "text-fg-dim")}
                    aria-hidden={true}
                  />
                  <span className="flex-1">
                    <span className={cn("block font-semibold", active ? "text-fg" : "text-fg-muted")}>
                      {name}
                    </span>
                    <span className="mt-0.5 block text-[10px] text-fg-dim">{desc}</span>
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex flex-col justify-between rounded-md border border-border-subtle bg-canvas p-5 md:col-span-3">
            <div>
              <div className="flex items-center justify-between border-b border-border-subtle pb-3">
                <span className="font-mono text-sm font-bold text-fg">{detail.title}</span>
                <span className="rounded-sm border border-teal-accent bg-teal-surface px-2 py-0.5 font-mono text-[10px] font-semibold uppercase text-teal-accent">
                  Live Rail
                </span>
              </div>
              <div className="mt-3 space-y-1.5 font-mono text-xs text-fg-muted">
                {detail.lines.map((line, i) => (
                  <div key={i}>• {line}</div>
                ))}
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between border-t border-border-subtle pt-3 font-mono text-xs text-fg-muted">
              <span>
                Cloud Token Bill:{" "}
                <strong className="text-fault line-through">$50.00</strong>
              </span>
              <span>
                Keelway Edge Cost:{" "}
                <strong className="font-bold text-teal-accent">$0.00</strong>
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
