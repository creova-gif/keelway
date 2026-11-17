import React from "react";
import Link from "next/link";
import { ArrowUpRight, ShieldCheck } from "lucide-react";
import { BrandMark } from "@/components/ui/BrandMark";

export function Footer() {
  return (
    <footer className="border-t border-border-subtle bg-canvas">
      <div className="mx-auto max-w-container px-4 py-14 sm:px-6">
        <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <Link
              href="/"
              aria-label="Keelway home"
              className="inline-flex min-h-[44px] items-center gap-2.5 text-lg font-bold tracking-tight text-fg"
            >
              <BrandMark size={28} showWordmark />
            </Link>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-fg-muted">
              The unified local-first AI agent platform for developers,
              non-technical builders, startups, and enterprises. Build,
              automate, and govern software and business workflows in one
              workspace.
            </p>
            <div className="mt-5 inline-flex items-center gap-2 rounded-sm border border-border-strong bg-surface px-3 py-2 font-mono text-xs text-fg-muted">
              <ShieldCheck
                className="h-4 w-4 shrink-0 text-teal-accent"
                aria-hidden="true"
              />
              <span>Open-Core Apache-2.0 · Ed25519 Signed Extensions</span>
            </div>
          </div>

          <div>
            <h2 className="font-mono text-xs font-semibold uppercase tracking-wider text-fg">
              Platform
            </h2>
            <ul className="mt-3 space-y-1 text-sm">
              <li>
                <Link
                  href="/#quickstart"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  Local Dev Tool (10 Views)
                </Link>
              </li>
              <li>
                <Link
                  href="/marketplace"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  Signed Marketplace
                </Link>
              </li>
              <li>
                <Link
                  href="/models"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  Models &amp; OpenCore
                </Link>
              </li>
              <li>
                <Link
                  href="/pricing"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  Pricing &amp; BYOM
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h2 className="font-mono text-xs font-semibold uppercase tracking-wider text-fg">
              Developers
            </h2>
            <ul className="mt-3 space-y-1 text-sm">
              <li>
                <Link
                  href="/docs"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  Documentation &amp; SDKs
                </Link>
              </li>
              <li>
                <Link
                  href="/api-reference"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  API Reference
                </Link>
              </li>
              <li>
                <a
                  href="/openapi.json"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-[44px] items-center gap-1 font-mono text-xs text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  <span>openapi.json (v3.1)</span>
                  <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                </a>
              </li>
              <li>
                <a
                  href="/feed.xml"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-[44px] items-center gap-1 font-mono text-xs text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  <span>RSS Feed</span>
                  <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                </a>
              </li>
              <li>
                <Link
                  href="/changelog"
                  className="inline-flex min-h-[44px] items-center gap-1 font-mono text-xs text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  <span>Changelog</span>
                  <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <h2 className="font-mono text-xs font-semibold uppercase tracking-wider text-fg">
              Enterprise &amp; Trust
            </h2>
            <ul className="mt-3 space-y-1 text-sm">
              <li>
                <Link
                  href="/governance"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  Security &amp; Governance
                </Link>
              </li>
              <li>
                <Link
                  href="/docs#surfaces"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  Guided No-Code &amp; Surfaces
                </Link>
              </li>
              <li>
                <Link
                  href="/brand"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  Brand Kit
                </Link>
              </li>
              <li>
                <Link
                  href="/#early-access"
                  className="inline-flex min-h-[44px] items-center text-fg-muted transition-colors duration-150 hover:text-fg"
                >
                  Team &amp; VPC Onboarding
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 flex flex-col items-start justify-between gap-4 border-t border-border-subtle pt-6 text-xs text-fg-muted sm:flex-row sm:items-center">
          <p>
            &copy; 2026 Keelway. Open-core platform licensed under{" "}
            <span className="font-mono text-fg">Apache-2.0</span>.
          </p>
          <p className="font-mono text-[11px]">
            local-first · open-weight + frontier · human-approved execution
          </p>
        </div>
      </div>
    </footer>
  );
}
