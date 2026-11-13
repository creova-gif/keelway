import React from "react";
import Link from "next/link";
import { ArrowUpRight, ShieldCheck } from "lucide-react";

/**
 * Global Multi-Column Footer linking all core platform pages, OpenAPI spec,
 * installer script, Brand Kit, and open-source repository.
 */
export function Footer() {
  return (
    <footer className="border-t border-border-subtle bg-surface/60">
      <div className="mx-auto max-w-container px-4 py-14 sm:px-6">
        <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 lg:grid-cols-5">
          {/* Brand Column */}
          <div className="lg:col-span-2">
            <Link
              href="/"
              aria-label="Keelway home"
              className="inline-flex min-h-[44px] items-center gap-2.5 text-lg font-bold tracking-tight text-fg"
            >
              <svg
                width="28"
                height="28"
                viewBox="0 0 48 48"
                aria-hidden="true"
              >
                <rect width="48" height="48" rx="11" fill="#2DD4BF" />
                <path d="M15 9h7v30H15z" fill="#0B0F14" />
                <path d="M22 24 32 9h7L30 24l9 15h-7z" fill="#0B0F14" />
              </svg>
              <span>Keelway</span>
            </Link>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-fg-muted">
              The sovereign hybrid AI control plane. Run open-weight OpenCore
              models locally alongside governed frontier APIs with deterministic
              4D routing and hash-chained execution proofs.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-sm border border-border-strong bg-canvas px-3 py-2 font-mono text-xs text-fg-muted">
              <ShieldCheck
                className="h-4 w-4 shrink-0 text-teal-accent"
                aria-hidden="true"
              />
              <span>167/167 Engineering Gates Verified · Apache-2.0</span>
            </div>
          </div>

          {/* Platform */}
          <div>
            <h2 className="font-mono text-xs font-semibold uppercase tracking-wider text-fg">
              Platform
            </h2>
            <ul className="mt-3 space-y-1 text-sm">
              <li>
                <Link
                  href="/models"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  Models &amp; OpenCore
                </Link>
              </li>
              <li>
                <Link
                  href="/governance"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  Hybrid Routing &amp; Governance
                </Link>
              </li>
              <li>
                <Link
                  href="/pricing"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  Pricing &amp; VPC Tiers
                </Link>
              </li>
              <li>
                <Link
                  href="/#workflow"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  5-Step Approval Gate
                </Link>
              </li>
            </ul>
          </div>

          {/* Developers */}
          <div>
            <h2 className="font-mono text-xs font-semibold uppercase tracking-wider text-fg">
              Developers
            </h2>
            <ul className="mt-3 space-y-1 text-sm">
              <li>
                <Link
                  href="/docs"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  Documentation
                </Link>
              </li>
              <li>
                <Link
                  href="/api-reference"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  Interactive API Reference
                </Link>
              </li>
              <li>
                <a
                  href="/openapi.json"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-[44px] items-center gap-1 font-mono text-xs text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  <span>openapi.json (v3.1)</span>
                  <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                </a>
              </li>
              <li>
                <a
                  href="/install.sh"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-[44px] items-center gap-1 font-mono text-xs text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  <span>install.sh</span>
                  <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                </a>
              </li>
            </ul>
          </div>

          {/* Open Source & Identity */}
          <div>
            <h2 className="font-mono text-xs font-semibold uppercase tracking-wider text-fg">
              Identity &amp; OSS
            </h2>
            <ul className="mt-3 space-y-1 text-sm">
              <li>
                <Link
                  href="/brand"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  Brand Kit &amp; Tokens
                </Link>
              </li>
              <li>
                <a
                  href="https://github.com/creova-gif/kora"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-[44px] items-center gap-1 text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  <span>GitHub Repository</span>
                  <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                </a>
              </li>
              <li>
                <Link
                  href="/#early-access"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-teal-accent"
                >
                  Enterprise Early Access
                </Link>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Legal & Sovereignty Strip */}
        <div className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-border-subtle pt-6 text-xs text-fg-muted sm:flex-row sm:items-center">
          <p>
            &copy; 2026 Keelway. Open-core platform licensed under{" "}
            <span className="font-mono text-fg">Apache-2.0</span>.
          </p>
          <p className="font-mono text-[11px]">
            local-first · open-weight + frontier · zero unauthorized egress
          </p>
        </div>
      </div>
    </footer>
  );
}
