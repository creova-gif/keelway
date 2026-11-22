"use client";

import { useState } from "react";
import { ControlPlaneFigure } from "@/components/site/ControlPlaneFigure";

const TABS = [
  {
    variant: "gate" as const,
    tab: "FIG 1.0 — Gate",
    caption: "FIG 1.0 — Control plane gate, live demo. Allow once or Deny — either way it seals.",
  },
  {
    variant: "flow" as const,
    tab: "FIG 1.1 — Flow",
    caption: "FIG 1.1 — KFlow run graph, sample render. Every edge writes to the tape.",
  },
  {
    variant: "policy" as const,
    tab: "FIG 1.2 — Policy",
    caption: "FIG 1.2 — Policy engine, sample render. Denials are sealed, not silent.",
  },
];

/**
 * Kit 09.3 feature carousel — accent-underlined tab switcher over the three
 * figure variants. No auto-advance; manual control only, reduced-motion safe.
 */
export function FigureTabs() {
  const [active, setActive] = useState(0);

  return (
    <div>
      <div role="tablist" aria-label="Product figures" className="flex flex-wrap gap-1 border-b border-[var(--rule)]">
        {TABS.map((t, i) => (
          <button
            key={t.variant}
            type="button"
            role="tab"
            aria-selected={active === i}
            aria-controls={`fig-panel-${t.variant}`}
            id={`fig-tab-${t.variant}`}
            className={`kw-navlink px-3 py-2.5 ${active === i ? "text-[var(--ink)]" : ""}`}
            data-active={active === i ? "true" : undefined}
            onClick={() => setActive(i)}
          >
            <span className="kw-data text-[10px]">{t.tab}</span>
          </button>
        ))}
      </div>
      {TABS.map((t, i) => (
        <figure
          key={t.variant}
          id={`fig-panel-${t.variant}`}
          role="tabpanel"
          aria-labelledby={`fig-tab-${t.variant}`}
          hidden={active !== i}
          className={active === i ? "mt-6" : ""}
        >
          {active === i ? (
            <div className="kw-land">
              <ControlPlaneFigure variant={t.variant} />
            </div>
          ) : null}
          <figcaption className="kw-figcap mt-3">{t.caption}</figcaption>
        </figure>
      ))}
    </div>
  );
}
