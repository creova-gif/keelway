"use client";

import React, { useState } from "react";
import { Check, Copy, Download, ShieldCheck, XCircle } from "lucide-react";
import { trackEvent } from "@/lib/analytics";

interface SwatchSpec {
  token: string;
  hex: string;
  role: string;
  contrastNote?: string;
}

const DARK_SWATCHES: SwatchSpec[] = [
  { token: "--bg-canvas", hex: "#0B0F14", role: "Deep void canvas" },
  { token: "--bg-surface", hex: "#111821", role: "Primary cards & panels" },
  {
    token: "--bg-surface-elevated",
    hex: "#17202B",
    role: "Raised & hover fills",
  },
  {
    token: "--fg-primary",
    hex: "#E6EDF3",
    role: "Primary ink",
    contrastNote: "14.8:1 AAA on #0B0F14",
  },
  {
    token: "--fg-muted",
    hex: "#9AA7B4",
    role: "Secondary metadata",
    contrastNote: "7.5:1 AAA on #0B0F14",
  },
  {
    token: "--teal-accent",
    hex: "#2DD4BF",
    role: "Sovereign action",
    contrastNote: "Chip ink #06201C (10.6:1)",
  },
  {
    token: "--amber-alert",
    hex: "#F5B547",
    role: "Awaiting human gate",
    contrastNote: "Chip ink #2A1C02 (10.4:1)",
  },
  {
    token: "--red-danger",
    hex: "#F87171",
    role: "Fault or removed diff line",
    contrastNote: "Chip ink #2A0606",
  },
];

const LIGHT_SWATCHES: SwatchSpec[] = [
  { token: "--bg-canvas", hex: "#F7F9FB", role: "Clean paper canvas" },
  { token: "--bg-surface", hex: "#FFFFFF", role: "Card surface" },
  {
    token: "--fg-primary",
    hex: "#0B0F14",
    role: "Primary ink",
    contrastNote: "18.1:1 AAA on #FFFFFF",
  },
  {
    token: "--fg-muted",
    hex: "#4A5866",
    role: "Secondary text",
    contrastNote: "7.1:1 AAA on #FFFFFF",
  },
  {
    token: "--teal-accent",
    hex: "#0F766E",
    role: "Sovereign action",
    contrastNote: "Chip ink #FFFFFF (5.4:1 AA)",
  },
  {
    token: "--amber-alert",
    hex: "#B45309",
    role: "Waiting decision",
    contrastNote: "Chip ink #FFFFFF (5.0:1 AA)",
  },
  {
    token: "Chip ink (Amber)",
    hex: "#6F2C0A",
    role: "Light-tint amber label ink",
  },
  {
    token: "Chip ink (Teal)",
    hex: "#0B534E",
    role: "Light-tint teal label ink",
  },
];

const TILE_MARK_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect width="48" height="48" rx="11" fill="#2DD4BF"/><path d="M15 9h7v30H15z" fill="#0B0F14"/><path d="M22 24 32 9h7L30 24l9 15h-7z" fill="#0B0F14"/></svg>`;

const HEADER_LOCKUP_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 48 48"><path d="M7 5h9v38H7z" fill="#E6EDF3"/><path d="M16 26 28 5h9L25.5 27 44 43H32L16 30z" fill="#E6EDF3"/><circle cx="42.5" cy="9" r="4.5" fill="#2DD4BF"/></svg>`;

/**
 * Interactive Brand Identity & Design System Lab (/brand)
 * Preserves 100% of `brand.html` and `DESIGN.md` specifications with
 * click-to-copy tokens, raw SVG copy, and live interactive control specimens.
 */
