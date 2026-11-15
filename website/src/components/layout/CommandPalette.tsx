"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import * as Dialog from "@radix-ui/react-dialog";
import {
  ArrowRight,
  BookOpen,
  Cpu,
  LayoutGrid,
  Search,
  Sparkles,
  Webhook,
  X,
} from "lucide-react";
import type { SearchIndexItem } from "@/app/api/search-index/route";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

type CommandItem = SearchIndexItem | (Omit<SearchIndexItem, "group"> & { group: "action" });

const BUILTIN_ACTIONS: CommandItem[] = [
  {
    id: "act-golden-thread-studio",
    group: "action",
    title: "Try Golden-Thread Studio Showcase",
    subtitle: "Zero-install LangGraph-to-KFlow SVG canvas, AST line sync, Flight-Tape scrubber & Prompt Gate",
    badge: "STUDIO",
    href: "/#studio-showcase",
    keywords: "action studio golden thread langgraph kflow ast scrubber blast radius prompt gate",
  },
  {
    id: "act-cyclic-kflow-autopilot",
    group: "action",
    title: "Simulate Cyclic KFlow & Cost/Privacy Autopilot",
    subtitle: "Bounded reflection loops, map-reduce fan-out, saga compensation & pre-run OpenCore fallback",
    badge: "AUTOPILOT",
    href: "/docs#surfaces",
    keywords: "action cyclic kflow reflection loop map reduce saga compensation autopilot p95 cost airgap privacy",
  },
  {
    id: "act-step-debugger-bridge",
    group: "action",
    title: "Attach VS Code / Cursor Step-Through Debugger",
    subtitle: "Live conditional breakpoints, F10/F11 stepping, DLP state mutation & 4D Routing CodeLens",
    badge: "DEBUGGER",
    href: "/docs#surfaces",
    keywords: "action step debugger conditional breakpoints f10 f11 codelens vscode cursor ide bridge",
  },
  {
    id: "act-dev-tool",
    group: "action",
    title: "Launch 10-View Local Dev Tool",
    subtitle: "Run keelway dev locally (:7420/app) for Builder & Guided Non-Coder Mode",
    badge: "ACTION",
    href: "/#quickstart",
    keywords: "action launch 10-view dev tool studio builder non-coder workbench quickstart",
  },
  {
    id: "act-tamper-lab",
    group: "action",
    title: "Simulate Record Tamper Lab",
    subtitle: "Mutate entry #1279 and verify SHA-256 hash-chain tamper evidence",
    badge: "ACTION",
    href: "/governance#tamper-lab",
    keywords: "action simulate record tamper lab sha256 #1279 ledger governance",
  },
  {
    id: "act-nocode-builder",
    group: "action",
    title: "Open No-Code Blueprint Builder",
    subtitle: "Launch keelway dev locally to compile briefs into PRDs, sprint issues & DAGs",
    badge: "ACTION",
    href: "/#quickstart",
    keywords: "action open no-code blueprint builder prd issues dag quickstart",
  },
  {
    id: "act-byom-pricing",
    group: "action",
    title: "Compare BYOM & Pro Pricing",
    subtitle: "5-stream pricing, 0%-markup BYOM API compliance & 85/15 Creator Marketplace",
    badge: "ACTION",
    href: "/pricing#byom-compliance",
    keywords: "action compare byom pro pricing chatgpt claude api marketplace",
  },
  {
    id: "act-marketplace-scanner",
    group: "action",
    title: "Test Marketplace Pre-Publish Security Scanner",
    subtitle: "Scan keelway.package/v1 manifests for prompt injection & shell=True sinks",
    badge: "ACTION",
    href: "/governance#manifest-drift",
    keywords: "action marketplace security scanner manifest drift p-13 p-14",
  },
];

const PREFIX_HINTS: { prefix: ">" | "@" | "/" | "#"; label: string }[] = [
  { prefix: ">", label: "> Actions" },
  { prefix: "@", label: "@ Models" },
  { prefix: "/", label: "/ Docs" },
  { prefix: "#", label: "# APIs & Governance" },
];

export function openCommandPalette(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("keelway:open-cmdk"));
  }
}

