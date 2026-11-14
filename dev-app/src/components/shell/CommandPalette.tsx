import React, { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "@/components/ui/Button";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import type {
  CodeSymbolItem,
  SettingsSubSection,
  SidebarTaskItem,
  TaskStatus,
  WorkspaceFileNode,
} from "@/lib/types";

export interface CommandPaletteActionItem {
  id: string;
  label: string;
  category: "kstack" | "workspace" | "audit" | "network";
  description?: string;
  shortcut?: string;
}

export interface CommandPaletteSettingItem {
  id: string;
  label: string;
  kind: "model" | "settings";
  detail: string;
  settingsSection?: SettingsSubSection;
  modelId?: string;
}

export interface CommandPaletteProps {
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  commands?: CommandPaletteActionItem[];
  tasks?: SidebarTaskItem[];
  files?: WorkspaceFileNode[];
  symbols?: CodeSymbolItem[];
  modelsAndSettings?: CommandPaletteSettingItem[];
  onRunCommand?: (commandId: string) => void;
  onSelectTask?: (taskId: string) => void;
  onJumpToApprovalHeading?: () => void;
  onSelectFile?: (filePath: string) => void;
  onSelectSymbol?: (symbol: CodeSymbolItem) => void;
  onSelectSettingOrModel?: (item: CommandPaletteSettingItem) => void;
  initialQuery?: string;
  disableGlobalShortcut?: boolean;
}

const DEFAULT_COMMANDS: CommandPaletteActionItem[] = [
  {
    id: "kstack-office-hours",
    label: "/office-hours — Reframe product problem & scope",
    category: "kstack",
    description: "Run KStack product framing review",
  },
  {
    id: "kstack-review",
    label: "/review — Pre-landing diff & gate integrity review",
    category: "kstack",
    description: "Run KStack staff engineer code review",
  },
  {
    id: "kstack-ship",
    label: "/ship — Verify gates, test suite & release readiness",
    category: "kstack",
    description: "Prepare workspace branch for delivery",
  },
  {
    id: "verify-chain",
    label: "Verify chain",
    category: "audit",
    description: "Re-verify SHA-256 hash chain & Merkle root in Record",
  },
  {
    id: "toggle-air-gap",
    label: "Toggle Air-Gap",
    category: "network",
    description: "Switch OS-enforced air-gap socket lock",
  },
  {
    id: "switch-local-model",
    label: "Switch to local OpenCore model",
    category: "network",
    description: "Route active workspace tasks to coder-7b v2.5.1 on 127.0.0.1",
  },
];

const DEFAULT_MODELS_AND_SETTINGS: CommandPaletteSettingItem[] = [
  {
    id: "model-coder-7b",
    label: "Local OpenCore runtime",
    kind: "model",
    detail: "Loopback 127.0.0.1 · Q4_K_M · 0 B external egress",
    modelId: "coder-7b v2.5.1",
  },
  {
    id: "settings-permissions",
    label: "Settings · Permissions & Scoped Rules",
    kind: "settings",
    detail: "Review P-10 human-only gates and prompt-bound scopes",
    settingsSection: "permissions",
  },
  {
    id: "settings-models",
    label: "Settings · Models & 4D Routing",
    kind: "settings",
    detail: "Inspect OpenCore weights and dry-run routing policies",
    settingsSection: "models",
  },
  {
    id: "settings-governance",
    label: "Settings · Governance & Residency",
    kind: "settings",
    detail: "Data residency zones, budget caps, and scoped API keys",
    settingsSection: "governance",
  },
  {
    id: "settings-network",
    label: "Settings · Network & Air-Gap",
    kind: "settings",
    detail: "Offline setting, egress verification, and endpoint audit",
    settingsSection: "network",
  },
  {
    id: "settings-appearance",
    label: "Settings · Appearance, Density & Locale",
    kind: "settings",
    detail: "Dark/Light theme, Compact/Comfortable density, RTL locale",
    settingsSection: "appearance",
  },
];

const FORBIDDEN_APPROVAL_PATTERN = /\b(allow once|allow always|deny|approve proposal)\b/i;

const TASK_STATUS_PRIORITY: Record<TaskStatus, number> = {
  needs_approval: 0,
  running: 1,
  queued: 2,
  ready: 3,
  failed: 4,
  done: 5,
};

const TASK_BADGE_MAP: Record<TaskStatus, SemanticBadgeKind> = {
  needs_approval: "needs-approval",
  running: "running",
  queued: "queued",
  done: "done",
  ready: "ready",
  failed: "failed",
};

interface FlattenedFileItem {
  path: string;
  name: string;
  gitStatus?: string;
}

function flattenWorkspaceFiles(nodes: WorkspaceFileNode[]): FlattenedFileItem[] {
  const acc: FlattenedFileItem[] = [];
  const visit = (list: WorkspaceFileNode[]) => {
    for (const node of list) {
      if (node.type === "file") {
        acc.push({ path: node.path, name: node.name, gitStatus: node.gitStatus });
      }
      if (node.children && node.children.length > 0) {
        visit(node.children);
      }
    }
  };
  visit(nodes);
  return acc;
}

type PaletteMode = "mixed" | "commands" | "tasks" | "symbols" | "settings";

interface PaletteEntry {
  key: string;
  group: "Commands" | "Tasks" | "Files" | "Symbols" | "Models & Settings";
  primaryLabel: string;
  codeTarget?: string;
  secondaryDetail?: string;
  shortcut?: string;
  badgeKind?: SemanticBadgeKind;
  onActivate: () => void;
}

function formatMissingMixedSections(missing: string[], term: string): string {
  if (missing.length === 0) {
    return "";
  }
  const normalized = missing.map((name, idx) =>
    idx === 0 ? name : name.toLowerCase(),
  );
  const joined =
    normalized.length === 1
      ? normalized[0]
      : `${normalized.slice(0, -1).join(", ")} and ${normalized[normalized.length - 1]}`;
  return `${joined}: no matches for "${term}"`;
}

export function CommandPalette({
  open: controlledOpen,
  onOpenChange,
  commands = DEFAULT_COMMANDS,
  tasks = [],
  files = [],
  symbols = [],
  modelsAndSettings = DEFAULT_MODELS_AND_SETTINGS,
  onRunCommand,
  onSelectTask,
  onJumpToApprovalHeading,
  onSelectFile,
  onSelectSymbol,
  onSelectSettingOrModel,
  initialQuery = "",
  disableGlobalShortcut = false,
}: CommandPaletteProps): React.JSX.Element {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false);
  const [query, setQuery] = useState(initialQuery);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const inputRef = useRef<HTMLInputElement | null>(null);
  const baseId = useId();
  const listboxId = `${baseId}-listbox`;
  const descId = `${baseId}-desc`;

  const isOpen = controlledOpen ?? uncontrolledOpen;

  const setOpen = useCallback(
    (next: boolean) => {
      if (controlledOpen === undefined) {
        setUncontrolledOpen(next);
      }
      if (next) {
        setQuery(initialQuery);
        setSelectedIndex(0);
      }
      onOpenChange?.(next);
    },
    [controlledOpen, initialQuery, onOpenChange],
  );

  useEffect(() => {
    if (disableGlobalShortcut) {
      return;
    }
    const handleGlobalKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return;
      if (
        (event.metaKey || event.ctrlKey) &&
        !event.shiftKey &&
        !event.altKey &&
        event.key.toLowerCase() === "k"
      ) {
        event.preventDefault();
        setOpen(!isOpen);
      }
    };
    window.addEventListener("keydown", handleGlobalKey);
    return () => window.removeEventListener("keydown", handleGlobalKey);
  }, [disableGlobalShortcut, isOpen, setOpen]);

  // Enforce P-10 safety invariant: strip any approval action verbs even if passed via props
  const safeCommands = useMemo(
    () =>
      commands.filter(
        (cmd) =>
          !FORBIDDEN_APPROVAL_PATTERN.test(cmd.id) &&
          !FORBIDDEN_APPROVAL_PATTERN.test(cmd.label),
      ),
    [commands],
  );

  const sortedTasks = useMemo(
    () =>
      tasks
        .map((item, idx) => ({ item, idx }))
        .sort((a, b) => {
          const diff =
            TASK_STATUS_PRIORITY[a.item.status] - TASK_STATUS_PRIORITY[b.item.status];
          return diff !== 0 ? diff : a.idx - b.idx;
        })
        .map(({ item }) => item),
    [tasks],
  );

  const flatFiles = useMemo(() => flattenWorkspaceFiles(files), [files]);

  const { mode, searchTerm } = useMemo((): { mode: PaletteMode; searchTerm: string } => {
    const raw = query.trimStart();
    if (raw.startsWith(">")) {
      return { mode: "commands", searchTerm: raw.slice(1).trim() };
    }
    if (raw.startsWith("#")) {
      return { mode: "tasks", searchTerm: raw.slice(1).trim() };
    }
    if (raw.startsWith("@")) {
      return { mode: "symbols", searchTerm: raw.slice(1).trim() };
    }
    if (raw.startsWith("/")) {
      return { mode: "settings", searchTerm: raw.slice(1).trim() };
    }
    return { mode: "mixed", searchTerm: raw.trim() };
  }, [query]);

  const { groups, flatEntries, partialEmptyNotice } = useMemo(() => {
    const needle = searchTerm.toLowerCase();
    const matches = (haystack: string) =>
      needle.length === 0 || haystack.toLowerCase().includes(needle);

    const buildCommandEntries = (): PaletteEntry[] =>
      safeCommands
        .filter((c) => matches(`${c.label} ${c.description ?? ""} ${c.id}`))
        .map((c) => ({
          key: `cmd-${c.id}`,
          group: "Commands",
          primaryLabel: c.label,
          secondaryDetail: c.description,
          shortcut: c.shortcut,
          onActivate: () => {
            onRunCommand?.(c.id);
            setOpen(false);
          },
        }));

    const buildTaskEntries = (): PaletteEntry[] =>
      sortedTasks
        .filter((t) => matches(`${t.title} ${t.branch ?? ""} ${t.id}`))
        .map((t) => ({
          key: `task-${t.id}`,
          group: "Tasks",
          primaryLabel: t.title,
          codeTarget: t.branch,
          badgeKind: TASK_BADGE_MAP[t.status],
          onActivate: () => {
            // P-10 invariant: selecting a Needs approval task ONLY navigates; it NEVER approves.
            onSelectTask?.(t.id);
            if (t.status === "needs_approval") {
              onJumpToApprovalHeading?.();
            }
            setOpen(false);
          },
        }));

    const buildFileEntries = (): PaletteEntry[] =>
      flatFiles
        .filter((f) => matches(`${f.path} ${f.name}`))
        .map((f) => ({
          key: `file-${f.path}`,
          group: "Files",
          primaryLabel: f.name,
          codeTarget: f.path,
          secondaryDetail: f.gitStatus ? `Git ${f.gitStatus}` : undefined,
          onActivate: () => {
            onSelectFile?.(f.path);
            setOpen(false);
          },
        }));

    const buildSymbolEntries = (): PaletteEntry[] =>
      symbols
        .filter((s) => matches(`${s.name} ${s.kind} ${s.path} ${s.signature ?? ""}`))
        .map((s) => ({
          key: `sym-${s.path}-${s.line}-${s.name}`,
          group: "Symbols",
          primaryLabel: s.name,
          codeTarget: `${s.path}:${s.line}`,
          secondaryDetail: s.kind,
          onActivate: () => {
            onSelectSymbol?.(s);
            setOpen(false);
          },
        }));

    const buildSettingEntries = (): PaletteEntry[] =>
      modelsAndSettings
        .filter((m) => matches(`${m.label} ${m.detail} ${m.modelId ?? ""}`))
        .map((m) => ({
          key: `set-${m.id}`,
          group: "Models & Settings",
          primaryLabel: m.label,
          codeTarget: m.modelId,
          secondaryDetail: m.detail,
          badgeKind: m.kind === "model" ? "opencore" : undefined,
          onActivate: () => {
            onSelectSettingOrModel?.(m);
            setOpen(false);
          },
        }));

    const nextGroups: Array<{ label: PaletteEntry["group"]; items: PaletteEntry[] }> = [];
    let partialNotice = "";

    if (mode === "commands") {
      const items = buildCommandEntries();
      if (items.length > 0) nextGroups.push({ label: "Commands", items });
    } else if (mode === "tasks") {
      const items = buildTaskEntries();
      if (items.length > 0) nextGroups.push({ label: "Tasks", items });
    } else if (mode === "symbols") {
      const items = buildSymbolEntries();
      if (items.length > 0) nextGroups.push({ label: "Symbols", items });
    } else if (mode === "settings") {
      const items = buildSettingEntries();
      if (items.length > 0) nextGroups.push({ label: "Models & Settings", items });
    } else {
      const cmdItems = buildCommandEntries();
      const taskItems = buildTaskEntries();
      const fileItems = buildFileEntries();

      if (cmdItems.length > 0) nextGroups.push({ label: "Commands", items: cmdItems });
      if (taskItems.length > 0) nextGroups.push({ label: "Tasks", items: taskItems });
      if (fileItems.length > 0) nextGroups.push({ label: "Files", items: fileItems });

      const totalCount = cmdItems.length + taskItems.length + fileItems.length;
      if (needle.length > 0 && totalCount > 0) {
        const missing: string[] = [];
        if (cmdItems.length === 0) missing.push("Commands");
        if (taskItems.length === 0) missing.push("Tasks");
        if (fileItems.length === 0) missing.push("Files");
        partialNotice = formatMissingMixedSections(missing, searchTerm);
      }
    }

    const flattened = nextGroups.flatMap((g) => g.items);
    return {
      groups: nextGroups,
      flatEntries: flattened,
      partialEmptyNotice: partialNotice,
    };
  }, [
    flatFiles,
    mode,
    modelsAndSettings,
    onJumpToApprovalHeading,
    onRunCommand,
    onSelectFile,
    onSelectSettingOrModel,
    onSelectSymbol,
    onSelectTask,
    safeCommands,
    searchTerm,
    setOpen,
    sortedTasks,
    symbols,
  ]);

  const clampedIndex =
    flatEntries.length === 0
      ? -1
      : Math.min(Math.max(selectedIndex, 0), flatEntries.length - 1);

  const activeOptionId =
    clampedIndex >= 0 && flatEntries[clampedIndex]
      ? `${baseId}-opt-${flatEntries[clampedIndex].key}`
      : undefined;

  const handleInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (flatEntries.length > 0) {
        setSelectedIndex((prev) => (prev + 1) % flatEntries.length);
      }
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (flatEntries.length > 0) {
        setSelectedIndex(
          (prev) => (prev - 1 + flatEntries.length) % flatEntries.length,
        );
      }
      return;
    }

    if (event.key === "Enter") {
      if (clampedIndex >= 0 && flatEntries[clampedIndex]) {
        event.preventDefault();
        flatEntries[clampedIndex].onActivate();
      }
    }
  };

  const displayEmptyQuery = searchTerm || query.trim();

  // Map each entry key to its global index for O(1) active state lookup
  const entryIndexMap = useMemo(() => {
    const map = new Map<string, number>();
    flatEntries.forEach((entry, idx) => map.set(entry.key, idx));
    return map;
  }, [flatEntries]);

  return (
    <Dialog.Root open={isOpen} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/60" />
        <Dialog.Content
          aria-describedby={descId}
          className="fixed start-1/2 top-[14%] z-50 flex w-full max-w-xl -translate-x-1/2 flex-col overflow-hidden rounded-md border border-border-strong bg-surface text-fg shadow-modal rtl:translate-x-1/2"
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Dialog.Description id={descId} className="sr-only">
            Navigate tasks, files, AST symbols, KStack skills, and sovereign settings.
            Approvals are never run from here.
          </Dialog.Description>

          {/* Search Combobox Bar */}
          <div className="flex items-center gap-2 border-b border-border px-3 py-2.5">
            <span aria-hidden="true" className="font-mono text-xs text-teal-accent">
              ⌘K
            </span>
            <input
              ref={inputRef}
              type="text"
              role="combobox"
              aria-label="Search commands, tasks, files, symbols, and settings"
              aria-expanded={flatEntries.length > 0 ? "true" : "false"}
              aria-controls={listboxId}
              aria-autocomplete="list"
              aria-activedescendant={activeOptionId}
              value={query}
              placeholder="Type > commands, # tasks, @ symbols, / models & settings…"
              onChange={(e) => {
                setQuery(e.target.value);
                setSelectedIndex(0);
              }}
              onKeyDown={handleInputKeyDown}
              className="w-full bg-transparent text-ui text-fg placeholder:text-fg-dim focus:outline-none"
            />
          </div>

          {/* Prefix Mode Chips */}
          <div className="flex flex-wrap items-center gap-1.5 border-b border-border bg-chrome px-3 py-1.5 font-mono text-[11px] text-fg-muted">
            <span>Prefixes:</span>
            <code dir="ltr" className="unicode-bidi-isolate rounded-xs bg-surface px-1 py-0.5">
              &gt; commands
            </code>
            <code dir="ltr" className="unicode-bidi-isolate rounded-xs bg-surface px-1 py-0.5">
              # tasks
            </code>
            <code dir="ltr" className="unicode-bidi-isolate rounded-xs bg-surface px-1 py-0.5">
              @ symbols
            </code>
            <code dir="ltr" className="unicode-bidi-isolate rounded-xs bg-surface px-1 py-0.5">
              / settings
            </code>
          </div>

          {/* Results Listbox */}
          <div className="max-h-80 overflow-y-auto p-2">
            <div
              id={listboxId}
              role="listbox"
              aria-label="Command palette results"
              className={flatEntries.length === 0 ? "sr-only" : "space-y-2"}
            >
              {groups.map((group) => (
                <div
                  key={group.label}
                  role="group"
                  aria-label={group.label}
                  className="space-y-0.5"
                >
                  <div
                    role="presentation"
                    className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-fg-dim"
                  >
                    {group.label}
                  </div>
                  {group.items.map((entry) => {
                    const idx = entryIndexMap.get(entry.key) ?? -1;
                    const isSelected = idx === clampedIndex;
                    const optionId = `${baseId}-opt-${entry.key}`;
                    return (
                      <div
                        key={entry.key}
                        id={optionId}
                        role="option"
                        aria-selected={isSelected}
                        onMouseEnter={() => setSelectedIndex(idx)}
                        onClick={() => entry.onActivate()}
                        className={`flex cursor-pointer items-center justify-between gap-3 rounded-sm px-2.5 py-2 text-xs transition-colors ${
                          isSelected
                            ? "bg-teal-surface text-fg"
                            : "text-fg hover:bg-surface-elevated"
                        }`}
                      >
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-medium text-fg">
                              {entry.primaryLabel}
                            </span>
                            {entry.badgeKind ? (
                              <SemanticBadge kind={entry.badgeKind} />
                            ) : null}
                          </div>
                          {entry.codeTarget || entry.secondaryDetail ? (
                            <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-fg-muted">
                              {entry.codeTarget ? (
                                <code
                                  dir="ltr"
                                  className="unicode-bidi-isolate font-mono text-fg-muted"
                                >
                                  {entry.codeTarget}
                                </code>
                              ) : null}
                              {entry.secondaryDetail ? (
                                <span>{entry.secondaryDetail}</span>
                              ) : null}
                            </div>
                          ) : null}
                        </div>

                        {entry.shortcut ? (
                          <kbd className="shrink-0 rounded-xs border border-border-control bg-canvas px-1.5 py-0.5 font-mono text-[10px] text-fg-muted">
                            {entry.shortcut}
                          </kbd>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>

            {/* Partial Empty State (Mixed Search) */}
            {partialEmptyNotice ? (
              <div className="mt-2 rounded-sm border border-border bg-chrome/60 px-2.5 py-1.5 text-xs text-fg-muted">
                {partialEmptyNotice}
              </div>
            ) : null}

            {/* Total Empty State */}
            {flatEntries.length === 0 ? (
              <div className="flex flex-col items-center justify-center gap-2.5 py-8 text-center">
                <p className="text-xs text-fg-muted">
                  {`No matches for "${displayEmptyQuery}"`}
                </p>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setQuery("");
                    setSelectedIndex(0);
                    inputRef.current?.focus();
                  }}
                >
                  Clear query
                </Button>
              </div>
            ) : null}
          </div>

          {/* Permanent P-10 Human-Only Safety Footer */}
          <div className="flex items-center justify-between gap-2 border-t border-border bg-chrome px-3 py-2 text-[11px] text-fg-muted">
            <span className="font-medium text-fg-muted">
              Approvals are never run from here
            </span>
            <span className="font-mono text-[10px] text-fg-dim">
              ↑↓ select · ↵ navigate · Esc close
            </span>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
