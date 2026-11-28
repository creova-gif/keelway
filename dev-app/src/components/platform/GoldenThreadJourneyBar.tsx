import React from "react";
import type { ExperienceMode, PlatformViewId } from "@/lib/types";

export type GoldenStageId = "plan_import" | "build_sync" | "scrub_blast" | "govern_ship";

export interface GoldenThreadJourneyBarProps {
  activeView: PlatformViewId;
  onSelectView: (view: PlatformViewId) => void;
  experienceMode: ExperienceMode;
}

interface GoldenStageSpec {
  id: GoldenStageId;
  stepNumber: string;
  shortLabel: string;
  fullLabel: string;
  subtitle: string;
  views: ReadonlyArray<PlatformViewId>;
}

const GOLDEN_STAGES: ReadonlyArray<GoldenStageSpec> = [
  {
    id: "plan_import",
    stepNumber: "01",
    shortLabel: "Plan & Import",
    fullLabel: "01 Plan & Import",
    subtitle: "No-Code · PRD · Sprint",
    views: ["nocode", "product", "pm"],
  },
  {
    id: "build_sync",
    stepNumber: "02",
    shortLabel: "Build & Sync Studio",
    fullLabel: "02 Build & Sync Studio",
    subtitle: "IDE · KFlow ↔ AST",
    views: ["ide", "automation"],
  },
  {
    id: "scrub_blast",
    stepNumber: "03",
    shortLabel: "Scrub & Blast-Radius",
    fullLabel: "03 Scrub & Blast-Radius",
    subtitle: "Flight-Tape · Chat · Seatbelt",
    views: ["agents", "chat"],
  },
  {
    id: "govern_ship",
    stepNumber: "04",
    shortLabel: "Govern & Ship",
    fullLabel: "04 Govern & Ship",
    subtitle: "P-10 · SBOM · Fleet",
    views: ["security", "marketplace", "operations", "docs"],
  },
];

export function resolveGoldenStageId(view: PlatformViewId): GoldenStageId {
  switch (view) {
    case "nocode":
    case "product":
    case "pm":
      return "plan_import";
    case "ide":
    case "automation":
      return "build_sync";
    case "agents":
    case "chat":
      return "scrub_blast";
    case "security":
    case "marketplace":
    case "operations":
    case "docs":
      return "govern_ship";
    default: {
      const _exhaustive: never = view;
      return _exhaustive;
    }
  }
}

export function resolvePrimaryStageView(stageId: GoldenStageId, experienceMode: ExperienceMode): PlatformViewId {
  switch (stageId) {
    case "plan_import":
      return experienceMode === "non_coder" ? "nocode" : "product";
    case "build_sync":
      return "automation";
    case "scrub_blast":
      return "agents";
    case "govern_ship":
      return "security";
    default: {
      const _exhaustive: never = stageId;
      return _exhaustive;
    }
  }
}

export function GoldenThreadJourneyBar({
  activeView,
  onSelectView,
  experienceMode,
}: GoldenThreadJourneyBarProps): React.JSX.Element {
  const activeStageId = resolveGoldenStageId(activeView);
  const activeIdx = GOLDEN_STAGES.findIndex((s) => s.id === activeStageId);
  const resolvedIdx = activeIdx >= 0 ? activeIdx : 0;
  const nextStage = GOLDEN_STAGES[(resolvedIdx + 1) % GOLDEN_STAGES.length]!;

  return (
    <div
      role="region"
      aria-label="Golden-thread lifecycle journey"
      className="flex flex-wrap items-center gap-0.5"
    >
      <span aria-hidden="true" className="me-0.5 font-mono text-[10px] text-fg-dim">
        ◈
      </span>
      {GOLDEN_STAGES.map((stage, idx) => {
        const isActive = stage.id === activeStageId;
        const isCompleted = idx < resolvedIdx;

        const tone = isActive
          ? stage.id === "govern_ship"
            ? "font-semibold text-ochre"
            : "font-semibold text-accent"
          : isCompleted
            ? "text-fg hover:text-accent"
            : "text-fg-dim hover:text-fg";

        return (
          <React.Fragment key={stage.id}>
            <button
              type="button"
              aria-label={stage.fullLabel}
              aria-current={isActive ? "step" : undefined}
              title={`${stage.fullLabel} · ${stage.subtitle}`}
              onClick={() => onSelectView(resolvePrimaryStageView(stage.id, experienceMode))}
              className={`inline-flex items-baseline gap-1 rounded-xs px-1 py-0.5 font-mono text-[10px] transition-colors duration-fast ease-state focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent ${tone}`}
            >
              <span aria-hidden="true" className="text-fg-dim">
                {isCompleted ? "✓" : stage.stepNumber}
              </span>
              <span>{stage.shortLabel}</span>
            </button>

            {idx < GOLDEN_STAGES.length - 1 ? (
              <span
                aria-hidden="true"
                className={`px-0.5 font-mono text-[10px] select-none ${
                  idx < resolvedIdx ? "text-accent" : "text-fg-dim"
                }`}
              >
                →
              </span>
            ) : null}
          </React.Fragment>
        );
      })}

      <button
        type="button"
        aria-label="Advance golden thread stage"
        onClick={() => onSelectView(resolvePrimaryStageView(nextStage.id, experienceMode))}
        className="ms-1 inline-flex items-center gap-1 rounded-xs px-1 py-0.5 font-mono text-[10px] text-accent underline-offset-2 transition-colors duration-fast ease-state hover:underline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
      >
        <span>{`Next in Golden Thread: ${nextStage.shortLabel} →`}</span>
      </button>
    </div>
  );
}