/**
 * Global Cmd+K / Ctrl+K Instant Search & Linear-Style Prefix Palette (`>`, `@`, `/`, `#`).
 */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SearchIndexItem[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const loadedRef = useRef(false);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const ensureIndexLoaded = useCallback(async () => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    try {
      const res = await fetch("/api/search-index");
      if (res.ok) {
        const data = (await res.json()) as { items?: SearchIndexItem[] };
        if (data.items) setItems(data.items);
      }
    } catch {
      loadedRef.current = false;
    }
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((prev) => {
          const next = !prev;
          if (next) {
            void ensureIndexLoaded();
            trackEvent("cmdk_opened", { trigger: "shortcut" });
          }
          return next;
        });
      }
    };

    const onCustomOpen = () => {
      void ensureIndexLoaded();
      setOpen(true);
      trackEvent("cmdk_opened", { trigger: "header_button" });
    };

    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keelway:open-cmdk", onCustomOpen);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keelway:open-cmdk", onCustomOpen);
    };
  }, [ensureIndexLoaded]);

  const activePrefix = useMemo<">" | "@" | "/" | "#" | null>(() => {
    const trimmed = query.trimStart();
    const first = trimmed[0];
    if (first === ">" || first === "@" || first === "/" || first === "#") {
      return first;
    }
    return null;
  }, [query]);

  const results = useMemo<CommandItem[]>(() => {
    const allPool: CommandItem[] = [...BUILTIN_ACTIONS, ...items];
    const trimmed = query.trimStart();

    if (activePrefix) {
      const rest = trimmed.slice(1).trim().toLowerCase();
      const filteredPool = allPool.filter((item) => {
        if (activePrefix === ">") {
          return item.group === "action";
        }
        if (activePrefix === "@") {
          return item.group === "model";
        }
        if (activePrefix === "/") {
          return item.group === "docs" || item.group === "page";
        }
        // '#' -> Governance Labs, Marketplace & OpenAPI 3.1 Endpoints
        return (
          item.group === "api" ||
          item.href.startsWith("/governance") ||
          item.keywords.toLowerCase().includes("marketplace")
        );
      });

      if (!rest) return filteredPool.slice(0, 24);
      const tokens = rest.split(/\s+/).filter(Boolean);
      return filteredPool
        .filter((item) => {
          const hay = `${item.title} ${item.subtitle} ${item.keywords}`.toLowerCase();
          return tokens.every((tok) => hay.includes(tok));
        })
        .slice(0, 24);
    }

    const q = trimmed.trim().toLowerCase();
    if (!q) {
      const actions = BUILTIN_ACTIONS.slice(0, 4);
      const pages = items.filter((i) => i.group === "page").slice(0, 4);
      const models = items.filter((i) => i.group === "model").slice(0, 3);
      const docs = items.filter((i) => i.group === "docs").slice(0, 3);
      const apis = items
        .filter((i) => i.group === "api" && i.title.includes("/v1/"))
        .slice(0, 4);
      return [...actions, ...pages, ...models, ...docs, ...apis];
    }

    const tokens = q.split(/\s+/).filter(Boolean);
    const scored: { item: CommandItem; score: number }[] = [];

    for (const item of allPool) {
      const titleLow = item.title.toLowerCase();
      const hay = `${titleLow} ${item.subtitle.toLowerCase()} ${item.keywords.toLowerCase()}`;
      if (!tokens.every((tok) => hay.includes(tok))) continue;

      let score = 10;
      if (titleLow === q) score += 100;
      else if (titleLow.startsWith(q)) score += 50;
      else if (titleLow.includes(q)) score += 25;
      if (item.group === "action" || item.group === "page" || item.group === "model") {
        score += 8;
      }
      scored.push({ item, score });
    }

    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, 24).map((s) => s.item);
  }, [activePrefix, items, query]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query, open]);

  const applyPrefixHint = (prefix: ">" | "@" | "/" | "#") => {
    setQuery((prev) => {
      const stripped = prev.trimStart().replace(/^[>@/#]\s*/, "");
      return activePrefix === prefix ? stripped : `${prefix} ${stripped}`;
    });
    trackEvent("cmdk_prefix_switched", { prefix });
    inputRef.current?.focus();
  };

  const selectItem = (item: CommandItem) => {
    setOpen(false);
    setQuery("");
    trackEvent("cmdk_result_selected", {
      group: item.group,
      target: item.href,
    });
    router.push(item.href);
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => (prev + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) => (prev - 1 + results.length) % results.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const chosen = results[activeIndex];
      if (chosen) selectItem(chosen);
    }
  };

  const iconForGroup = (group: CommandItem["group"]) => {
    switch (group) {
      case "action":
        return <Sparkles className="h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />;
      case "model":
        return <Cpu className="h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />;
      case "docs":
        return <BookOpen className="h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />;
      case "api":
        return <Webhook className="h-4 w-4 shrink-0 text-amber-alert" aria-hidden="true" />;
      case "page":
        return <LayoutGrid className="h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />;
      default: {
        const _exhaustive: never = group;
        return _exhaustive;
      }
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-[11vh] z-50 w-[94vw] max-w-2xl -translate-x-1/2 overflow-hidden rounded-lg border border-border-strong bg-surface shadow-2xl focus:outline-none">
          <Dialog.Title className="sr-only">
            Search Keelway Actions, Models, Docs, and Governance Endpoints
          </Dialog.Title>
          <Dialog.Description className="sr-only">
            Type to filter universally, or prefix with &gt; for Actions, @ for
            Models, / for Docs, and # for APIs &amp; Governance.
          </Dialog.Description>

          {/* Search Input Bar */}
          <div className="flex items-center gap-3 border-b border-border-subtle bg-surface-elevated/80 px-4 py-3">
            <Search
              className="h-4 w-4 shrink-0 text-teal-accent"
              aria-hidden="true"
            />
            <input
              ref={inputRef}
              type="text"
              role="combobox"
              aria-expanded="true"
              aria-controls="cmdk-results-list"
              aria-activedescendant={
                results[activeIndex] ? `cmdk-opt-${results[activeIndex].id}` : undefined
              }
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder="Search or type > actions, @ models, / docs, # APIs & governance…"
              autoFocus
              className="min-h-[36px] flex-1 bg-transparent text-sm text-fg placeholder:text-fg-dim focus:outline-none"
            />
            <Dialog.Close
              aria-label="Close command palette"
              className="inline-flex h-8 items-center gap-1 rounded-sm border border-border-strong bg-canvas px-2 font-mono text-[11px] text-fg-muted hover:text-fg"
            >
              <span>ESC</span>
              <X className="h-3 w-3" aria-hidden="true" />
            </Dialog.Close>
          </div>

          {/* Clickable Prefix Hint Pills */}
          <div className="flex flex-wrap items-center gap-1.5 border-b border-border-subtle bg-canvas/70 px-4 py-2">
            <span className="mr-1 font-mono text-[10px] uppercase text-fg-dim">
              Prefix Modes:
            </span>
            {PREFIX_HINTS.map((hint) => {
              const active = activePrefix === hint.prefix;
              return (
                <button
                  key={hint.prefix}
                  type="button"
                  onClick={() => applyPrefixHint(hint.prefix)}
                  className={cn(
                    "min-h-[28px] rounded-sm border px-2 font-mono text-[11px] transition-colors duration-100",
                    active
                      ? "border-teal-accent bg-teal-surface font-semibold text-teal-accent"
                      : "border-border-strong bg-surface text-fg-muted hover:border-teal-accent/60 hover:text-fg"
                  )}
                >
                  {hint.label}
                </button>
              );
            })}
          </div>

          {/* Results Listbox */}
          <div
            id="cmdk-results-list"
            role="listbox"
            className="max-h-[54vh] overflow-y-auto p-2"
          >
            {results.length === 0 ? (
              <div className="py-12 text-center">
                <p className="font-mono text-xs text-fg-muted">
                  No matches found for &ldquo;{query}&rdquo; across{" "}
                  {items.length + BUILTIN_ACTIONS.length} indexed items.
                </p>
              </div>
            ) : (
              results.map((item, idx) => {
                const isSelected = idx === activeIndex;
                return (
                  <button
                    key={item.id}
                    id={`cmdk-opt-${item.id}`}
                    type="button"
                    role="option"
                    aria-selected={isSelected}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onClick={() => selectItem(item)}
                    className={cn(
                      "flex min-h-[52px] w-full items-center justify-between gap-3 rounded-md px-3 py-2 text-left transition-colors duration-100",
                      isSelected
                        ? "border border-teal-accent/60 bg-surface-elevated"
                        : "border border-transparent hover:bg-surface-elevated/50"
                    )}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      {iconForGroup(item.group)}
                      <div className="min-w-0">
                        <div className="truncate font-mono text-xs font-semibold text-fg">
                          {item.group === "action" ? `> ${item.title}` : item.title}
                        </div>
                        <div className="truncate text-xs text-fg-muted">
                          {item.subtitle}
                        </div>
                      </div>
                    </div>

                    <div className="flex shrink-0 items-center gap-2">
                      <span
                        className={cn(
                          "rounded-sm px-2 py-0.5 text-[10px]",
                          item.group === "action"
                            ? "chip-teal"
                            : item.group === "api" && item.badge === "POST"
                              ? "chip-amber"
                              : "chip-neutral"
                        )}
                      >
                        {item.badge}
                      </span>
                      {isSelected && (
                        <ArrowRight
                          className="h-3.5 w-3.5 text-teal-accent"
                          aria-hidden="true"
                        />
                      )}
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {/* Footer Keyboard Legend */}
          <div className="flex items-center justify-between border-t border-border-subtle bg-canvas/80 px-4 py-2 font-mono text-[11px] text-fg-muted">
            <span>
              Indexed:{" "}
              <strong className="text-fg">
                {(items.length || 214) + BUILTIN_ACTIONS.length}
              </strong>{" "}
              actions, models, routes &amp; OpenAPI 3.1 operations
            </span>
            <span className="hidden sm:inline">
              ↑↓ Navigate · ↵ Open · Esc Dismiss
            </span>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
