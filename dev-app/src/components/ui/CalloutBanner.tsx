import type React from "react";

export type CalloutBannerVariant =
  | "prompt-drift"
  | "chain-verified"
  | "chain-broken"
  | "runtime-unreachable"
  | "spend-warn"
  | "spend-cap";

export interface CalloutBannerProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  variant: CalloutBannerVariant;
  title: React.ReactNode;
  description?: React.ReactNode;
  safeStateNote?: React.ReactNode;
  actions?: React.ReactNode;
}

interface CalloutSpec {
  role: "status" | "alert";
  glyph: string;
  containerClasses: string;
  iconClasses: string;
}

const CALLOUT_SPECS: Record<CalloutBannerVariant, CalloutSpec> = {
  "prompt-drift": {
    role: "status",
    glyph: "!",
    containerClasses: "border-warning/45 bg-warning-subtle text-fg",
    iconClasses: "text-warning border-warning/40 bg-canvas/40",
  },
  "chain-verified": {
    role: "status",
    glyph: "✓",
    containerClasses: "border-ok/40 bg-ok-subtle text-fg",
    iconClasses: "text-ok border-ok/40 bg-canvas/40",
  },
  "chain-broken": {
    role: "alert",
    glyph: "✕",
    containerClasses: "border-danger/50 bg-danger-subtle text-fg",
    iconClasses: "text-danger border-danger/45 bg-canvas/40",
  },
  "runtime-unreachable": {
    role: "status",
    glyph: "!",
    containerClasses: "border-warning/45 bg-warning-subtle text-fg",
    iconClasses: "text-warning border-warning/40 bg-canvas/40",
  },
  "spend-warn": {
    role: "status",
    glyph: "▲",
    containerClasses: "border-warning/45 bg-warning-subtle text-fg",
    iconClasses: "text-warning border-warning/40 bg-canvas/40",
  },
  "spend-cap": {
    role: "alert",
    glyph: "✕",
    containerClasses: "border-danger/50 bg-danger-subtle text-fg",
    iconClasses: "text-danger border-danger/45 bg-canvas/40",
  },
};

/**
 * Persistent recovery & integrity callout banner.
 * By design, CalloutBanner has ZERO auto-dismiss timers so critical governance,
 * prompt-drift, spend-cap, and SHA-256 chain states remain visible until resolved.
 */
export function CalloutBanner({
  variant,
  title,
  description,
  safeStateNote,
  actions,
  className = "",
  ...rest
}: CalloutBannerProps): React.JSX.Element {
  const spec = CALLOUT_SPECS[variant];

  return (
    <div
      role={spec.role}
      data-callout-variant={variant}
      className={`flex flex-wrap items-start justify-between gap-3 rounded-md border px-3.5 py-2.5 text-ui ${spec.containerClasses} ${className}`.trim()}
      {...rest}
    >
      <div className="flex min-w-0 flex-1 items-start gap-2.5">
        <span
          aria-hidden="true"
          className={`mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-xs border font-mono text-xs font-[640] ${spec.iconClasses}`}
        >
          {spec.glyph}
        </span>
        <div className="min-w-0 space-y-0.5">
          <div className="font-semibold text-fg">{title}</div>
          {description ? <div className="text-xs text-fg-muted">{description}</div> : null}
          {safeStateNote ? (
            <div className="font-mono text-[11px] text-fg-dim">{safeStateNote}</div>
          ) : null}
        </div>
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  );
}
