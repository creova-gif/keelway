import React, { useEffect, useId, useMemo, useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { SearchField } from "@/components/ui/FilterBar";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import type { CodeSymbolItem, GitFileStatus, WorkspaceFileNode } from "@/lib/types";

export type FilesExplorerTab = "tree" | "changes" | "symbols";

const GIT_STATUS_STYLES: Record<GitFileStatus, { label: string; classes: string }> = {
  M: { label: "Modified", classes: "border-running/40 bg-running-subtle text-running" },
  A: { label: "Added", classes: "border-ok/40 bg-ok-subtle text-ok" },
  D: { label: "Deleted", classes: "border-danger/45 bg-danger-subtle text-danger" },
  U: { label: "Untracked", classes: "border-border-control/60 bg-surface-elevated text-fg-muted" },
};

const SYMBOL_KIND_SHORT: Record<CodeSymbolItem["kind"], string> = {
  function: "fn",
  class: "cls",
  interface: "ifc",
  variable: "var",
  method: "mtd",
  type: "typ",
};

export function flattenFiles(nodes: WorkspaceFileNode[]): WorkspaceFileNode[] {
  const out: WorkspaceFileNode[] = [];
  const visit = (items: WorkspaceFileNode[]) => {
    for (const item of items) {
      if (item.type === "file") {
        out.push(item);
      } else if (item.children) {
        visit(item.children);
      }
    }
  };
  visit(nodes);
  return out;
}

function collectDirectoryPaths(nodes: WorkspaceFileNode[]): string[] {
  const dirs: string[] = [];
  const visit = (items: WorkspaceFileNode[]) => {
    for (const item of items) {
      if (item.type === "directory") {
        dirs.push(item.path);
        if (item.children) visit(item.children);
      }
    }
  };
  visit(nodes);
  return dirs;
}

export interface FilesExplorerSidebarProps {
  tree: WorkspaceFileNode[];
  symbols: CodeSymbolItem[];
  activeTab: FilesExplorerTab;
  onTabChange: (tab: FilesExplorerTab) => void;
  activePath: string;
  dirtyByPath: Record<string, boolean>;
  saveErrorsByPath: Record<string, string>;
  onSelectFile: (path: string) => void;
  onSelectSymbol: (symbol: CodeSymbolItem) => void;
}

export function FilesExplorerSidebar({
  tree,
  symbols,
  activeTab,
  onTabChange,
  activePath,
  dirtyByPath,
  saveErrorsByPath,
  onSelectFile,
  onSelectSymbol,
}: FilesExplorerSidebarProps): React.JSX.Element {
  const [expandedDirs, setExpandedDirs] = useState<Record<string, boolean>>({});
  const [symbolQuery, setSymbolQuery] = useState("");
  const symbolFilterId = useId();

  useEffect(() => {
    const allDirs = collectDirectoryPaths(tree);
    setExpandedDirs((prev) => {
      const next = { ...prev };
      for (const dir of allDirs) {
        if (next[dir] === undefined) next[dir] = true;
      }
      return next;
    });
  }, [tree]);

  const flatFiles = useMemo(() => flattenFiles(tree), [tree]);

  const changedFiles = useMemo(
    () =>
      flatFiles.filter(
        (node) =>
          Boolean(node.gitStatus) ||
          Boolean(node.dirty) ||
          Boolean(dirtyByPath[node.path]) ||
          Boolean(saveErrorsByPath[node.path]),
      ),
    [dirtyByPath, flatFiles, saveErrorsByPath],
  );

  const filteredSymbols = useMemo(() => {
    const q = symbolQuery.trim().toLowerCase();
    if (!q) return symbols;
    return symbols.filter(
      (s) => s.name.toLowerCase().includes(q) || s.path.toLowerCase().includes(q),
    );
  }, [symbolQuery, symbols]);

  const renderGitBadge = (status?: GitFileStatus) => {
    if (!status) return null;
    const spec = GIT_STATUS_STYLES[status];
    return (
      <span
        title={spec.label}
        className={`inline-flex shrink-0 items-center rounded-xs border px-1 py-0 font-mono text-[10px] font-semibold leading-4 ${spec.classes}`}
      >
        {status}
      </span>
    );
  };

  const renderTreeNodes = (nodes: WorkspaceFileNode[], depth = 0): React.ReactNode =>
    nodes.map((node) => {
      if (node.type === "directory") {
        const isOpen = expandedDirs[node.path] !== false;
        return (
          <div key={node.path}>
            <button
              type="button"
              aria-expanded={isOpen}
              onClick={() => setExpandedDirs((prev) => ({ ...prev, [node.path]: !isOpen }))}
              style={{ paddingInlineStart: `${8 + depth * 12}px` }}
              className="flex min-h-row w-full items-center gap-1.5 rounded-xs pe-2 py-1 text-start text-xs font-medium text-fg-muted hover:bg-surface-elevated hover:text-fg"
            >
              <span aria-hidden="true" className="font-mono text-[10px] text-fg-dim">
                {isOpen ? "▾" : "▸"}
              </span>
              <code dir="ltr" className="unicode-bidi-isolate truncate font-mono">
                {node.name}
              </code>
            </button>
            {isOpen && node.children ? <div>{renderTreeNodes(node.children, depth + 1)}</div> : null}
          </div>
        );
      }

      const isCurrent = node.path === activePath;
      const err = saveErrorsByPath[node.path];
      const isDirty = Boolean(dirtyByPath[node.path] || node.dirty);

      return (
        <button
          key={node.path}
          type="button"
          aria-current={isCurrent ? "true" : undefined}
          onClick={() => onSelectFile(node.path)}
          style={{ paddingInlineStart: `${16 + depth * 12}px` }}
          className={`flex min-h-row w-full items-center justify-between gap-1.5 rounded-xs border-s-2 pe-2 py-1 text-start text-xs transition-colors duration-fast ease-state ${
            isCurrent
              ? "border-s-accent text-fg"
              : "border-s-transparent text-fg-muted hover:bg-surface-elevated hover:text-fg"
          }`}
        >
          <code dir="ltr" className="unicode-bidi-isolate truncate font-mono">
            {node.name}
          </code>
          <span className="flex shrink-0 items-center gap-1">
            {err ? (
              <SemanticBadge kind="not-saved" />
            ) : isDirty ? (
              <span className="rounded-xs border border-border-control/60 bg-surface-elevated px-1 font-mono text-[10px] text-fg-muted">
                Unsaved
              </span>
            ) : null}
            {renderGitBadge(node.gitStatus)}
          </span>
        </button>
      );
    });

  return (
    <Tabs.Root
      value={activeTab}
      onValueChange={(val) => onTabChange(val as FilesExplorerTab)}
      className="flex h-full min-h-0 flex-col overflow-hidden"
    >
      <Tabs.List
        aria-label="Files explorer views"
        className="grid shrink-0 grid-cols-3 gap-1 border-b border-border px-2 py-1.5"
      >
        <Tabs.Trigger
          value="tree"
          className="rounded-xs px-2 py-1 text-xs font-medium text-fg-muted data-[state=active]:bg-surface-elevated data-[state=active]:text-fg"
        >
          Tree
        </Tabs.Trigger>
        <Tabs.Trigger
          value="changes"
          className="inline-flex items-center justify-center gap-1 rounded-xs px-2 py-1 text-xs font-medium text-fg-muted data-[state=active]:bg-surface-elevated data-[state=active]:text-fg"
        >
          <span>Changes</span>
          <span className="rounded-full border border-border-control/60 bg-canvas px-1.5 py-0 font-mono text-[10px] tabular-nums text-fg">
            {changedFiles.length}
          </span>
        </Tabs.Trigger>
        <Tabs.Trigger
          value="symbols"
          className="rounded-xs px-2 py-1 text-xs font-medium text-fg-muted data-[state=active]:bg-surface-elevated data-[state=active]:text-fg"
        >
          Symbols
        </Tabs.Trigger>
      </Tabs.List>

      <Tabs.Content value="tree" className="min-h-0 flex-1 overflow-y-auto p-1.5">
        {tree.length === 0 ? (
          <p className="p-2 text-xs text-fg-muted">No files loaded in workspace.</p>
        ) : (
          renderTreeNodes(tree)
        )}
      </Tabs.Content>

      <Tabs.Content value="changes" className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2">
        <div className="px-1 font-mono text-[11px] tabular-nums text-fg-muted">
          {`${changedFiles.length} changed ${changedFiles.length === 1 ? "file" : "files"}`}
        </div>
        {changedFiles.length === 0 ? (
          <p className="px-1 py-3 text-xs text-fg-muted">Working tree is clean.</p>
        ) : (
          changedFiles.map((node) => (
            <button
              key={node.path}
              type="button"
              aria-current={node.path === activePath ? "true" : undefined}
              onClick={() => onSelectFile(node.path)}
              className={`flex min-h-row w-full items-center justify-between gap-2 rounded-xs border-s-2 px-2 py-1 text-start text-xs ${
                node.path === activePath
                  ? "border-s-accent text-fg"
                  : "border-s-transparent text-fg-muted hover:bg-surface-elevated hover:text-fg"
              }`}
            >
              <code dir="ltr" className="unicode-bidi-isolate truncate font-mono">
                {node.path}
              </code>
              <span className="flex shrink-0 items-center gap-1">
                {saveErrorsByPath[node.path] ? <SemanticBadge kind="not-saved" /> : null}
                {renderGitBadge(node.gitStatus)}
              </span>
            </button>
          ))
        )}
      </Tabs.Content>

      <Tabs.Content value="symbols" className="flex min-h-0 flex-1 flex-col overflow-hidden p-2">
        <div className="mb-2 shrink-0">
          <SearchField
            id={symbolFilterId}
            label="Filter symbols"
            value={symbolQuery}
            onChange={(e) => setSymbolQuery(e.target.value)}
            placeholder="Filter symbols..."
          />
        </div>
        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto">
          {filteredSymbols.length === 0 ? (
            <p className="px-2 py-3 text-xs text-fg-muted">No matching symbols.</p>
          ) : (
            filteredSymbols.map((sym) => (
              <button
                key={`${sym.path}-${sym.name}-${sym.line}`}
                type="button"
                onClick={() => onSelectSymbol(sym)}
                className="flex w-full flex-col gap-0.5 rounded-xs border border-transparent px-2 py-1.5 text-start text-xs hover:border-border-strong hover:bg-surface-elevated"
              >
                <div className="flex items-center justify-between gap-1.5">
                  <span className="inline-flex min-w-0 items-center gap-1.5 font-mono font-medium text-fg">
                    <span className="rounded-xs border border-border-control/50 bg-surface px-1 text-[10px] text-accent">
                      {SYMBOL_KIND_SHORT[sym.kind]}
                    </span>
                    <code dir="ltr" className="unicode-bidi-isolate truncate">
                      {sym.name}
                    </code>
                  </span>
                  <span className="shrink-0 font-mono text-[10px] tabular-nums text-fg-dim">
                    {`:${sym.line}`}
                  </span>
                </div>
                <code dir="ltr" className="unicode-bidi-isolate truncate font-mono text-[10px] text-fg-muted">
                  {sym.path}
                </code>
              </button>
            ))
          )}
        </div>
      </Tabs.Content>
    </Tabs.Root>
  );
}