export function BrandKitLab() {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [specimenText, setSpecimenText] = useState<string>(
    "Sovereign open weights. Verifiable agents."
  );

  const handleCopy = async (
    id: string,
    payload: string,
    kind: "token" | "svg"
  ) => {
    try {
      await navigator.clipboard.writeText(payload);
      setCopiedId(id);
      if (kind === "svg") {
        trackEvent("brand_svg_copied", { asset: id });
      } else {
        trackEvent("brand_token_copied", { token: id });
      }
      window.setTimeout(() => setCopiedId(null), 1800);
    } catch {
      // Ignore clipboard failures
    }
  };

  return (
    <div className="space-y-20">
      {/* ====================================================================
          1. OFFICIAL MARK & WORDMARK LOCKUPS
          ==================================================================== */}
      <section id="mark" aria-labelledby="mark-heading">
        <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
          01 // MARK &amp; LOCKUP
        </p>
        <h2
          id="mark-heading"
          className="mt-2 text-2xl font-bold tracking-tight text-fg"
        >
          Geometric &lsquo;K&rsquo; Mark
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-fg-muted">
          The standalone mark is a geometric <strong className="text-fg">K</strong>{" "}
          cut from a Sovereign Teal tile (<code className="font-mono">#2DD4BF</code>)
          in <code className="font-mono">favicon.svg</code>, keeping strokes at{" "}
          <code className="font-mono">#0B0F14</code> on both dark and light
          surfaces. The header lockup draws the K in the page&apos;s foreground
          color with a standalone teal dot beside the wordmark{" "}
          <strong className="text-fg">Keelway</strong> on its own — never with a
          tagline crammed inside the logo.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
          {/* Dark Surface Specimen */}
          <div
            className="flex flex-col justify-between rounded-lg border border-[#243040] p-6"
            style={{ backgroundColor: "#0B0F14", color: "#E6EDF3" }}
          >
            <div>
              <span className="font-mono text-[11px] uppercase text-[#9AA7B4]">
                Primary Dark Surface (#0B0F14)
              </span>
              <div className="mt-6 flex flex-wrap items-center gap-8">
                {/* Tile Mark */}
                <div className="flex items-center gap-3">
                  <svg
                    width="48"
                    height="48"
                    viewBox="0 0 48 48"
                    role="img"
                    aria-label="Keelway teal tile mark on dark background"
                  >
                    <rect width="48" height="48" rx="11" fill="#2DD4BF" />
                    <path d="M15 9h7v30H15z" fill="#0B0F14" />
                    <path d="M22 24 32 9h7L30 24l9 15h-7z" fill="#0B0F14" />
                  </svg>
                  <span className="text-xl font-bold tracking-tight">
                    Keelway
                  </span>
                </div>

                {/* Header Dot Lockup */}
                <div className="flex items-center gap-2.5 border-l border-[#243040] pl-8">
                  <svg
                    width="32"
                    height="32"
                    viewBox="0 0 48 48"
                    role="img"
                    aria-label="Keelway header dot lockup"
                  >
                    <path d="M7 5h9v38H7z" fill="#E6EDF3" />
                    <path
                      d="M16 26 28 5h9L25.5 27 44 43H32L16 30z"
                      fill="#E6EDF3"
                    />
                    <circle cx="42.5" cy="9" r="4.5" fill="#2DD4BF" />
                  </svg>
                  <span className="text-lg font-bold tracking-tight">
                    Keelway
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-8 flex flex-wrap gap-2 border-t border-[#1C2633] pt-4">
              <button
                type="button"
                onClick={() => handleCopy("tile-svg", TILE_MARK_SVG, "svg")}
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-sm border border-[#243040] bg-[#111821] px-3 font-mono text-xs text-[#E6EDF3] hover:border-[#2DD4BF]"
              >
                {copiedId === "tile-svg" ? (
                  <>
                    <Check
                      className="h-3.5 w-3.5 text-[#2DD4BF]"
                      aria-hidden="true"
                    />
                    <span>Copied Tile SVG</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                    <span>Copy Tile SVG</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={() =>
                  handleCopy("lockup-svg", HEADER_LOCKUP_SVG, "svg")
                }
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-sm border border-[#243040] bg-[#111821] px-3 font-mono text-xs text-[#E6EDF3] hover:border-[#2DD4BF]"
              >
                {copiedId === "lockup-svg" ? (
                  <>
                    <Check
                      className="h-3.5 w-3.5 text-[#2DD4BF]"
                      aria-hidden="true"
                    />
                    <span>Copied Lockup SVG</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                    <span>Copy Header SVG</span>
                  </>
                )}
              </button>

              <a
                href="/favicon.svg"
                download="keelway-mark.svg"
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-sm border border-[#243040] bg-[#111821] px-3 font-mono text-xs text-[#2DD4BF] hover:border-[#2DD4BF]"
              >
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Download favicon.svg</span>
              </a>
            </div>
          </div>

          {/* Light Surface Specimen */}
          <div
            className="flex flex-col justify-between rounded-lg border border-[#CBD5E1] p-6"
            style={{ backgroundColor: "#F7F9FB", color: "#0B0F14" }}
          >
            <div>
              <span className="font-mono text-[11px] uppercase text-[#4A5866]">
                High-Contrast Light Surface (#F7F9FB)
              </span>
              <div className="mt-6 flex flex-wrap items-center gap-8">
                <div className="flex items-center gap-3">
                  <svg
                    width="48"
                    height="48"
                    viewBox="0 0 48 48"
                    role="img"
                    aria-label="Keelway teal tile mark on light background"
                  >
                    <rect width="48" height="48" rx="11" fill="#2DD4BF" />
                    <path d="M15 9h7v30H15z" fill="#0B0F14" />
                    <path d="M22 24 32 9h7L30 24l9 15h-7z" fill="#0B0F14" />
                  </svg>
                  <span className="text-xl font-bold tracking-tight">
                    Keelway
                  </span>
                </div>

                <div className="flex items-center gap-2.5 border-l border-[#CBD5E1] pl-8">
                  <svg
                    width="32"
                    height="32"
                    viewBox="0 0 48 48"
                    role="img"
                    aria-label="Keelway light header lockup"
                  >
                    <path d="M7 5h9v38H7z" fill="#0B0F14" />
                    <path
                      d="M16 26 28 5h9L25.5 27 44 43H32L16 30z"
                      fill="#0B0F14"
                    />
                    <circle cx="42.5" cy="9" r="4.5" fill="#0F766E" />
                  </svg>
                  <span className="text-lg font-bold tracking-tight">
                    Keelway
                  </span>
                </div>
              </div>
            </div>

            <p className="mt-8 border-t border-[#E2E8F0] pt-4 font-mono text-xs text-[#4A5866]">
              Tile inner stroke remains <code>#0B0F14</code> invariant across
              both themes for unmistakable silhouette contrast.
            </p>
          </div>
        </div>
      </section>

      {/* ====================================================================
          2. INTERACTIVE COLOR SWATCHES (DARK & LIGHT SCHEMES)
          ==================================================================== */}
      <section
        id="color"
        aria-labelledby="color-heading"
        className="border-t border-border-subtle pt-14"
      >
        <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
          02 // SEMANTIC COLOR TOKENS
        </p>
        <h2
          id="color-heading"
          className="mt-2 text-2xl font-bold tracking-tight text-fg"
        >
          Click Any Swatch to Copy HEX Value
        </h2>
        <p className="mt-2 max-w-2xl text-sm text-fg-muted">
          Dark is the primary interface scheme. Teal denotes verified local
          execution and primary action; Amber denotes a pending human approval
          decision or external cloud boundary; Red denotes a fault or deleted
          diff line.
        </p>

        {/* Dark Scheme Grid */}
        <h3 className="mt-8 font-mono text-xs font-bold uppercase tracking-wider text-fg">
          Dark Scheme (Default)
        </h3>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {DARK_SWATCHES.map((s) => {
            const key = `dark-${s.token}`;
            return (
              <button
                key={key}
                type="button"
                onClick={() => handleCopy(key, s.hex, "token")}
                className="group flex flex-col justify-between overflow-hidden rounded-md border border-border-strong bg-surface text-left transition-colors duration-150 hover:border-teal-accent"
              >
                <div
                  className="h-20 w-full border-b border-border-subtle"
                  style={{ backgroundColor: s.hex }}
                />
                <div className="p-3">
                  <div className="flex items-center justify-between font-mono text-xs font-bold text-fg">
                    <span>{s.hex}</span>
                    <span className="text-[11px] text-teal-accent">
                      {copiedId === key ? "Copied ✓" : "Copy"}
                    </span>
                  </div>
                  <div className="mt-0.5 font-mono text-[11px] text-fg-muted">
                    {s.token}
                  </div>
                  <div className="mt-1 text-xs text-fg-muted">{s.role}</div>
                  {s.contrastNote && (
                    <div className="mt-1.5 font-mono text-[10px] text-teal-accent">
                      {s.contrastNote}
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* Light Scheme Grid */}
        <h3 className="mt-10 font-mono text-xs font-bold uppercase tracking-wider text-fg">
          Light Scheme (High-Contrast Clean)
        </h3>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {LIGHT_SWATCHES.map((s) => {
            const key = `light-${s.token}`;
            return (
              <button
                key={key}
                type="button"
                onClick={() => handleCopy(key, s.hex, "token")}
                className="group flex flex-col justify-between overflow-hidden rounded-md border border-border-strong bg-surface text-left transition-colors duration-150 hover:border-teal-accent"
              >
                <div
                  className="h-20 w-full border-b border-border-subtle"
                  style={{ backgroundColor: s.hex }}
                />
                <div className="p-3">
                  <div className="flex items-center justify-between font-mono text-xs font-bold text-fg">
                    <span>{s.hex}</span>
                    <span className="text-[11px] text-teal-accent">
                      {copiedId === key ? "Copied ✓" : "Copy"}
                    </span>
                  </div>
                  <div className="mt-0.5 font-mono text-[11px] text-fg-muted">
                    {s.token}
                  </div>
                  <div className="mt-1 text-xs text-fg-muted">{s.role}</div>
                  {s.contrastNote && (
                    <div className="mt-1.5 font-mono text-[10px] text-teal-accent">
                      {s.contrastNote}
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {/* ====================================================================
          3. LIVE VARIABLE FONT SPECIMEN LAB
          ==================================================================== */}
      <section
        id="type"
        aria-labelledby="type-heading"
        className="border-t border-border-subtle pt-14"
      >
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
              03 // SELF-HOSTED VARIABLE TYPOGRAPHY
            </p>
            <h2
              id="type-heading"
              className="mt-2 text-2xl font-bold tracking-tight text-fg"
            >
              Inter + JetBrains Mono (Offline-First)
            </h2>
            <p className="mt-1 max-w-2xl text-sm text-fg-muted">
              Both variable fonts are served directly from this repository — the
              exact files shipped inside Keelway Studio — so pages render
              identically offline with zero Google Fonts network calls.
            </p>
          </div>

          <div className="w-full md:w-80">
            <label
              htmlFor="specimen-input"
              className="block font-mono text-[11px] uppercase text-fg-muted"
            >
              Live Type Specimen Input
            </label>
            <input
              id="specimen-input"
              type="text"
              value={specimenText}
              onChange={(e) => setSpecimenText(e.target.value)}
              className="mt-1 min-h-[44px] w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-fg focus:border-teal-accent"
            />
          </div>
        </div>

        <div className="mt-6 space-y-5 rounded-lg border border-border-strong bg-surface p-6">
          <div className="border-b border-border-subtle pb-4">
            <span className="font-mono text-[11px] text-fg-muted">
              Display Header · Inter 800 · -0.03em tracking
            </span>
            <p className="mt-1 text-3xl font-extrabold tracking-tight text-fg sm:text-4xl">
              {specimenText || "Build with governed agents."}
            </p>
          </div>

          <div className="border-b border-border-subtle pb-4">
            <span className="font-mono text-[11px] text-fg-muted">
              Body Copy · Inter 400 · ~70ch measure · 1.6 line-height
            </span>
            <p className="mt-1 max-w-[70ch] text-[15px] leading-relaxed text-fg-muted">
              Body text stays inside a comfortable ~70-character measure so
              technical architecture docs and security policies read effortlessly
              without eye fatigue.
            </p>
          </div>

          <div>
            <span className="font-mono text-[11px] text-fg-muted">
              Code, AST &amp; Telemetry · JetBrains Mono 500/600 · tabular-nums
            </span>
            <p className="mt-1 font-mono text-sm text-teal-accent">
              edit_file · src/billing/retry.py · sha256:f91a83e54b20c67d ·
              340.12ms · $0.0000
            </p>
          </div>
        </div>
      </section>

      {/* ====================================================================
          4. CONTROLS, MOTION & CANONICAL GUARDRAILS
          ==================================================================== */}
      <section
        id="controls"
        aria-labelledby="controls-heading"
        className="border-t border-border-subtle pt-14"
      >
        <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
          04 // CONTROLS, MOTION &amp; USAGE GUARDRAILS
        </p>
        <h2
          id="controls-heading"
          className="mt-2 text-2xl font-bold tracking-tight text-fg"
        >
          44px Interactive Targets, Crisp 150ms Motion &amp; Brand Rules
        </h2>

        {/* Live Control Row */}
        <div className="mt-6 rounded-lg border border-border-strong bg-surface p-6">
          <p className="text-sm text-fg-muted">
            Buttons, links, and fields maintain at least a{" "}
            <code className="font-mono text-fg">44×44px</code> tap target.
            Keyboard focus renders a{" "}
            <code className="font-mono text-fg">2px solid teal</code> ring{" "}
            <code className="font-mono text-fg">3px</code> outside the control.
            Pressed buttons settle to{" "}
            <code className="font-mono text-fg">scale(0.99)</code>; when{" "}
            <code className="font-mono text-fg">prefers-reduced-motion</code> is
            enabled, transitions and animations shut off completely.
          </p>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button type="button" className="kw-btn kw-btn-primary">
              Primary Action
            </button>
            <button type="button" className="kw-btn kw-btn-secondary">
              Secondary Action
            </button>
            <span className="chip-amber rounded-sm px-2.5 py-1.5">
              NEEDS YOUR DECISION
            </span>
            <span className="chip-teal rounded-sm px-2.5 py-1.5">
              LOCAL OPENCORE
            </span>
            <span className="chip-neutral rounded-sm px-2.5 py-1.5">
              STAGE 7 OF 10
            </span>
          </div>
        </div>

        {/* Keep vs. Leave Alone Rules from brand.html */}
        <div id="rules" className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
          <article className="rounded-lg border border-teal-accent/50 bg-surface p-6">
            <div className="flex items-center gap-2 text-teal-accent">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              <h3 className="text-lg font-bold text-fg">Keep</h3>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-fg-muted">
              The <code className="font-mono text-fg">#2DD4BF</code> teal square
              and the <code className="font-mono text-fg">#0B0F14</code>{" "}
              geometric K cut from it. The wordmark{" "}
              <strong className="text-fg">&ldquo;Keelway&rdquo;</strong> on its
              own, with no tagline stuffed into the lockup. Dark and light
              tokens from the specification above. Code in{" "}
              <code className="font-mono text-fg">JetBrains Mono</code> inside a
              horizontal scroller when wider than the column. Primary navigation
              visible at phone width, wrapped cleanly onto its own row.
            </p>
          </article>

          <article className="rounded-lg border border-fault/50 bg-surface p-6">
            <div className="flex items-center gap-2 text-fault">
              <XCircle className="h-5 w-5" aria-hidden="true" />
              <h3 className="text-lg font-bold text-fg">Leave Alone (Avoid)</h3>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-fg-muted">
              Inventing a second logo, renaming the product arbitrarily, or
              recoloring the K mark in purple/neon gradients. Hiding primary
              navigation destinations (Models, Governance, Docs, API Reference)
              behind inaccessible traps below 820px. Rendering low-contrast 11px
              teal or amber text on a faint translucent chip of the same hue —
              always use high-contrast solid fills with dark ink (
              <code className="font-mono text-fg">#06201C</code> /{" "}
              <code className="font-mono text-fg">#2A1C02</code>).
            </p>
          </article>
        </div>
      </section>
    </div>
  );
}
