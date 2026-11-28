import React from "react";

export interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Small muted label above the value, e.g. "Platform fee" */
  label: string;
  /** Primary metric — rendered in the mono tabular display style */
  value: React.ReactNode;
  /** Optional secondary line under the value (delta, caption, unit note) */
  delta?: React.ReactNode;
  /** Render the value in the accent tone (e.g. savings callouts) */
  emphasis?: boolean;
  /** Bordered canvas chrome (default). Pass `false` inside an already-framed `<dl>`. */
  framed?: boolean;
}

/**
 * Metric tile: muted label over a mono tabular value.
 * Emits `<dt>`/`<dd>` inside the cell `<div>` — mount inside a `<dl>` (the
 * valid HTML grouping for term/description lists).
 */
export function StatCard({ label, value, delta, emphasis, framed = true, className, ...rest }: StatCardProps) {
  return (
    <div
      className={[framed ? "rounded-sm border border-border bg-canvas p-3" : "", className]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      <dt className="text-[11px] text-fg-muted">{label}</dt>
      <dd
        className={[
          "mt-1 font-mono text-sm font-semibold tabular-nums",
          emphasis ? "text-accent" : "text-fg",
        ].join(" ")}
      >
        <code dir="ltr" className="unicode-bidi-isolate">
          {value}
        </code>
        {delta ? (
          <span className="mt-0.5 block font-sans text-[11px] font-normal leading-4 text-fg-dim">
            {delta}
          </span>
        ) : null}
      </dd>
    </div>
  );
}
