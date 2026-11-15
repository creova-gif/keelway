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
    subtitle: "Flight-Tape · Seatbelt",
    views: ["agents"],
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
      className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border-strong bg-canvas/85 px-2.5 py-1.5"
    >
      <div className="flex flex-wrap items-center gap-1">
        <span className="me-1 hidden items-center gap-1 rounded-xs border border-teal-accent/35 bg-teal-surface px-1.5 py-0.5 font-mono text-[10px] font-semibold tracking-wide text-teal-accent xl:inline-flex">
          <span aria-hidden="true">◈</span>
          <span>GOLDEN THREAD</span>
        </span>

        {GOLDEN_STAGES.map((stage, idx) => {
          const isActive = stage.id === activeStageId;
          const isCompleted = idx < resolvedIdx;
          const isGovernanceStage = stage.id === "govern_ship";

          const pillTone = isActive
            ? isGovernanceStage
              ? "border-ochre/65 bg-ochre-subtle text-ochre shadow-[0_0_12px_rgba(229,169,60,0.18)]"
              : "border-teal-accent/65 bg-teal-surface text-teal-accent shadow-[0_0_12px_rgba(45,212,191,0.18)]"
            : isCompleted
              ? "border-teal-accent/30 bg-surface text-fg hover:border-teal-accent/55"
              : "border-border-strong bg-surface text-fg-muted hover:border-border-control hover:text-fg";

          return (
            <React.Fragment key={stage.id}>
              <button
                type="button"
                aria-current={isActive ? "step" : undefined}
                onClick={() => onSelectView(resolvePrimaryStageView(stage.id, experienceMode))}
                className={`group inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 text-[11px] transition-all focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-accent ${pillTone}`}
              >
                <span
                  aria-hidden="true"
                  className={`inline-flex h-4 min-w-[20px] items-center justify-center rounded-xs px-1 font-mono text-[10px] font-bold ${
                    isActive
                      ? isGovernanceStage
                        ? "bg-ochre text-ochre-ink"
                        : "bg-teal-accent text-teal-ink"
                      : isCompleted
                        ? "bg-teal-surface text-teal-accent"
                        : "bg-chrome text-fg-dim"
                  }`}
                >
                  {isCompleted ? "✓" : stage.stepNumber}
                </span>
                <span className="font-semibold">{stage.fullLabel}</span>
                <span className="hidden font-mono text-[10px] opacity-80 2xl:inline">{`· ${stage.subtitle}`}</span>
              </button>

              {idx < GOLDEN_STAGES.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={`px-0.5 font-mono text-[11px] select-none ${
                    idx < resolvedIdx ? "text-teal-accent" : "text-fg-dim"
                  }`}
                >
                  →
                </span>
              ) : null}
            </React.Fragment>
          );
        })}
      </div>

      <button
        type="button"
        aria-label="Advance golden thread stage"
        onClick={() => onSelectView(resolvePrimaryStageView(nextStage.id, experienceMode))}
        className="inline-flex min-h-ctrl-sm items-center gap-1.5 rounded-sm border border-teal-accent/50 bg-teal-surface px-2.5 py-0.5 font-mono text-[11px] font-semibold text-teal-accent transition-colors hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal-accent"
      >
        <span>{`Next in Golden Thread: ${nextStage.shortLabel} →`}</span>
      </button>
    </div>
  );
}
