import React, { useEffect, useId, useMemo, useState } from "react";
import { Button } from "@/components/ui/Button";
import { fetchCodebaseSymbols, fetchOpenCoreWeights } from "@/lib/api";
import type { CodeSymbolItem, OpenCoreWeightItem, RoutingExplainResult } from "@/lib/types";

export interface SlashSkillOption {
  name: string;
  description: string;
}

export const DEFAULT_SLASH_SKILLS: SlashSkillOption[] = [
  { name: "/office-hours", description: "Reframe product scope before writing code" },
  { name: "/review", description: "Pre-landing PR safety & gate integrity review" },
  { name: "/qa", description: "Surface-aware browser, API, and CLI verification" },
  { name: "/investigate", description: "Systematic root-cause debugging" },
  { name: "/ship", description: "Run tests, audit Record chain, and prepare PR" },
];

/** Last routing simulation for the composer — populated before a run launches, never after. */
export type ComposerPreflight =
  | { status: "simulated"; result: RoutingExplainResult }
  | { status: "unavailable" };

export function routeLabel(result: RoutingExplainResult): string {
  if (result.decision === "blocked_fail_closed") return "blocked — fail-closed";
  if (result.dataBoundary === "external_vendor_api") return `cloud (${result.provider})`;
  return result.dataBoundary === "sovereign_vpc" ? "local (sovereign vpc)" : "local (sovereign)";
}

export interface AgentComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmitPrompt: () => void;
  runtimeReachable: boolean;
  textareaRef?: React.RefObject<HTMLTextAreaElement | null>;
  slashSkills?: SlashSkillOption[];
  activeModelLabel?: string;
  onSelectActiveModel?: (modelId: string, modelLabel: string) => void;
  preflight?: ComposerPreflight | null;
  fetchSymbolsFn?: () => Promise<CodeSymbolItem[]>;
  fetchModelsFn?: () => Promise<OpenCoreWeightItem[]>;
}

