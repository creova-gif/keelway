"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Moon, Search, Sun, Terminal } from "lucide-react";
import { useTheme } from "./ThemeProvider";
import { openCommandPalette } from "./CommandPalette";
import { BrandMark } from "@/components/ui/BrandMark";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

export interface NavItem {
  label: string;
  href: string;
}

export const PRIMARY_NAV: NavItem[] = [
  { label: "Marketplace", href: "/marketplace" },
  { label: "Models & OpenCore", href: "/models" },
  { label: "Routing & Governance", href: "/governance" },
  { label: "Pricing", href: "/pricing" },
  { label: "Docs", href: "/docs" },
  { label: "API Reference", href: "/api-reference" },
];

export function Header() {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="sticky top-0 z-50 border-b border-border-subtle bg-canvas/85 backdrop-blur-md">
      <div className="mx-auto max-w-container px-4 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-3 lg:flex-nowrap">
          <Link
            href="/"
            aria-label="Keelway home"
            className="inline-flex min-h-[44px] shrink-0 items-center gap-2 rounded-sm pr-1 text-lg font-bold tracking-tight text-fg transition-opacity duration-150 hover:opacity-90"
          >
            <BrandMark size={28} showWordmark />
          </Link>

          <div className="flex shrink-0 items-center gap-1.5 lg:order-3">
            <button
              type="button"
              onClick={openCommandPalette}
              aria-label="Search models, API endpoints, and docs (Command+K)"
              title="Instant Search (⌘K / Ctrl+K)"
              className="inline-flex min-h-[44px] items-center gap-1.5 rounded-sm border border-border-strong bg-surface px-2.5 font-mono text-xs text-fg-muted transition-colors duration-150 hover:border-fg-dim hover:text-fg"
            >
              <Search className="h-3.5 w-3.5 text-fg-muted" aria-hidden="true" />
              <span className="hidden 2xl:inline">Search</span>
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
              className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-sm border border-border-strong bg-surface text-fg-muted transition-colors duration-150 hover:border-fg-dim hover:text-fg"
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
              className="kw-btn kw-btn-secondary hidden whitespace-nowrap px-3 text-[13px] xl:inline-flex"
            >
              <Terminal className="h-4 w-4 text-fg-muted" aria-hidden="true" />
              <span>Quickstart</span>
            </Link>

            <Link
              href="/#early-access"
              onClick={() =>
                trackEvent("cta_early_access_clicked", { location: "header" })
              }
              className="kw-btn kw-btn-primary whitespace-nowrap px-3.5 text-[13px]"
            >
              <span>Request Access</span>
            </Link>
          </div>

          <nav
            aria-label="Primary"
            className="order-3 flex w-full items-center gap-0.5 overflow-x-auto border-t border-border-subtle pt-2 lg:order-2 lg:w-auto lg:border-t-0 lg:pt-0"
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
                    "inline-flex min-h-[44px] shrink-0 items-center whitespace-nowrap rounded-sm px-2.5 text-[13px] font-medium transition-colors duration-150",
                    isActive
                      ? "bg-surface-elevated text-fg"
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
