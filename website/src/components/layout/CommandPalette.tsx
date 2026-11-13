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
  Webhook,
  X,
} from "lucide-react";
import type { SearchIndexItem } from "@/app/api/search-index/route";
import { cn } from "@/lib/utils";
import { trackEvent } from "@/lib/analytics";

export function openCommandPalette(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("keelway:open-cmdk"));
  }
}

/**
 * Global Cmd+K / Ctrl+K Instant Search Palette (Claude Academy / Linear style).
 * Jumps instantly across all 7 routes, 15 models, 6 doc sections, and 183 API endpoints.
 */
export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<SearchIndexItem[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const loadedRef = useRef(false);

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

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) {
      // Curated default high-value jump targets across all 4 domains
      const pages = items.filter((i) => i.group === "page").slice(0, 5);
      const models = items.filter((i) => i.group === "model").slice(0, 4);
      const docs = items.filter((i) => i.group === "docs").slice(0, 3);
      const apis = items
        .filter((i) => i.group === "api" && i.title.includes("/v1/"))
        .slice(0, 6);
      return [...pages, ...models, ...docs, ...apis];
    }

    const tokens = q.split(/\s+/).filter(Boolean);
    const scored: { item: SearchIndexItem; score: number }[] = [];

    for (const item of items) {
      const titleLow = item.title.toLowerCase();
      const hay = `${titleLow} ${item.subtitle.toLowerCase()} ${item.keywords.toLowerCase()}`;
      if (!tokens.every((tok) => hay.includes(tok))) continue;

      let score = 10;
      if (titleLow === q) score += 100;
      else if (titleLow.startsWith(q)) score += 50;
      else if (titleLow.includes(q)) score += 25;
      if (item.group === "page" || item.group === "model") score += 8;
      scored.push({ item, score });
    }

    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, 24).map((s) => s.item);
  }, [items, query]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query, open]);

  const selectItem = (item: SearchIndexItem) => {
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

  const iconForGroup = (group: SearchIndexItem["group"]) => {
    switch (group) {
      case "model":
        return <Cpu className="h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />;
      case "docs":
        return <BookOpen className="h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />;
      case "api":
        return <Webhook className="h-4 w-4 shrink-0 text-amber-alert" aria-hidden="true" />;
      default:
        return <LayoutGrid className="h-4 w-4 shrink-0 text-teal-accent" aria-hidden="true" />;
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-[12vh] z-50 w-[94vw] max-w-2xl -translate-x-1/2 overflow-hidden rounded-lg border border-border-strong bg-surface shadow-2xl focus:outline-none">
          <Dialog.Title className="sr-only">
            Search Keelway Models, API Endpoints, and Documentation
          </Dialog.Title>
          <Dialog.Description className="sr-only">
            Type to filter across 15 hybrid models, 183 OpenAPI endpoints, and
            developer guides. Use Up and Down arrows to navigate and Enter to
            open.
          </Dialog.Description>

          {/* Search Input Bar */}
          <div className="flex items-center gap-3 border-b border-border-subtle bg-surface-elevated/80 px-4 py-3">
            <Search
              className="h-4 w-4 shrink-0 text-teal-accent"
              aria-hidden="true"
            />
            <input
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
              placeholder="Jump to model (keelway-core, gemini), endpoint (/v1/responses), or docs…"
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

          {/* Results Listbox */}
          <div
            id="cmdk-results-list"
            role="listbox"
            className="max-h-[58vh] overflow-y-auto p-2"
          >
            {results.length === 0 ? (
              <div className="py-12 text-center">
                <p className="font-mono text-xs text-fg-muted">
                  No matches found for &ldquo;{query}&rdquo; across {items.length}{" "}
                  indexed items.
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
                        ? "bg-surface-elevated border border-teal-accent/60"
                        : "border border-transparent hover:bg-surface-elevated/50"
                    )}
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      {iconForGroup(item.group)}
                      <div className="min-w-0">
                        <div className="truncate font-mono text-xs font-semibold text-fg">
                          {item.title}
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
                          item.group === "api" && item.badge === "POST"
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
              Indexed: <strong className="text-fg">{items.length || 211}</strong>{" "}
              models, routes &amp; OpenAPI 3.1 operations
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
