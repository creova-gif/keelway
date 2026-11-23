import type React from "react";

export type SemanticBadgeKind =
  // Status (9)
  | "needs-approval"
  | "running"
  | "queued"
  | "done"
  | "ready"
  | "passed"
  | "failed"
  | "reconfirm"
  | "not-saved"
  // Epistemic (5)
  | "live"
  | "estimated"
  | "simulated"
  | "prototype"
  | "unmeasured"
  // Provenance (4)
  | "ai"
  | "opencore"
  | "frontier"
  | "locked";

export interface SemanticBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  kind: SemanticBadgeKind;
  detail?: string;
  labelOverride?: string;
}

interface BadgeSpec {
  glyph: string;
  label: string;
  classes: string;
}

const BADGE_SPECS: Record<SemanticBadgeKind, BadgeSpec> = {
  // Status badges
  "needs-approval": {
    glyph: "●",
    label: "Needs approval",
    classes: "text-ochre bg-ochre-subtle border-ochre/40",
  },
  running: {
    glyph: "ⓘ",
    label: "Running",
    classes: "text-running bg-running-subtle border-running/40",
  },
  queued: {
    glyph: "○",
    label: "Queued",
    classes: "text-fg-muted bg-surface-elevated border-border-control/50",
  },
  done: {
    glyph: "✓",
    label: "Done",
    classes: "text-fg-muted bg-surface-elevated border-border-strong",
  },
  ready: {
    glyph: "○",
    label: "Ready",
    classes: "text-fg-muted bg-surface-elevated border-border-strong",
  },
  passed: {
    glyph: "✓",
    label: "Passed",
    classes: "text-ok bg-ok-subtle border-ok/40",
  },
  failed: {
    glyph: "✗",
    label: "Failed",
    classes: "text-danger bg-danger-subtle border-danger/45",
  },
  reconfirm: {
    glyph: "!",
    label: "Re-confirm",
    classes: "text-warning bg-warning-subtle border-warning/45",
  },
  "not-saved": {
    glyph: "▲",
    label: "Not saved",
    classes: "text-warning bg-warning-subtle border-warning/45",
  },

  // Epistemic honesty badges
  live: {
    glyph: "✓",
    label: "Live",
    classes: "text-ok bg-ok-subtle border-ok/40",
  },
  estimated: {
    glyph: "≈",
    label: "Estimated",
    classes: "text-fg-muted bg-surface-elevated border-border-control/60",
  },
  simulated: {
    glyph: "▨",
    label: "Simulated",
    classes: "kw-badge-simulated text-fg-muted bg-surface-elevated border-border-control",
  },
  prototype: {
    glyph: "◇",
    label: "Prototype",
    classes: "text-warning bg-warning-subtle border-warning/40",
  },
  unmeasured: {
    glyph: "∅",
    label: "No counter yet",
    classes: "text-fg-muted bg-surface-elevated border-border-strong",
  },

  // Provenance badges
  ai: {
    glyph: "✦",
    label: "AI",
    classes: "text-accent bg-accent-subtle border-accent/40",
  },
  opencore: {
    glyph: "▣",
    label: "OpenCore",
    classes: "text-accent bg-accent-subtle border-accent/40",
  },
  frontier: {
    glyph: "↗",
    label: "Frontier",
    classes: "text-fg-muted bg-surface-elevated border-border-control/60",
  },
  locked: {
    glyph: "⚿",
    label: "Locked",
    classes: "text-fg-muted bg-surface-elevated border-border-control",
  },
};

export function SemanticBadge({
  kind,
  detail,
  labelOverride,
  className = "",
  ...rest
}: SemanticBadgeProps): React.JSX.Element {
  const spec = BADGE_SPECS[kind];

  let computedLabel = labelOverride ?? spec.label;
  if (!labelOverride && detail) {
    computedLabel = kind === "ai" ? `AI ${detail}` : `${spec.label} · ${detail}`;
  }

  return (
    <span
      data-badge-kind={kind}
      className={`inline-flex items-center gap-1 rounded-xs border px-1.5 py-0.5 font-mono text-badge font-medium whitespace-nowrap select-none ${spec.classes} ${className}`.trim()}
      {...rest}
    >
      <span aria-hidden="true" data-badge-glyph="" className="leading-none">
        {spec.glyph}
      </span>
      <span>{computedLabel}</span>
    </span>
  );
}
