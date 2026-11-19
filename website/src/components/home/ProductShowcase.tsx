"use client";

import React, { useState } from "react";
import { Camera } from "lucide-react";
import { trackEvent } from "@/lib/analytics";

const SHOTS = [
  {
    id: "ide",
    label: "IDE & P-10 Gate",
    src: "/product/app-main.png",
    alt: "Keelway Sovereign Agent IDE showing a P-10 human approval gate for a pytest run, execution receipts, and Golden Thread stage bar",
    caption:
      "P-10 human approval gate on a workspace command — allow once, allow scoped, edit, or deny with a ledger-recorded reason.",
  },
  {
    id: "kflow",
    label: "KFlow Studio",
    src: "/product/app-automation.png",
    alt: "Bidirectional KFlow topology studio showing a DAG blueprint synced to live Python AST code with P-10 node locks",
    caption:
      "Bidirectional KFlow ⇄ AST split studio — every graph node maps to an exact source span; P-10 locks are per-node.",
  },
  {
    id: "security",
    label: "Security Posture",
    src: "/product/app-security.png",
    alt: "Security governance view with compliance framework evaluator, workspace secret scanner, and dual-human P-10 quorum controls",
    caption:
      "Security & governance surface — compliance-framework evaluation, secret scanning, and 2-of-2 dual-human quorum.",
  },
] as const;

type ShotId = (typeof SHOTS)[number]["id"];

/**
 * Real product screenshot showcase — captured live from `keelway dev` (/app).
 */
export function ProductShowcase() {
  const [active, setActive] = useState<ShotId>("ide");
  const shot = SHOTS.find((s) => s.id === active) ?? SHOTS[0];

  return (
    <section
      aria-labelledby="product-showcase-heading"
      className="relative border-t border-border-subtle bg-canvas py-16 sm:py-24"
    >
      <span className="kw-section-index" aria-hidden="true">
        01 / PROOF
      </span>
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <span className="kw-kicker inline-flex items-center gap-1.5 rounded-sm border border-border-strong bg-surface px-3 py-1 text-fg-muted">
              <Camera className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
              ACTUAL PRODUCT — CAPTURED FROM keelway dev
            </span>
            <h2
              id="product-showcase-heading"
              className="kw-h2 mt-4 text-fg"
            >
              This is the running product,
              <br className="hidden sm:block" /> not a mockup.
            </h2>
          </div>
          <div
            role="tablist"
            aria-label="Product views"
            className="inline-flex shrink-0 gap-1 rounded-md border border-border-strong bg-surface p-1"
          >
            {SHOTS.map((s) => (
              <button
                key={s.id}
                role="tab"
                aria-selected={active === s.id}
                onClick={() => {
                  setActive(s.id);
                  trackEvent("product_showcase_tab", { view: s.id });
                }}
                className={
                  active === s.id
                    ? "min-h-[40px] rounded-sm bg-teal-surface px-3 font-mono text-xs font-semibold text-teal-accent"
                    : "min-h-[40px] rounded-sm px-3 font-mono text-xs text-fg-muted hover:text-fg"
                }
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        <figure className="mt-8">
          <div
            role="tabpanel"
            className="frame-crosshair frame-teal-rule overflow-hidden rounded-lg border border-border-strong bg-surface"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={shot.src}
              alt={shot.alt}
              width={1440}
              height={900}
              loading="lazy"
              decoding="async"
              className="block h-auto w-full"
            />
          </div>
          <figcaption className="mt-3 font-mono text-xs text-fg-muted">
            {shot.caption}
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
