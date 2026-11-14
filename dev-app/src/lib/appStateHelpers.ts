import {
  DEFAULT_MODELS_AND_SETTINGS,
  type CommandPaletteSettingItem,
} from "@/components/shell/CommandPalette";
import { getFallbackDiffHunks } from "@/lib/apiFallbacks";
import type {
  FileDiffHunk,
  OpenCoreWeightItem,
  P10ApprovalProposal,
  RailSection,
  SettingsSubSection,
  SidebarTaskItem,
  StepReceiptItem,
} from "@/lib/types";

function isRailSection(val: string | null): val is RailSection {
  return val === "tasks" || val === "files" || val === "record" || val === "settings";
}

function isSettingsSubSection(val: string | null): val is SettingsSubSection {
  return (
    val === "permissions" ||
    val === "models" ||
    val === "governance" ||
    val === "network" ||
    val === "appearance" ||
    val === "labs" ||
    val === "general" ||
    val === "keyboard"
  );
}

export function readInitialUrlState(): {
  section?: RailSection;
  settings?: SettingsSubSection;
  companion: boolean;
  onboarding: boolean;
} {
  if (typeof window === "undefined") {
    return { companion: false, onboarding: false };
  }
  try {
    const params = new URLSearchParams(window.location.search);
    const rawSection = params.get("section");
    const rawSettings = params.get("settings");
    return {
      section: isRailSection(rawSection) ? rawSection : undefined,
      settings: isSettingsSubSection(rawSettings) ? rawSettings : undefined,
      companion: params.get("companion") === "1",
      onboarding: params.get("onboarding") === "1",
    };
  } catch {
    return { companion: false, onboarding: false };
  }
}

export const INITIAL_TASKS: SidebarTaskItem[] = [
  {
    id: "task-csp-gate",
    title: "Harden loopback CSP & verify Studio token middleware",
    status: "needs_approval",
    branch: "feat/unified-dev-app",
    modelLabel: "coder-7b v2.5.1",
    updatedAt: "2m ago",
    pendingApprovalId: "prop-csp-pytest",
    filesChangedCount: 1,
  },
  {
    id: "task-merkle-audit",
    title: "Audit SHA-256 Merkle inclusion proofs",
    status: "ready",
    branch: "feat/unified-dev-app",
    modelLabel: "coder-7b v2.5.1",
    updatedAt: "14m ago",
    filesChangedCount: 0,
  },
];

export const INITIAL_PROPOSALS: P10ApprovalProposal[] = [
  {
    id: "prop-csp-pytest",
    taskId: "task-csp-gate",
    kind: "command",
    title: "Run pytest Studio CSP suite",
    summary: "Execute isolated pytest verification over Studio strict CSP and loopback auth.",
    whyReason: "Confirm X-Content-Type-Options and strict 'self' CSP headers pass before commit.",
    command: "pytest tests/test_studio.py -q",
    workingDir: "/workspace/keelway",
    previewStatus: "ready",
    modelId: "coder-7b",
    modelVersion: "2.5.1",
    promptVersion: "p-14",
    confidence: "Medium",
    createdAt: "2026-11-14T02:14:20Z",
    recordSeqCandidate: 1284,
  },
];

export const INITIAL_STEP_RECEIPTS: StepReceiptItem[] = [
  {
    id: "step-read-main",
    kind: "read",
    title: "Read file",
    target: "core/main.py",
    status: "ready",
    recordSeq: 1281,
  },
  {
    id: "step-edit-csp",
    kind: "edited",
    title: "Edited file",
    target: "core/main.py",
    linesAdded: 3,
    linesRemoved: 1,
    status: "ready",
    recordSeq: 1283,
  },
];

export function buildPaletteModelsAndSettings(
  weights: OpenCoreWeightItem[],
): CommandPaletteSettingItem[] {
  const settingsItems = DEFAULT_MODELS_AND_SETTINGS.filter((item) => item.kind === "settings");
  const baseModels = DEFAULT_MODELS_AND_SETTINGS.filter((item) => item.kind === "model");
  const seenModelIds = new Set(baseModels.map((m) => m.modelId).filter(Boolean));

  const dynamicModels: CommandPaletteSettingItem[] = [];
  for (const w of weights) {
    if (seenModelIds.has(w.id)) continue;
    seenModelIds.add(w.id);
    const displayLabel = `${w.name} v${w.version}`;
    dynamicModels.push({
      id: `model-${w.id.replace(/[^a-z0-9]+/gi, "-")}`,
      label: `Local OpenCore · ${displayLabel}`,
      kind: "model",
      detail: `Loopback 127.0.0.1 · ${w.quantization} · ${w.vramGb.toFixed(1)} GB unified memory`,
      modelId: w.id,
      modelLabel: displayLabel,
    });
  }

  return [...baseModels, ...dynamicModels, ...settingsItems];
}

export function mergeFocusedDiffHunks(
  existing: FileDiffHunk[],
  incoming: FileDiffHunk[],
  diffPath: string,
  seq?: number,
): FileDiffHunk[] {
  const merged: FileDiffHunk[] = [];
  const seen = new Set<string>();

  for (const hunk of [...incoming, ...existing]) {
    const key = `${hunk.path}:${hunk.oldStart}:${hunk.newStart}`;
    if (!seen.has(key)) {
      seen.add(key);
      merged.push(hunk);
    }
  }

  if (!merged.some((h) => h.path === diffPath)) {
    const fallbackMatch = getFallbackDiffHunks().filter((h) => h.path === diffPath);
    if (fallbackMatch.length > 0) {
      merged.unshift(...fallbackMatch);
    } else {
      merged.unshift({
        path: diffPath,
        oldStart: 1,
        newStart: 1,
        additions: 0,
        deletions: 0,
        ...(typeof seq === "number" ? { aiRecordSeq: seq } : {}),
        lines: [
          { type: "hunk", content: "@@ -1,1 +1,1 @@" },
          {
            type: "context",
            oldLine: 1,
            newLine: 1,
            content: `Recorded ledger change on ${diffPath}`,
          },
        ],
      });
    }
  }

  const focused = merged.filter((h) => h.path === diffPath);
  const others = merged.filter((h) => h.path !== diffPath);
  return [...focused, ...others];
}
