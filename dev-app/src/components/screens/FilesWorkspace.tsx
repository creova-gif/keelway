import React, { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { FilesCommitModal, FilesDiffView, type FilesCommitModalProps, type FilesDiffViewProps } from "@/components/screens/FilesDiffAndCommit";
import { FilesExplorerSidebar, flattenFiles, type FilesExplorerSidebarProps, type FilesExplorerTab } from "@/components/screens/FilesExplorerSidebar";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { SemanticBadge } from "@/components/ui/SemanticBadge";
import {
  createGitCommit, fetchCodebaseSymbols, fetchFileContent, fetchFilesTree,
  fetchGitProposal, fetchStudioDiff, openInExternalEditor, saveFileContent,
} from "@/lib/api";
import type { CodeSymbolItem, FileDiffHunk, GitCommitResult, WorkspaceFileNode } from "@/lib/types";

export {
  FilesCommitModal, FilesDiffView, FilesExplorerSidebar,
  type FilesCommitModalProps, type FilesDiffViewProps, type FilesExplorerSidebarProps, type FilesExplorerTab,
};

export type FilesViewMode = "code" | "unified" | "split";

const LARGE_FILE_BYTES = 512 * 1024;
const MONACO_SELF_LOADER_SRC = "/studio/assets/monaco/vs/loader.js";
const MONACO_SELF_CSS_HREF = "/studio/assets/monaco/vs/editor/editor.main.css";

interface AmdRequireFunction {
  (deps: string[], onLoad: () => void, onError?: (err: unknown) => void): void;
  config?: (options: { paths: Record<string, string> }) => void;
}

interface MonacoDisposable {
  dispose(): void;
}

interface MonacoEditorInstance {
  getValue(): string;
  setValue(value: string): void;
  getModel?(): unknown;
  revealLineInCenter?(lineNumber: number): void;
  setPosition?(pos: { lineNumber: number; column: number }): void;
  onDidChangeModelContent(listener: () => void): MonacoDisposable;
  dispose(): void;
}

interface MonacoGlobal {
  editor: {
    defineTheme(name: string, data: Record<string, unknown>): void;
    setTheme(name: string): void;
    setModelLanguage?(model: unknown, languageId: string): void;
    create(container: HTMLElement, options: Record<string, unknown>): MonacoEditorInstance;
  };
}

function basenameOf(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

export interface FilesNavigationTarget {
  path: string;
  line?: number;
  nonce?: number;
}

export interface FilesWorkspaceProps {
  initialActivePath?: string;
  initialActiveLine?: number;
  selectedPath?: string;
  selectedLine?: number;
  navigationTarget?: FilesNavigationTarget;
  initialViewMode?: FilesViewMode;
  initialSidebarTab?: FilesExplorerTab;
  initialSaveError?: string;
  saveError?: string | null;
  renderSidebarInShell?: boolean;
  preferTextareaFallback?: boolean;
  onSidebarStateChange?: (sidebarProps: FilesExplorerSidebarProps) => void;
  onTreeLoaded?: (nodes: WorkspaceFileNode[]) => void;
  onSymbolsLoaded?: (symbols: CodeSymbolItem[]) => void;
  onCommitted?: (result: GitCommitResult) => void;
  fetchTreeFn?: typeof fetchFilesTree;
  fetchContentFn?: typeof fetchFileContent;
  saveContentFn?: typeof saveFileContent;
  fetchDiffFn?: typeof fetchStudioDiff;
  fetchSymbolsFn?: typeof fetchCodebaseSymbols;
  openInEditorFn?: typeof openInExternalEditor;
  fetchProposalFn?: typeof fetchGitProposal;
  commitFn?: typeof createGitCommit;
}

export function FilesWorkspace({
  initialActivePath = "core/main.py",
  initialActiveLine = 1,
  selectedPath,
  selectedLine,
  navigationTarget,
  initialViewMode = "code",
  initialSidebarTab = "tree",
  initialSaveError,
  saveError,
  renderSidebarInShell = false,
  preferTextareaFallback = false,
  onSidebarStateChange,
  onTreeLoaded,
  onSymbolsLoaded,
  onCommitted,
  fetchTreeFn = fetchFilesTree,
  fetchContentFn = fetchFileContent,
  saveContentFn = saveFileContent,
  fetchDiffFn = fetchStudioDiff,
  fetchSymbolsFn = fetchCodebaseSymbols,
  openInEditorFn = openInExternalEditor,
  fetchProposalFn = fetchGitProposal,
  commitFn = createGitCommit,
}: FilesWorkspaceProps): React.JSX.Element {
  const resolvedInitialPath = navigationTarget?.path ?? selectedPath ?? initialActivePath;
  const resolvedInitialLine = navigationTarget?.line ?? selectedLine ?? initialActiveLine;

  const [tree, setTree] = useState<WorkspaceFileNode[]>([]);
  const [treeResolved, setTreeResolved] = useState(false);
  const [symbols, setSymbols] = useState<CodeSymbolItem[]>([]);
  const [diffHunks, setDiffHunks] = useState<FileDiffHunk[]>([]);
  const [sidebarTab, setSidebarTab] = useState<FilesExplorerTab>(initialSidebarTab);
  const [viewMode, setViewMode] = useState<FilesViewMode>(initialViewMode);

  const [activePath, setActivePath] = useState<string>(resolvedInitialPath);
  const [seedErrorPath, setSeedErrorPath] = useState<string>(resolvedInitialPath);
  const [activeLine, setActiveLine] = useState<number>(resolvedInitialLine);
  const [openPaths, setOpenPaths] = useState<string[]>([resolvedInitialPath]);

  const [buffers, setBuffers] = useState<Record<string, string>>({});
  const [languages, setLanguages] = useState<Record<string, string>>({});
  const [aiSeqByPath, setAiSeqByPath] = useState<Record<string, number>>({});
  const [dirtyByPath, setDirtyByPath] = useState<Record<string, boolean>>({});
  const [runtimeSaveErrors, setRuntimeSaveErrors] = useState<Record<string, string>>({});
  const [clearedSeedErrors, setClearedSeedErrors] = useState<Record<string, boolean>>({});

  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [saveAsOpen, setSaveAsOpen] = useState(false);
  const [saveAsTarget, setSaveAsTarget] = useState("");
  const [commitModalOpen, setCommitModalOpen] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const initialPathRef = useRef(resolvedInitialPath);
  const onSidebarStateChangeRef = useRef(onSidebarStateChange);
  onSidebarStateChangeRef.current = onSidebarStateChange;
  const onTreeLoadedRef = useRef(onTreeLoaded);
  onTreeLoadedRef.current = onTreeLoaded;
  const onSymbolsLoadedRef = useRef(onSymbolsLoaded);
  onSymbolsLoadedRef.current = onSymbolsLoaded;

  const tabMovesFocusRef = useRef(false);
  const [tabMovesFocus, setTabMovesFocus] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const pendingCursorOffsetRef = useRef<number | null>(null);

  const monacoContainerRef = useRef<HTMLDivElement | null>(null);
  const monacoEditorRef = useRef<MonacoEditorInstance | null>(null);
  const isSyncingMonacoRef = useRef(false);
  const [monacoReady, setMonacoReady] = useState(false);
  const [monacoFailed, setMonacoFailed] = useState(false);

  const editorHintId = useId();
  const saveAsInputId = useId();

  useEffect(() => {
    let cancelled = false;
    fetchTreeFn()
      .then((nodes) => {
        if (cancelled) return;
        setTree(nodes);
        onTreeLoadedRef.current?.(nodes);
        const files = flattenFiles(nodes);
        setTreeResolved(true);
        if (!files.some((f) => f.path === initialPathRef.current)) {
          const first = files[0]?.path ?? "";
          setSeedErrorPath(first);
          setActivePath(first);
          setOpenPaths(first ? [first] : []);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setTreeResolved(true);
        setStatusMessage(`Failed to load workspace tree: ${err instanceof Error ? err.message : "unknown error"}`);
      });
    fetchDiffFn()
      .then((hunks) => { if (!cancelled) setDiffHunks(hunks); })
      .catch((err) => {
        if (!cancelled) setStatusMessage(`Failed to load diff: ${err instanceof Error ? err.message : "unknown error"}`);
      });
    fetchSymbolsFn()
      .then((items) => {
        if (cancelled) return;
        setSymbols(items);
        onSymbolsLoadedRef.current?.(items);
      })
      .catch((err) => {
        if (!cancelled) setStatusMessage(`Failed to load symbols: ${err instanceof Error ? err.message : "unknown error"}`);
      });
    return () => { cancelled = true; };
  }, [fetchDiffFn, fetchSymbolsFn, fetchTreeFn]);

  const loadedPathsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    if (!activePath || !treeResolved || loadedPathsRef.current.has(activePath)) {
      return;
    }
    let cancelled = false;

    fetchContentFn(activePath)
      .then((res) => {
        if (cancelled) return;
        loadedPathsRef.current.add(activePath);
        setBuffers((prev) =>
          prev[activePath] !== undefined ? prev : { ...prev, [activePath]: res.content },
        );
        setLanguages((prev) => ({ ...prev, [activePath]: res.language }));
        if (typeof res.aiRecordSeq === "number") {
          setAiSeqByPath((prev) => ({ ...prev, [activePath]: res.aiRecordSeq! }));
        }
      })
      .catch((err) => {
        if (!cancelled) setStatusMessage(`Failed to load ${activePath}: ${err instanceof Error ? err.message : "unknown error"}`);
      });

    return () => {
      cancelled = true;
    };
  }, [activePath, fetchContentFn, treeResolved]);

  const flatFiles = useMemo(() => flattenFiles(tree), [tree]);

  const effectiveSaveErrors = useMemo(() => {
    const map: Record<string, string> = {};
    for (const node of flatFiles) {
      if (node.saveError && !clearedSeedErrors[node.path]) {
        map[node.path] = node.saveError;
      }
    }
    const seedError = saveError ?? initialSaveError;
    if (seedError && !clearedSeedErrors[seedErrorPath]) {
      map[seedErrorPath] = seedError;
    }
    for (const [p, err] of Object.entries(runtimeSaveErrors)) {
      map[p] = err;
    }
    return map;
  }, [clearedSeedErrors, flatFiles, initialSaveError, runtimeSaveErrors, saveError, seedErrorPath]);

  const activeSaveError = effectiveSaveErrors[activePath];
  const activeContent = buffers[activePath] ?? "";
  const activeLanguage = languages[activePath] ?? "plaintext";
  const isLargeFile = activeContent.length > LARGE_FILE_BYTES;
  const monacoLanguage = isLargeFile ? "plaintext" : activeLanguage;
  const activeContentRef = useRef(activeContent);
  activeContentRef.current = activeContent;
  const monacoLanguageRef = useRef(monacoLanguage);
  monacoLanguageRef.current = monacoLanguage;

  const activeAiSeq = useMemo(() => {
    if (typeof aiSeqByPath[activePath] === "number") return aiSeqByPath[activePath];
    const treeNode = flatFiles.find((n) => n.path === activePath);
    if (typeof treeNode?.aiRecordSeq === "number") return treeNode.aiRecordSeq;
    return diffHunks.find((h) => h.path === activePath)?.aiRecordSeq;
  }, [activePath, aiSeqByPath, diffHunks, flatFiles]);

  const changedCount = useMemo(
    () =>
      flatFiles.filter(
        (n) => Boolean(n.gitStatus || n.dirty || dirtyByPath[n.path] || effectiveSaveErrors[n.path]),
      ).length,
    [dirtyByPath, effectiveSaveErrors, flatFiles],
  );

  const openFileTab = useCallback((path: string, line = 1) => {
    setActivePath(path);
    setActiveLine(line);
    setOpenPaths((prev) => (prev.includes(path) ? prev : [...prev, path]));
  }, []);

  const externalNavKey = navigationTarget
    ? `${navigationTarget.path}:${navigationTarget.line ?? 1}:${navigationTarget.nonce ?? 0}`
    : selectedPath
      ? `${selectedPath}:${selectedLine ?? 1}`
      : "";
  const prevNavKeyRef = useRef(externalNavKey);

  useEffect(() => {
    if (!externalNavKey || externalNavKey === prevNavKeyRef.current) return;
    prevNavKeyRef.current = externalNavKey;
    const targetPath = navigationTarget?.path ?? selectedPath;
    if (targetPath) {
      openFileTab(targetPath, navigationTarget?.line ?? selectedLine ?? 1);
      setViewMode("code");
    }
  }, [externalNavKey, navigationTarget, openFileTab, selectedLine, selectedPath]);

  const handleSelectSymbol = useCallback(
    (sym: CodeSymbolItem) => {
      openFileTab(sym.path, sym.line);
      setViewMode("code");
    },
    [openFileTab],
  );

  const updateBufferContent = useCallback((path: string, nextValue: string) => {
    setBuffers((prev) => ({ ...prev, [path]: nextValue }));
    setDirtyByPath((prev) => ({ ...prev, [path]: true }));
  }, []);

  const handleSave = useCallback(
    async (targetPath: string, overrideSourcePath?: string) => {
      if (savingRef.current) return;
      const sourcePath = overrideSourcePath ?? targetPath;
      const contentToWrite = buffers[sourcePath] ?? "";
      savingRef.current = true;
      setSaving(true);
      try {
        const res = await saveContentFn(targetPath, contentToWrite);
        if (!res.ok) {
          setRuntimeSaveErrors((prev) => ({ ...prev, [sourcePath]: res.error || "write failed" }));
          return;
        }
        setRuntimeSaveErrors((prev) => {
          const next = { ...prev };
          delete next[sourcePath];
          delete next[targetPath];
          return next;
        });
        setClearedSeedErrors((prev) => ({ ...prev, [sourcePath]: true, [targetPath]: true }));
        setDirtyByPath((prev) => ({ ...prev, [sourcePath]: false, [targetPath]: false }));
        setSaveAsOpen(false);
        setStatusMessage(`Saved ${res.path}`);
      } catch (err) {
        setRuntimeSaveErrors((prev) => ({
          ...prev,
          [sourcePath]: err instanceof Error ? err.message : "write failed",
        }));
      } finally {
        savingRef.current = false;
        setSaving(false);
      }
    },
    [buffers, saveContentFn],
  );

  useEffect(() => {
    const onWindowKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || document.querySelector('[role="dialog"]')) return;
      if ((event.metaKey || event.ctrlKey) && !event.shiftKey && !event.altKey && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (event.repeat || savingRef.current) return;
        void handleSave(activePath);
      }
    };
    window.addEventListener("keydown", onWindowKeyDown);
    return () => window.removeEventListener("keydown", onWindowKeyDown);
  }, [activePath, handleSave]);

  useEffect(() => {
    if (preferTextareaFallback || typeof window === "undefined") return;
    let cancelled = false;
    const win = window as unknown as { monaco?: MonacoGlobal; require?: AmdRequireFunction };

    const ensureMonacoCss = () => {
      if (!document.querySelector(`link[href="${MONACO_SELF_CSS_HREF}"]`)) {
        const link = document.createElement("link");
        link.rel = "stylesheet";
        link.href = MONACO_SELF_CSS_HREF;
        link.dataset.keelwayMonacoCss = "true";
        document.head.appendChild(link);
      }
    };

    const activateMonacoViaAmd = (): boolean => {
      if (win.monaco?.editor) {
        ensureMonacoCss();
        if (!cancelled) setMonacoReady(true);
        return true;
      }
      if (typeof win.require === "function" && typeof win.require.config === "function") {
        ensureMonacoCss();
        win.require.config({ paths: { vs: "/studio/assets/monaco/vs" } });
        win.require(
          ["vs/editor/editor.main"],
          () => { if (!cancelled) setMonacoReady(true); },
          () => { if (!cancelled) setMonacoFailed(true); },
        );
        return true;
      }
      return false;
    };

    if (activateMonacoViaAmd() || import.meta.env.MODE === "test") {
      return () => { cancelled = true; };
    }

    ensureMonacoCss();
    let script = document.querySelector<HTMLScriptElement>(`script[src="${MONACO_SELF_LOADER_SRC}"]`);
    const onLoad = () => { if (!activateMonacoViaAmd() && !cancelled) setMonacoFailed(true); };
    const onError = () => { if (!cancelled) setMonacoFailed(true); };

    if (!script) {
      script = document.createElement("script");
      script.src = MONACO_SELF_LOADER_SRC;
      script.async = true;
      script.dataset.keelwayMonaco = "self-hosted";
      document.head.appendChild(script);
    }
    script.addEventListener("load", onLoad);
    script.addEventListener("error", onError);
    return () => {
      cancelled = true;
      script?.removeEventListener("load", onLoad);
      script?.removeEventListener("error", onError);
    };
  }, [preferTextareaFallback]);

  const useMonaco = monacoReady && !monacoFailed && !preferTextareaFallback && viewMode === "code";

  useEffect(() => {
    if (!useMonaco || !monacoContainerRef.current) return;
    const monaco = (window as unknown as { monaco?: MonacoGlobal }).monaco;
    if (!monaco?.editor) return;

    try {
      monaco.editor.defineTheme("keelway-dark", {
        base: "vs-dark",
        inherit: true,
        rules: [],
        colors: { "editor.background": "#09090b" },
      });
      monaco.editor.defineTheme("keelway-light", {
        base: "vs",
        inherit: true,
        rules: [],
        colors: { "editor.background": "#f8fafc" },
      });
      const currentTheme =
        document.documentElement.getAttribute("data-theme") === "light" ? "keelway-light" : "keelway-dark";

      const instance = monaco.editor.create(monacoContainerRef.current, {
        value: activeContentRef.current,
        language: monacoLanguageRef.current,
        theme: currentTheme,
        automaticLayout: true,
        minimap: { enabled: false },
      });
      monacoEditorRef.current = instance;
      const sub = instance.onDidChangeModelContent(() => {
        if (isSyncingMonacoRef.current) return;
        updateBufferContent(activePath, instance.getValue());
      });
      const themeObserver = new MutationObserver(() => {
        monaco.editor.setTheme(
          document.documentElement.getAttribute("data-theme") === "light" ? "keelway-light" : "keelway-dark",
        );
      });
      themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
      return () => {
        themeObserver.disconnect();
        sub.dispose();
        instance.dispose();
        monacoEditorRef.current = null;
      };
    } catch {
      setMonacoFailed(true);
    }
  }, [activePath, updateBufferContent, useMonaco]);

  useEffect(() => {
    if (!useMonaco) return;
    const inst = monacoEditorRef.current;
    if (!inst) return;
    if (inst.getValue() !== activeContent) {
      isSyncingMonacoRef.current = true;
      try {
        inst.setValue(activeContent);
      } finally {
        isSyncingMonacoRef.current = false;
      }
    }
    const monaco = (window as unknown as { monaco?: MonacoGlobal }).monaco;
    const model = inst.getModel?.();
    if (model && monaco?.editor.setModelLanguage) {
      monaco.editor.setModelLanguage(model, monacoLanguage);
    }
  }, [activeContent, activeLanguage, isLargeFile, monacoLanguage, useMonaco]);

  useEffect(() => {
    if (!useMonaco) return;
    const inst = monacoEditorRef.current;
    if (!inst) return;
    inst.revealLineInCenter?.(activeLine);
    inst.setPosition?.({ lineNumber: activeLine, column: 1 });
  }, [activePath, activeLine, useMonaco]);

  useLayoutEffect(() => {
    if (pendingCursorOffsetRef.current !== null && textareaRef.current) {
      const pos = pendingCursorOffsetRef.current;
      pendingCursorOffsetRef.current = null;
      textareaRef.current.setSelectionRange(pos, pos);
    }
  }, [activeContent]);

  const handleTextareaKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && !event.shiftKey && !event.altKey && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (event.repeat || savingRef.current) return;
      void handleSave(activePath);
      return;
    }
    if (event.key === "Escape") {
      tabMovesFocusRef.current = true;
      setTabMovesFocus(true);
      return;
    }
    if (event.key === "Tab") {
      if (tabMovesFocusRef.current) {
        tabMovesFocusRef.current = false;
        setTabMovesFocus(false);
        return;
      }
      event.preventDefault();
      const el = event.currentTarget;
      const start = el.selectionStart ?? activeContent.length;
      const end = el.selectionEnd ?? start;
      const next = `${activeContent.slice(0, start)}  ${activeContent.slice(end)}`;
      pendingCursorOffsetRef.current = start + 2;
      updateBufferContent(activePath, next);
      return;
    }
    if (event.key === "Shift" || event.key === "Control" || event.key === "Alt" || event.key === "Meta") {
      return;
    }
    if (!event.metaKey && !event.ctrlKey && !event.altKey) {
      tabMovesFocusRef.current = false;
      if (tabMovesFocus) setTabMovesFocus(false);
    }
  };

  const sidebarProps: FilesExplorerSidebarProps = useMemo(
    () => ({
      tree,
      symbols,
      activeTab: sidebarTab,
      onTabChange: setSidebarTab,
      activePath,
      dirtyByPath,
      saveErrorsByPath: effectiveSaveErrors,
      onSelectFile: (p: string) => openFileTab(p, 1),
      onSelectSymbol: handleSelectSymbol,
    }),
    [activePath, dirtyByPath, effectiveSaveErrors, handleSelectSymbol, openFileTab, sidebarTab, symbols, tree],
  );

  useEffect(() => {
    onSidebarStateChangeRef.current?.(sidebarProps);
  }, [sidebarProps]);

  const lineCount = useMemo(() => Math.max(1, activeContent.split("\n").length), [activeContent]);

  return (
    <div className="flex h-full min-h-[480px] w-full flex-col overflow-hidden bg-canvas text-fg md:flex-row">
      {!renderSidebarInShell ? (
        <aside
          aria-label="Files explorer"
          className="flex w-full shrink-0 flex-col overflow-hidden border-b border-border bg-chrome md:w-sidebar md:border-b-0 md:border-e"
        >
          <FilesExplorerSidebar {...sidebarProps} />
        </aside>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-chrome px-3 py-1.5">
          <div role="group" aria-label="Open file tabs" className="flex min-w-0 flex-wrap items-center gap-1">
            {openPaths.map((path) => {
              const isCurrent = path === activePath;
              const fileErr = effectiveSaveErrors[path];
              const isDirty = Boolean(dirtyByPath[path]);
              return (
                <button
                  key={path}
                  type="button"
                  aria-current={isCurrent ? "true" : undefined}
                  onClick={() => openFileTab(path, 1)}
                  className={`inline-flex min-h-ctrl-sm items-center gap-1.5 rounded-xs border px-2.5 py-1 text-xs transition-colors duration-fast ease-state ${
                    isCurrent
                      ? "border-border-strong bg-surface text-fg"
                      : "border-transparent bg-transparent text-fg-muted hover:bg-surface-elevated hover:text-fg"
                  }`}
                >
                  <code dir="ltr" className="unicode-bidi-isolate font-mono">{basenameOf(path)}</code>
                  {fileErr ? (
                    <SemanticBadge kind="not-saved" detail={fileErr} />
                  ) : isDirty ? (
                    <span className="rounded-xs border border-border-control/50 bg-surface-elevated px-1 font-mono text-[10px] text-fg-muted">
                      Modified
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            <div role="group" aria-label="Editor view mode" className="inline-flex items-center rounded-sm border border-border-strong bg-surface p-0.5">
              {([{ mode: "code", label: "Code" }, { mode: "unified", label: "Unified diff" }, { mode: "split", label: "Split diff" }] as const).map(({ mode, label }) => (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={viewMode === mode}
                  onClick={() => setViewMode(mode)}
                  className={`rounded-xs px-2 py-1 text-xs font-medium transition-colors duration-fast ease-state ${viewMode === mode ? "bg-accent-subtle text-accent" : "text-fg-muted hover:text-fg"}`}
                >
                  {label}
                </button>
              ))}
            </div>

            <Button
              size="sm"
              variant="secondary"
              disabled={!activePath}
              onClick={() => void openInEditorFn(activePath, activeLine).then((res) => setStatusMessage(`Opened ${res.target} in ${res.editor}`))}
            >
              Open in VS Code
            </Button>

            <Button size="sm" variant="primary" onClick={() => setCommitModalOpen(true)}>
              {`Commit ${changedCount} ${changedCount === 1 ? "file" : "files"}...`}
            </Button>
          </div>
        </div>

        {activeSaveError ? (
          <div className="border-b border-border px-3 py-2">
            <CalloutBanner
              variant="runtime-unreachable"
              title={`Could not save ${activePath} (${activeSaveError})`}
              description="Your edits are still held safely in the in-memory buffer. Free disk space or save to another path."
              actions={
                <>
                  <Button size="sm" variant="primary" shortcutHint="⌘S" loading={saving} onClick={() => void handleSave(activePath)}>
                    Retry save
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => { setSaveAsTarget(`${activePath}.bak`); setSaveAsOpen((prev) => !prev); }}>
                    Save as...
                  </Button>
                </>
              }
            />
            {saveAsOpen ? (
              <form
                onSubmit={(e) => { e.preventDefault(); if (saveAsTarget.trim()) void handleSave(saveAsTarget.trim(), activePath); }}
                className="mt-2 flex flex-wrap items-center gap-2 rounded-sm border border-border-strong bg-surface p-2"
              >
                <label htmlFor={saveAsInputId} className="text-xs font-medium text-fg">Save copy as</label>
                <input
                  id={saveAsInputId}
                  type="text"
                  dir="ltr"
                  value={saveAsTarget}
                  onChange={(e) => setSaveAsTarget(e.target.value)}
                  className="unicode-bidi-isolate min-h-ctrl-sm flex-1 rounded-xs border border-border-control bg-canvas px-2.5 py-1 font-mono text-xs text-fg"
                />
                <Button type="submit" size="sm" variant="primary" loading={saving}>Save copy</Button>
              </form>
            ) : null}
          </div>
        ) : null}

        {isLargeFile ? (
          <div role="status" className="border-b border-border bg-surface-elevated px-3 py-1.5 text-xs text-fg-muted">
            Large file (&gt;512 KB) · syntax decorations paused to preserve responsiveness.
          </div>
        ) : null}

        {viewMode === "code" && !activePath ? (
          <div className="flex min-h-0 flex-1 items-center justify-center bg-code text-xs text-fg-dim">
            No file open — select a file in the workspace tree.
          </div>
        ) : viewMode === "code" ? (
          <div className="flex min-h-0 flex-1 overflow-hidden bg-code">
            <div
              data-testid="provenance-gutter"
              className="flex w-24 shrink-0 select-none flex-col border-e border-border bg-chrome/60 py-2.5 pe-2 ps-2 font-mono text-[11px] leading-5 text-fg-dim"
            >
              {Array.from({ length: Math.min(lineCount, 200) }, (_, i) => {
                const ln = i + 1;
                const showAi = ln === 1 && typeof activeAiSeq === "number";
                return (
                  <div key={ln} className="flex items-center justify-between gap-1">
                    <span className="truncate text-[10px] text-accent">{showAi ? `AI #${activeAiSeq}` : ""}</span>
                    <span className={`tabular-nums ${ln === activeLine ? "font-bold text-fg" : ""}`}>{ln}</span>
                  </div>
                );
              })}
            </div>

            {useMonaco ? (
              <div ref={monacoContainerRef} data-testid="monaco-editor-host" className="min-h-0 flex-1" />
            ) : (
              <textarea
                ref={textareaRef}
                aria-label={`Code editor for ${activePath}`}
                aria-describedby={editorHintId}
                dir="ltr"
                spellCheck={false}
                value={activeContent}
                onFocus={() => { tabMovesFocusRef.current = false; setTabMovesFocus(false); }}
                onChange={(e) => updateBufferContent(activePath, e.target.value)}
                onKeyDown={handleTextareaKeyDown}
                className="unicode-bidi-isolate min-h-0 flex-1 resize-none bg-code p-2.5 font-mono text-code leading-5 text-fg focus:outline-none"
              />
            )}
          </div>
        ) : (
          <FilesDiffView mode={viewMode} hunks={diffHunks} activePath={activePath} />
        )}

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border bg-chrome px-3 py-1 text-[11px] text-fg-muted">
          <div className="flex items-center gap-2.5 font-mono">
            <code dir="ltr" className="unicode-bidi-isolate text-fg">{activePath || "No file open"}</code>
            {activePath ? (
              <>
                <span className="tabular-nums">{`Ln ${activeLine}`}</span>
                <span>{activeLanguage}</span>
              </>
            ) : null}
            {typeof activeAiSeq === "number" ? <SemanticBadge kind="ai" detail={`#${activeAiSeq}`} /> : null}
          </div>
          <div className="flex items-center gap-3">
            {statusMessage ? <span role="status" className="font-mono text-fg">{statusMessage}</span> : null}
            <span id={editorHintId} className="font-mono text-fg-dim">
              {tabMovesFocus
                ? "Esc armed: next Tab moves focus (Tab indents · Esc then Tab moves focus)"
                : "Tab indents · Esc then Tab moves focus"}
            </span>
          </div>
        </div>
      </div>

      <FilesCommitModal
        open={commitModalOpen}
        onOpenChange={setCommitModalOpen}
        fetchProposalFn={fetchProposalFn}
        commitFn={commitFn}
        onCommitted={(res) => {
          setStatusMessage(`Committed ${res.commitSha.slice(0, 7)} on ${res.branch}`);
          onCommitted?.(res);
        }}
      />
    </div>
  );
}
