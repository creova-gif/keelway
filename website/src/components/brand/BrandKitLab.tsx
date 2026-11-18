"use client";

import React, { useState } from "react";
import { Check, Copy, Download, ShieldCheck, XCircle } from "lucide-react";
import {
  BrandMark,
  DARK_SWATCHES,
  LIGHT_SWATCHES,
  serializeFaviconSvg,
  serializeWordmarkLockupSvg,
} from "@/components/ui/BrandMark";
import { trackEvent } from "@/lib/analytics";

const TILE_MARK_SVG = serializeFaviconSvg();
const HEADER_LOCKUP_SVG = serializeWordmarkLockupSvg("dark");

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
      return;
    }
  };

  return (
    <div className="space-y-20">
      <section id="mark" aria-labelledby="mark-heading">
        <p className="font-mono text-xs font-semibold uppercase tracking-wider text-teal-accent">
          01 // MARK &amp; LOCKUP
        </p>
        <h2
          id="mark-heading"
          className="mt-2 text-2xl font-bold tracking-tight text-fg"
        >
          Geometric &lsquo;K&rsquo; Mark &amp; Wordmark Lockup
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-fg-muted">
          Keelway standardizes a single geometric <strong className="text-fg">K</strong>{" "}
          with a standalone teal dot (<code className="font-mono">#2DD4BF</code>{" "}
          dark / <code className="font-mono">#0F766E</code> light) beside the{" "}
          <strong className="text-fg">Keelway</strong> wordmark across headers,
          footers, Keelway Studio, and the Web Console — never with a tagline
          crammed inside the lockup. Standalone app icons and{" "}
          <code className="font-mono">favicon.svg</code> place the{" "}
          <code className="font-mono">#FAFAFA</code> geometric K and{" "}
          <code className="font-mono">#2DD4BF</code> dot inside a monochrome{" "}
          <code className="font-mono">#09090B</code> rounded tile.
        </p>

        <div className="mt-8 grid grid-cols-1 gap-6 md:grid-cols-2">
          <div
            className="flex flex-col justify-between rounded-lg border border-[#3F3F46] p-6"
            style={{ backgroundColor: "#09090B", color: "#FAFAFA" }}
          >
            <div>
              <span className="font-mono text-[11px] uppercase text-[#A1A1AA]">
                Primary Dark Surface (#09090B)
              </span>
              <div className="mt-6 flex flex-wrap items-center gap-8">
                <div className="flex items-center gap-3">
                  <BrandMark
                    size={48}
                    variant="tile"
                    aria-label="Keelway app icon tile mark on dark background"
                  />
                  <span className="text-xl font-bold tracking-tight">
                    Keelway
                  </span>
                </div>

                <div className="flex items-center gap-2.5 border-l border-[#27272A] pl-8 text-lg">
                  <BrandMark
                    size={32}
                    showWordmark
                    themeOverride="dark"
                    aria-label="Keelway dark wordmark lockup"
                  />
                </div>
              </div>
            </div>

            <div className="mt-8 flex flex-wrap gap-2 border-t border-[#27272A] pt-4">
              <button
                type="button"
                onClick={() => handleCopy("tile-svg", TILE_MARK_SVG, "svg")}
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-sm border border-[#3F3F46] bg-[#121215] px-3 font-mono text-xs text-[#FAFAFA] hover:border-[#2DD4BF]"
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
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-sm border border-[#3F3F46] bg-[#121215] px-3 font-mono text-xs text-[#FAFAFA] hover:border-[#2DD4BF]"
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
                className="inline-flex min-h-[40px] items-center gap-1.5 rounded-sm border border-[#3F3F46] bg-[#121215] px-3 font-mono text-xs text-[#2DD4BF] hover:border-[#2DD4BF]"
              >
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Download favicon.svg</span>
              </a>
            </div>
          </div>

          <div
            className="flex flex-col justify-between rounded-lg border border-[#D4D4D8] p-6"
            style={{ backgroundColor: "#FAFAFA", color: "#09090B" }}
          >
            <div>
              <span className="font-mono text-[11px] uppercase text-[#52525B]">
                High-Contrast Light Surface (#FAFAFA)
              </span>
              <div className="mt-6 flex flex-wrap items-center gap-8">
                <div className="flex items-center gap-3">
                  <BrandMark
                    size={48}
                    variant="tile"
                    aria-label="Keelway app icon tile mark on light background"
                  />
                  <span className="text-xl font-bold tracking-tight">
                    Keelway
                  </span>
                </div>

                <div className="flex items-center gap-2.5 border-l border-[#D4D4D8] pl-8 text-lg">
                  <BrandMark
                    size={32}
                    showWordmark
                    themeOverride="light"
                    aria-label="Keelway light wordmark lockup"
                  />
                </div>
              </div>
            </div>

            <p className="mt-8 border-t border-[#E4E4E7] pt-4 font-mono text-xs text-[#52525B]">
              In-page headers and footers render the K in{" "}
              <code>currentColor</code> with the teal dot; standalone app icons
              use the <code>#09090B</code> rounded tile across both themes.
            </p>
          </div>
        </div>
      </section>

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
          Dark monochrome zinc (<code className="font-mono">#09090B</code>) is
          the primary interface scheme, paired with a clean light canvas (
          <code className="font-mono">#FAFAFA</code>). Teal (
          <code className="font-mono">#2DD4BF</code> dark /{" "}
          <code className="font-mono">#0F766E</code> light) is reserved strictly
          for the K-dot mark, primary CTA, and keyboard focus ring; secondary
          badges and surfaces stay in high-contrast monochrome zinc.
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
            <span className="chip-neutral rounded-sm px-2.5 py-1.5">
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

        <div id="rules" className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-2">
          <article className="rounded-lg border border-teal-accent/50 bg-surface p-6">
            <div className="flex items-center gap-2 text-teal-accent">
              <ShieldCheck className="h-5 w-5" aria-hidden="true" />
              <h3 className="text-lg font-bold text-fg">Keep</h3>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-fg-muted">
              The standardized geometric <strong className="text-fg">K</strong>{" "}
              with the standalone teal dot (<code className="font-mono text-fg">#2DD4BF</code>{" "}
              dark / <code className="font-mono text-fg">#0F766E</code> light)
              beside the wordmark{" "}
              <strong className="text-fg">&ldquo;Keelway&rdquo;</strong> on its
              own, with no tagline stuffed into the lockup. Monochrome zinc
              dark (<code className="font-mono text-fg">#09090B</code>) and
              light (<code className="font-mono text-fg">#FAFAFA</code>)
              surfaces that reserve teal strictly for the logo dot, primary CTA,
              and focus ring. Code in{" "}
              <code className="font-mono text-fg">JetBrains Mono</code> and
              primary navigation visible at phone width.
            </p>
          </article>

          <article className="rounded-lg border border-fault/50 bg-surface p-6">
            <div className="flex items-center gap-2 text-fault">
              <XCircle className="h-5 w-5" aria-hidden="true" />
              <h3 className="text-lg font-bold text-fg">Leave Alone (Avoid)</h3>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-fg-muted">
              Inventing a second logo, using a filled teal square background
              tile in headers or footers, or scattering competing yellow/amber/blue
              accents across secondary badges and sliders. Hiding primary
              navigation destinations (Models, Governance, Docs, API Reference)
              behind inaccessible traps below 820px. Rendering low-contrast 11px
              text on a faint translucent chip — always use high-contrast
              monochrome zinc or solid teal fills with{" "}
              <code className="font-mono text-fg">#042F2E</code> /{" "}
              <code className="font-mono text-fg">#FFFFFF</code> ink.
            </p>
          </article>
        </div>
      </section>
    </div>
  );
}
