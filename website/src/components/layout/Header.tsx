"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Github, Moon, Search, Sun, Terminal } from "lucide-react";
import { useTheme } from "./ThemeProvider";
import { openCommandPalette } from "./CommandPalette";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

export interface NavItem {
  label: string;
  href: string;
}

export const PRIMARY_NAV: NavItem[] = [
  { label: "Playground", href: "/playground" },
  { label: "Marketplace", href: "/marketplace" },
  { label: "Models & OpenCore", href: "/models" },
  { label: "Routing & Governance", href: "/governance" },
  { label: "Pricing", href: "/pricing" },
  { label: "Docs", href: "/docs" },
  { label: "API Reference", href: "/api-reference" },
];

/**
 * Sticky Global Header following DESIGN.md & brand.html specifications:
 * - Official geometric 'K' lockup with standalone teal dot + "Keelway" wordmark alone.
 * - Primary navigation remains visible on mobile wrapped onto its own accessible row
 *   (never hidden below 820px), with >= 44px touch targets.
 */
export function Header() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-50 border-b border-border-subtle bg-canvas/90 backdrop-blur-md">
      {/* Top Status Telemetry Bar */}
      <div className="border-b border-border-subtle bg-surface/70">
        <div className="mx-auto flex max-w-container items-center justify-between gap-4 px-4 py-1.5 text-xs sm:px-6">
          <div className="flex items-center gap-2 font-mono text-[11px] text-fg-muted">
            <span
              className="inline-block h-2 w-2 rounded-full bg-teal-accent"
              aria-hidden="true"
            />
            <span>KEELWAY v1 HYBRID ENGINE</span>
            <span className="hidden sm:inline text-fg-dim">·</span>
            <span className="hidden sm:inline">
              OPENCORE WEIGHTS + FRONTIER APIS + HASH-CHAINED AUDIT
            </span>
          </div>
          <div className="flex items-center gap-3 font-mono text-[11px]">
            <a
              href="https://github.com/creova-gif/kora"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-fg-muted transition-colors duration-150 hover:text-teal-accent"
            >
              <Github className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Apache-2.0</span>
            </a>
          </div>
        </div>
      </div>

      {/* Main Navigation Row */}
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 py-3">
          {/* Official Keelway Brand Lockup (brand.html canonical SVG) */}
          <Link
            href="/"
            aria-label="Keelway home"
            className="inline-flex min-h-[44px] items-center gap-2.5 rounded-sm pr-2 text-lg font-bold tracking-tight text-fg transition-opacity duration-150 hover:opacity-90"
          >
            <svg
              width="30"
              height="30"
              viewBox="0 0 48 48"
              aria-hidden="true"
              className="shrink-0"
            >
              <path d="M7 5h9v38H7z" fill="currentColor" />
              <path
                d="M16 26 28 5h9L25.5 27 44 43H32L16 30z"
                fill="currentColor"
              />
              <circle cx="42.5" cy="9" r="4.5" fill="var(--teal-accent)" />
            </svg>
            <span>Keelway</span>
          </Link>

          {/* Right Action Controls */}
          <div className="flex items-center gap-2 lg:order-3">
            <button
              type="button"
              onClick={openCommandPalette}
              aria-label="Search models, API endpoints, and docs (Command+K)"
              title="Instant Search (⌘K / Ctrl+K)"
              className="inline-flex min-h-[44px] items-center gap-2 rounded-sm border border-border-strong bg-surface px-3 font-mono text-xs text-fg-muted transition-colors duration-150 hover:border-teal-accent hover:text-fg"
            >
              <Search className="h-3.5 w-3.5 text-teal-accent" aria-hidden="true" />
              <span className="hidden md:inline">Search</span>
              <kbd className="rounded-sm border border-border-subtle bg-canvas px-1.5 py-0.5 text-[10px] font-semibold text-fg">
                ⌘K
              </kbd>
            </button>

            <button
              type="button"
              onClick={toggleTheme}
              aria-label={
                theme === "dark"
                  ? "Switch to light color theme"
                  : "Switch to dark color theme"
              }
              title={
                theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
              }
              className="inline-flex h-11 w-11 items-center justify-center rounded-sm border border-border-strong bg-surface text-fg-muted transition-colors duration-150 hover:border-teal-accent hover:text-fg"
            >
              {theme === "dark" ? (
                <Sun className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Moon className="h-4 w-4" aria-hidden="true" />
              )}
            </button>

            <Link
              href="/#quickstart"
              onClick={() =>
                trackEvent("cta_quickstart_clicked", { location: "header" })
              }
              className="kw-btn kw-btn-secondary hidden sm:inline-flex"
            >
              <Terminal className="h-4 w-4 text-teal-accent" aria-hidden="true" />
              <span>Quickstart</span>
            </Link>

            <Link
              href="/#early-access"
              onClick={() =>
                trackEvent("cta_early_access_clicked", { location: "header" })
              }
              className="kw-btn kw-btn-primary"
            >
              <span>Request Access</span>
            </Link>
          </div>

          {/* Primary Navigation — Always Visible, Wraps Cleanly at Phone Width per brand.html */}
          <nav
            aria-label="Primary"
            className="order-3 flex w-full items-center gap-1 overflow-x-auto border-t border-border-subtle pt-2 lg:order-2 lg:w-auto lg:border-t-0 lg:pt-0"
          >
            {PRIMARY_NAV.map((item) => {
              const isActive =
                pathname === item.href ||
                (item.href !== "/" && pathname?.startsWith(item.href));
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "inline-flex min-h-[44px] shrink-0 items-center rounded-sm px-3 text-sm font-medium transition-colors duration-150",
                    isActive
                      ? "bg-surface-elevated text-teal-accent"
                      : "text-fg-muted hover:bg-surface hover:text-fg"
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>
    </header>
  );
}