export function AgentComposer({
  value,
  onChange,
  onSubmitPrompt,
  runtimeReachable,
  textareaRef,
  slashSkills = DEFAULT_SLASH_SKILLS,
  activeModelLabel,
  onSelectActiveModel,
  preflight = null,
  fetchSymbolsFn = fetchCodebaseSymbols,
  fetchModelsFn = fetchOpenCoreWeights,
}: AgentComposerProps): React.JSX.Element {
  const composerId = useId();
  const listboxId = useId();
  const symbolsListboxId = useId();

  const [activeIndex, setActiveIndex] = useState(0);
  const [dismissedForValue, setDismissedForValue] = useState<string | null>(null);
  const [symbols, setSymbols] = useState<CodeSymbolItem[] | null>(null);
  const [models, setModels] = useState<OpenCoreWeightItem[] | null>(null);
  const [modelMenuOpen, setModelMenuOpen] = useState(false);

  const slashQuery = useMemo(() => {
    const match = /^\/([^\s]*)$/.exec(value);
    return match ? match[1]!.toLowerCase() : null;
  }, [value]);

  const symbolQuery = useMemo(() => {
    const match = /^@([^\s]*)$/.exec(value);
    return match ? match[1]!.toLowerCase() : null;
  }, [value]);

  const filteredSkills = useMemo(() => {
    if (slashQuery === null) return [];
    if (slashQuery.length === 0) return slashSkills;
    return slashSkills.filter(
      (item) =>
        item.name.slice(1).toLowerCase().includes(slashQuery) ||
        item.description.toLowerCase().includes(slashQuery),
    );
  }, [slashQuery, slashSkills]);

  const filteredSymbols = useMemo(() => {
    if (symbolQuery === null || !symbols) return [];
    const pool = symbolQuery.length === 0
      ? symbols
      : symbols.filter(
          (item) =>
            item.name.toLowerCase().includes(symbolQuery) ||
            item.path.toLowerCase().includes(symbolQuery),
        );
    return pool.slice(0, 8);
  }, [symbolQuery, symbols]);

  const isSlashMenuOpen =
    slashQuery !== null && dismissedForValue !== value && filteredSkills.length > 0;
  const isSymbolMenuOpen =
    symbolQuery !== null && dismissedForValue !== value && filteredSymbols.length > 0;
  const safeActiveIndex =
    filteredSkills.length > 0 ? Math.min(activeIndex, filteredSkills.length - 1) : 0;
  const safeSymbolIndex =
    filteredSymbols.length > 0 ? Math.min(activeIndex, filteredSymbols.length - 1) : 0;

  useEffect(() => {
    if (symbolQuery === null || symbols !== null) return;
    let mounted = true;
    fetchSymbolsFn()
      .then((items) => {
        if (mounted) setSymbols(items);
      })
      .catch(() => {
        if (mounted) setSymbols([]);
      });
    return () => {
      mounted = false;
    };
  }, [symbolQuery, symbols, fetchSymbolsFn]);

  useEffect(() => {
    if (!modelMenuOpen || models !== null) return;
    let mounted = true;
    fetchModelsFn()
      .then((items) => {
        if (mounted) setModels(items);
      })
      .catch(() => {
        if (mounted) setModels([]);
      });
    return () => {
      mounted = false;
    };
  }, [modelMenuOpen, models, fetchModelsFn]);

  const insertSlashSkill = (skillName: string) => {
    onChange(`${skillName} `);
    setActiveIndex(0);
    setDismissedForValue(null);
    textareaRef?.current?.focus();
  };

  const insertSymbol = (item: CodeSymbolItem) => {
    onChange(`@${item.path} `);
    setActiveIndex(0);
    setDismissedForValue(null);
    textareaRef?.current?.focus();
  };

  const isSendSoftDisabled = !runtimeReachable || value.trim().length === 0;

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && !event.shiftKey && !event.altKey && event.key === "Enter") {
      event.preventDefault();
      event.stopPropagation();
      if (!isSendSoftDisabled) onSubmitPrompt();
      return;
    }

    if (isSymbolMenuOpen) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((prev) => (prev + 1) % filteredSymbols.length);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((prev) => (prev - 1 + filteredSymbols.length) % filteredSymbols.length);
      } else if (
        event.key === "Enter" &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.shiftKey &&
        !event.altKey
      ) {
        event.preventDefault();
        event.stopPropagation();
        const chosen = filteredSymbols[safeSymbolIndex];
        if (chosen) insertSymbol(chosen);
      } else if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        setDismissedForValue(value);
      }
      return;
    }

    if (!isSlashMenuOpen) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((prev) => (prev + 1) % filteredSkills.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((prev) => (prev - 1 + filteredSkills.length) % filteredSkills.length);
    } else if (
      event.key === "Enter" &&
      !event.metaKey &&
      !event.ctrlKey &&
      !event.shiftKey &&
      !event.altKey
    ) {
      event.preventDefault();
      event.stopPropagation();
      const chosen = filteredSkills[safeActiveIndex];
      if (chosen) insertSlashSkill(chosen.name);
    } else if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      setDismissedForValue(value);
    }
  };

  return (
    <div className="relative mt-4 rounded-md border border-border-strong bg-surface p-3">
      {isSlashMenuOpen ? (
        <ul
          id={listboxId}
          role="listbox"
          aria-label="Slash skills"
          className="mb-2 max-h-44 overflow-y-auto rounded-sm border border-border-strong bg-surface-elevated p-1 shadow-popover"
        >
          {filteredSkills.map((skill, idx) => {
            const isSelected = idx === safeActiveIndex;
            return (
              <li
                key={skill.name}
                id={`${listboxId}-opt-${idx}`}
                role="option"
                aria-selected={isSelected}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => insertSlashSkill(skill.name)}
                className={`flex cursor-pointer items-center justify-between gap-2 rounded-xs px-2.5 py-1.5 text-xs ${
                  isSelected
                    ? "bg-accent-subtle text-accent"
                    : "text-fg hover:bg-surface"
                }`}
              >
                <code dir="ltr" className="unicode-bidi-isolate font-mono font-semibold">
                  {skill.name}
                </code>
                <span className="truncate text-[11px] text-fg-muted">{skill.description}</span>
              </li>
            );
          })}
        </ul>
      ) : null}

      {isSymbolMenuOpen ? (
        <ul
          id={symbolsListboxId}
          role="listbox"
          aria-label="Files and symbols"
          className="mb-2 max-h-44 overflow-y-auto rounded-sm border border-border-strong bg-surface-elevated p-1 shadow-popover"
        >
          {filteredSymbols.map((item, idx) => {
            const isSelected = idx === safeSymbolIndex;
            return (
              <li
                key={`${item.path}:${item.name}`}
                id={`${symbolsListboxId}-opt-${idx}`}
                role="option"
                aria-selected={isSelected}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => insertSymbol(item)}
                className={`flex cursor-pointer items-center justify-between gap-2 rounded-xs px-2.5 py-1.5 text-xs ${
                  isSelected
                    ? "bg-accent-subtle text-accent"
                    : "text-fg hover:bg-surface"
                }`}
              >
                <code dir="ltr" className="unicode-bidi-isolate font-mono font-semibold">
                  {item.name}
                </code>
                <span className="truncate text-[11px] text-fg-muted">{item.kind} · {item.path}</span>
              </li>
            );
          })}
        </ul>
      ) : null}

      <label htmlFor={composerId} className="mb-1.5 block text-xs font-medium text-fg-muted">
        Ask agent or follow up in workspace
      </label>
      <textarea
        id={composerId}
        ref={textareaRef}
        rows={2}
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
          setActiveIndex(0);
          if (dismissedForValue !== null) setDismissedForValue(null);
        }}
        onKeyDown={handleKeyDown}
        placeholder="Describe the change. The agent plans, simulates, then asks before anything Tier-3."
        className="w-full resize-y rounded-sm border border-border-control bg-canvas px-2.5 py-1.5 text-ui text-fg placeholder:text-fg-dim"
      />
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => {
              onChange("@");
              textareaRef?.current?.focus();
            }}
            className="rounded-sm border border-border-strong px-2 py-1 font-mono text-[10px] font-semibold text-fg-muted hover:bg-surface-elevated hover:text-fg"
          >
            + Attach files
          </button>
          <button
            type="button"
            onClick={() => {
              onChange("@");
              textareaRef?.current?.focus();
            }}
            className="rounded-sm border border-border-strong px-2 py-1 font-mono text-[10px] font-semibold text-fg-muted hover:bg-surface-elevated hover:text-fg"
          >
            @ file / symbol
          </button>
          <button
            type="button"
            onClick={() => {
              onChange("/");
              textareaRef?.current?.focus();
            }}
            className="rounded-sm border border-border-strong px-2 py-1 font-mono text-[10px] font-semibold text-fg-muted hover:bg-surface-elevated hover:text-fg"
          >
            / command
          </button>
          <span className="ms-1 text-[11px] text-fg-dim">
            ⌘↵ sends prompt only · never approves pending P-10 gates
          </span>
        </div>
        <div className="flex items-center gap-2">
          {activeModelLabel ? (
            <div className="relative">
              <button
                type="button"
                onClick={() => setModelMenuOpen((v) => !v)}
                disabled={!onSelectActiveModel}
                aria-haspopup="listbox"
                aria-expanded={modelMenuOpen}
                className="font-mono text-[10px] text-fg-dim hover:text-fg disabled:cursor-default"
              >
                local · {activeModelLabel} <span className="text-fg-muted">Model ▾</span>
              </button>
              {modelMenuOpen && onSelectActiveModel ? (
                <ul
                  role="listbox"
                  aria-label="Model"
                  className="absolute bottom-full end-0 z-50 mb-1 max-h-44 w-56 overflow-y-auto rounded-sm border border-border-strong bg-surface-elevated p-1 shadow-popover"
                >
                  {models === null ? (
                    <li className="px-2.5 py-1.5 text-[11px] text-fg-dim">Loading weights…</li>
                  ) : models.length === 0 ? (
                    <li className="px-2.5 py-1.5 text-[11px] text-fg-dim">
                      No weights listed — model picker unavailable.
                    </li>
                  ) : (
                    models.map((w) => (
                      <li
                        key={w.id}
                        role="option"
                        aria-selected={`${w.name} v${w.version}` === activeModelLabel}
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => {
                          onSelectActiveModel(w.id, `${w.name} v${w.version}`);
                          setModelMenuOpen(false);
                        }}
                        className="flex cursor-pointer items-center justify-between gap-2 rounded-xs px-2.5 py-1.5 text-xs text-fg hover:bg-surface"
                      >
                        <span className="font-mono font-semibold">{w.name} v{w.version}</span>
                        <span className="text-[10px] text-fg-dim">{w.status}</span>
                      </li>
                    ))
                  )}
                </ul>
              ) : null}
            </div>
          ) : null}
          <Button
            size="sm"
            variant="primary"
            shortcutHint="⌘↵"
            aria-disabled={isSendSoftDisabled ? "true" : undefined}
            onClick={onSubmitPrompt}
          >
            Plan run
          </Button>
        </div>
      </div>

      {preflight ? (
        <div className="mt-3 rounded-sm border border-border bg-canvas px-3 py-2">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-xs font-semibold text-fg">Pre-flight strip</span>
            <span className="font-mono text-[10px] text-fg-dim">simulated, zero tokens</span>
          </div>
          {preflight.status === "simulated" ? (
            <p className="mt-1 font-mono text-[11px] text-fg-muted">
              Route: {routeLabel(preflight.result)} · {preflight.result.selectedModel} · est. $
              {preflight.result.estimatedCostUsd.toFixed(2)} / ~{preflight.result.estimatedLatencyMs}ms
              {preflight.result.decision === "blocked_fail_closed" && preflight.result.blockedReason
                ? ` — ${preflight.result.blockedReason}`
                : ""}
            </p>
          ) : (
            <p className="mt-1 font-mono text-[11px] text-fg-muted">
              Routing simulation unavailable — the run still starts; no estimates shown.
            </p>
          )}
          <p className="mt-1 text-[10px] text-fg-dim">
            Estimates are labeled estimates. If routing can&apos;t be simulated, the strip says so —
            never guesses.
          </p>
        </div>
      ) : null}
    </div>
  );
}
