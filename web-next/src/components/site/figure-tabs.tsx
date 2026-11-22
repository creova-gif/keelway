"use client";

import { useState } from "react";
import { ControlPlaneFigure } from "@/components/site/control-plane-figure";

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

export function FigureTabs() {
  const [active, setActive] = useState(0);

  return (
    <div>
      <div role="tablist" aria-label="Product figures" className="flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t, i) => (
          <button
            key={t.variant}
            type="button"
            role="tab"
            aria-selected={active === i}
            aria-controls={`fig-panel-${t.variant}`}
            id={`fig-tab-${t.variant}`}
            className="kw-underline px-3 py-2.5"
            data-active={active === i ? "true" : undefined}
            onClick={() => setActive(i)}
          >
            <span className={`font-mono text-[10px] ${active === i ? "text-fg" : "text-fg-muted"}`}>{t.tab}</span>
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
          <figcaption className="mt-3 font-mono text-[10px] text-fg-muted">{t.caption}</figcaption>
        </figure>
      ))}
    </div>
  );
}
