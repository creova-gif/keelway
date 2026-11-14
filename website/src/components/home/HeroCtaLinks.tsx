"use client";

import React from "react";
import Link from "next/link";
import { ArrowRight, Sparkles, Terminal } from "lucide-react";
import { trackEvent } from "@/lib/analytics";

export function HeroCtaLinks() {
  return (
    <div className="mt-8 flex flex-wrap items-center gap-3">
      <Link
        href="/playground"
        onClick={() =>
          trackEvent("cta_quickstart_clicked", { location: "hero_playground" })
        }
        className="kw-btn kw-btn-primary"
      >
        <Sparkles className="h-4 w-4" aria-hidden="true" />
        <span>Try 10-View Playground</span>
        <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>
      <Link
        href="#quickstart"
        onClick={() =>
          trackEvent("cta_quickstart_clicked", { location: "hero_primary" })
        }
        className="kw-btn kw-btn-secondary"
      >
        <Terminal className="h-4 w-4 text-teal-accent" aria-hidden="true" />
        <span>Install in 60 Seconds</span>
      </Link>
    </div>
  );
}
