import React from "react";
import { PLATFORM_VIEWS } from "@/components/platform/PlatformWorkspaceBar";
import type { PlatformViewId } from "@/lib/types";

export interface PlatformViewListProps {
  activeView: PlatformViewId;
  onSelectView: (view: PlatformViewId) => void;
}

export function PlatformViewList({ activeView, onSelectView }: PlatformViewListProps): React.JSX.Element {
  return (
    <nav aria-label="Unified platform views" className="shrink-0 border-b border-border px-2 py-2">
      <p className="px-1 pb-1.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-fg-dim">Views</p>
      <ul className="space-y-0.5">
        {PLATFORM_VIEWS.map((view) => {
          const isActive = activeView === view.id;
          return (
            <li key={view.id}>
              <button
                type="button"
                title={`${view.label} — ${view.capability}`}
                aria-current={isActive ? "page" : undefined}
                onClick={() => onSelectView(view.id)}
                className={`flex w-full items-center rounded-xs border-s-2 px-2 py-1 text-xs transition-colors duration-fast ease-state focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent ${
                  isActive
                    ? "border-s-accent font-semibold text-accent"
                    : "border-s-transparent font-medium text-fg-muted hover:bg-surface hover:text-fg"
                }`}
              >
                {view.label}
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
