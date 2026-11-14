import React from "react";
import { Button } from "@/components/ui/Button";
import { SUBSCRIPTION_TIERS } from "@/lib/platformData";
import type { ExperienceMode, PlatformViewId, SubscriptionTierId } from "@/lib/types";

export interface PlatformWorkspaceBarProps {
  activeView: PlatformViewId;
  onSelectView: (view: PlatformViewId) => void;
  experienceMode: ExperienceMode;
  onChangeExperienceMode: (mode: ExperienceMode) => void;
  subscriptionTier: SubscriptionTierId;
  onChangeSubscriptionTier: (tier: SubscriptionTierId) => void;
  workspacePath: string;
  workspaceBranch: string;
  activeModelLabel: string;
  pendingApprovalCount: number;
}

const PLATFORM_VIEWS: Array<{ id: PlatformViewId; label: string }> = [
  { id: "ide", label: "IDE" },
  { id: "agents", label: "Agents" },
  { id: "pm", label: "Project Manager" },
  { id: "product", label: "Product" },
  { id: "automation", label: "Automation" },
  { id: "marketplace", label: "Marketplace" },
  { id: "security", label: "Security" },
  { id: "docs", label: "Documentation" },
  { id: "operations", label: "Operations" },
  { id: "nocode", label: "No-Code Builder" },
];

export function PlatformWorkspaceBar({
  activeView,
  onSelectView,
  experienceMode,
  onChangeExperienceMode,
  subscriptionTier,
  onChangeSubscriptionTier,
  workspacePath,
  workspaceBranch,
  activeModelLabel,
  pendingApprovalCount,
}: PlatformWorkspaceBarProps): React.JSX.Element {
  const tierMeta = SUBSCRIPTION_TIERS[subscriptionTier];

  return (
    <section
      aria-label="Unified workspace bar"
      className="flex shrink-0 flex-col gap-1.5 border-b border-border bg-chrome px-3 py-2 text-xs"
    >
      {/* Top Row: Shared Project Context Pill + Persona Switcher + Tier/BYOM Pill */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5 rounded-sm border border-border-strong bg-surface px-2.5 py-1 font-mono text-[11px] text-fg-muted">
          <code dir="ltr" className="unicode-bidi-isolate text-fg">
            {workspacePath}
          </code>
          <span aria-hidden="true">·</span>
          <span>
            <span aria-hidden="true" className="me-0.5">
              ⎇
            </span>
            <code dir="ltr" className="unicode-bidi-isolate text-fg">
              {workspaceBranch}
            </code>
          </span>
          <span aria-hidden="true">·</span>
          <code dir="ltr" className="unicode-bidi-isolate">
            {activeModelLabel}
          </code>
          <span aria-hidden="true">·</span>
          <span className="text-teal-accent font-medium">Zero Context Loss</span>
          {pendingApprovalCount > 0 ? (
            <span className="ms-1 rounded-xs border border-ochre/40 bg-ochre-subtle px-1.5 py-0.5 text-[10px] font-semibold text-ochre">
              {`${pendingApprovalCount} P-10 pending`}
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div
            role="group"
            aria-label="Experience persona"
            className="inline-flex items-center rounded-sm border border-border-control/70 bg-surface p-0.5"
          >
            <button
              type="button"
              aria-pressed={experienceMode === "builder"}
              onClick={() => onChangeExperienceMode("builder")}
              className={`rounded-xs px-2 py-0.5 text-[11px] font-medium transition-colors ${
                experienceMode === "builder"
                  ? "bg-teal-surface text-teal-accent"
                  : "text-fg-muted hover:text-fg"
              }`}
            >
              Builder
            </button>
            <button
              type="button"
              aria-pressed={experienceMode === "non_coder"}
              onClick={() => onChangeExperienceMode("non_coder")}
              className={`rounded-xs px-2 py-0.5 text-[11px] font-medium transition-colors ${
                experienceMode === "non_coder"
                  ? "bg-teal-surface text-teal-accent"
                  : "text-fg-muted hover:text-fg"
              }`}
            >
              Guided Non-Coder
            </button>
          </div>

          {experienceMode === "non_coder" && activeView !== "nocode" ? (
            <Button size="sm" variant="primary" onClick={() => onSelectView("nocode")}>
              Open No-Code Builder
            </Button>
          ) : null}

          <div className="inline-flex items-center gap-1.5 rounded-sm border border-border-control/70 bg-surface px-2 py-0.5">
            <span className="font-mono text-[10px] uppercase tracking-wide text-fg-dim">Tier</span>
            <select
              aria-label="Subscription tier"
              value={subscriptionTier}
              onChange={(e) => onChangeSubscriptionTier(e.target.value as SubscriptionTierId)}
              className="bg-transparent font-mono text-[11px] font-semibold text-teal-accent focus:outline-none"
            >
              <option value="community">Community</option>
              <option value="pro">Pro</option>
              <option value="byom">BYOM · 0% Markup</option>
              <option value="enterprise">Enterprise</option>
            </select>
            <span className="hidden font-mono text-[10px] text-fg-dim xl:inline">
              {tierMeta.priceLabel}
            </span>
          </div>
        </div>
      </div>

      {/* Bottom Row: 10-View Unified Platform Switcher */}
      <nav
        aria-label="Unified platform views"
        className="flex flex-wrap items-center gap-1"
      >
        {PLATFORM_VIEWS.map((view) => {
          const isActive = activeView === view.id;
          return (
            <button
              key={view.id}
              type="button"
              aria-current={isActive ? "page" : undefined}
              onClick={() => onSelectView(view.id)}
              className={`rounded-sm border px-2.5 py-1 text-xs font-medium transition-colors ${
                isActive
                  ? "border-teal-accent/50 bg-teal-surface text-teal-accent"
                  : "border-transparent text-fg-muted hover:border-border-strong hover:bg-surface hover:text-fg"
              }`}
            >
              {view.label}
            </button>
          );
        })}
      </nav>
    </section>
  );
}
