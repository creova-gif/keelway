"use client";

import React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { trackEvent } from "@/lib/analytics";

export function HeroCtaLinks() {
  return (
    <div className="mt-8 flex flex-wrap items-center gap-3">
      <Link
        href="#quickstart"
        onClick={() =>
          trackEvent("cta_quickstart_clicked", { location: "hero_primary" })
        }
        className="kw-btn kw-btn-primary"
      >
        <span>Start in 60 Seconds</span>
        <ArrowRight className="h-4 w-4" aria-hidden="true" />
      </Link>
      <Link
        href="/models"
        onClick={() =>
          trackEvent("cta_early_access_clicked", {
            location: "hero_explore_models",
          })
        }
        className="kw-btn kw-btn-secondary"
      >
        <span>Explore OpenCore &amp; Frontier Models</span>
      </Link>
    </div>
  );
}
