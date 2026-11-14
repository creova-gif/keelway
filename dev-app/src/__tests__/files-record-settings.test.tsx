import React from "react";
import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FilesWorkspace } from "@/components/screens/FilesWorkspace";
import type { CodeSymbolItem, FileDiffHunk, GitCommitProposal, WorkspaceFileNode } from "@/lib/types";
import { runAxe } from "@/test/setup";
import "@/styles/tokens.css";

const SAMPLE_TREE: WorkspaceFileNode[] = [
  {
    path: "core", name: "core", type: "directory",
    children: [
      { path: "core/main.py", name: "main.py", type: "file", language: "python", gitStatus: "M", aiRecordSeq: 1283 },
      { path: "core/security/policy.py", name: "policy.py", type: "file", language: "python", gitStatus: "A" },
      { path: "core/legacy.py", name: "legacy.py", type: "file", language: "python", gitStatus: "D" },
    ],
  },
  { path: "notes.txt", name: "notes.txt", type: "file", language: "plaintext", gitStatus: "U" },
];

const SAMPLE_SYMBOLS: CodeSymbolItem[] = [
  { name: "health_check", kind: "function", path: "core/main.py", line: 8, signature: "async def health_check()" },
  { name: "requires_human_quorum", kind: "function", path: "core/security/policy.py", line: 14, signature: "def requires_human_quorum(tier: int)" },
];

const SAMPLE_DIFFS: FileDiffHunk[] = [
  {
    path: "core/main.py", oldStart: 4, newStart: 4, additions: 2, deletions: 1, aiRecordSeq: 1283,
    lines: [
      { type: "hunk", content: "@@ -4,3 +4,4 @@" },
      { type: "context", oldLine: 4, newLine: 4, content: "app = FastAPI()" },
      { type: "del", oldLine: 5, content: 'CSP_POLICY = "default-src *"' },
      { type: "add", newLine: 5, content: "_STUDIO_CSP = \"default-src 'self'\"" },
      { type: "add", newLine: 6, content: 'REFERRER_POLICY = "no-referrer"' },
    ],
  },
];

describe("FilesWorkspace (Screen 05)", () => {
  it("renders 240px Tree | Changes | Symbols sidebar with Git M/A/D/U badges, dirty counts, and symbol navigation", async () => {
    const user = userEvent.setup();
    const openInEditorFn = vi.fn().mockResolvedValue({ ok: true, editor: "vscode", target: "core/security/policy.py:14" });
    const fetchContentFn = vi.fn(async (path: string) => ({
      path,
      language: "python",
      aiRecordSeq: path === "core/main.py" ? 1283 : undefined,
      content: path === "core/security/policy.py" ? "def requires_human_quorum(tier: int) -> bool:\n    return tier >= 2\n" : "app = FastAPI()\n",
    }));

    const onTreeLoaded = vi.fn();
    const onSymbolsLoaded = vi.fn();
    const fetchTreeFn = vi.fn(async () => SAMPLE_TREE);
    const fetchDiffFn = vi.fn(async () => SAMPLE_DIFFS);
    const fetchSymbolsFn = vi.fn(async () => SAMPLE_SYMBOLS);

    const { rerender, container } = render(
      <React.StrictMode>
        <FilesWorkspace
          fetchTreeFn={fetchTreeFn}
          fetchContentFn={fetchContentFn}
          fetchDiffFn={fetchDiffFn}
          fetchSymbolsFn={fetchSymbolsFn}
          openInEditorFn={openInEditorFn}
          onTreeLoaded={onTreeLoaded}
          onSymbolsLoaded={onSymbolsLoaded}
        />
      </React.StrictMode>,
    );

    const sidebar = await screen.findByRole("complementary", { name: /Files explorer/i });
    expect(sidebar).toHaveClass("w-sidebar");
    expect(onTreeLoaded).toHaveBeenCalledWith(SAMPLE_TREE);
    expect(onSymbolsLoaded).toHaveBeenCalledWith(SAMPLE_SYMBOLS);
    for (const status of ["M", "A", "D", "U"]) {
      expect(within(sidebar).getByText(status)).toBeInTheDocument();
    }

    const changesTab = within(sidebar).getByRole("tab", { name: /Changes/i });
    expect(changesTab).toHaveTextContent("4");
    await user.click(changesTab);
    expect(within(sidebar).getByText(/main\.py/)).toBeInTheDocument();
    expect(within(sidebar).getByText(/notes\.txt/)).toBeInTheDocument();

    await user.click(within(sidebar).getByRole("tab", { name: /Symbols/i }));
    const filterInput = within(sidebar).getByPlaceholderText(/Filter symbols/i);
    await user.type(filterInput, "nonexistent_symbol");
    expect(within(sidebar).getByText("No matching symbols.")).toBeInTheDocument();
    await user.clear(filterInput);

    await user.click(within(sidebar).getByRole("button", { name: /requires_human_quorum/i }));
    await waitFor(() => expect(fetchContentFn).toHaveBeenCalledWith("core/security/policy.py"));
    expect(await screen.findByText(/Ln 14/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Open in VS Code/i }));
    expect(openInEditorFn).toHaveBeenCalledWith("core/security/policy.py", 14);

    // Dirty edit in policy.py must survive external selectedPath/selectedLine navigation
    const policyEditor = await screen.findByRole("textbox", { name: /Code editor for core\/security\/policy\.py/i });
    fireEvent.change(policyEditor, { target: { value: "# unsaved local edit\n" } });
    rerender(
      <React.StrictMode>
        <FilesWorkspace
          selectedPath="core/main.py"
          selectedLine={8}
          fetchTreeFn={fetchTreeFn}
          fetchContentFn={fetchContentFn}
          fetchDiffFn={fetchDiffFn}
          fetchSymbolsFn={fetchSymbolsFn}
          openInEditorFn={openInEditorFn}
        />
      </React.StrictMode>,
    );
    expect(await screen.findByText(/Ln 8/i)).toBeInTheDocument();
    const tabsGroup = within(container).getByRole("group", { name: /Open file tabs/i });
    const policyTab = within(tabsGroup).getByRole("button", { name: /policy\.py/i });
    expect(policyTab).toHaveTextContent("Modified");
    await user.click(policyTab);
    expect(await screen.findByRole("textbox", { name: /Code editor for core\/security\/policy\.py/i })).toHaveValue(
      "# unsaved local edit\n",
    );
  });

  it("surfaces explicit 'Not saved · disk full' badge and persistent recovery bar, clearing on Retry save or Cmd+S", async () => {
    const user = userEvent.setup();
    const saveContentFn = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, path: "core/main.py", bytesWritten: 0, error: "disk full" })
      .mockResolvedValueOnce({ ok: true, path: "core/main.py", bytesWritten: 64 });

    const { container } = render(
      <FilesWorkspace fetchTreeFn={async () => SAMPLE_TREE} saveContentFn={saveContentFn} />,
    );

    const editor = await screen.findByRole("textbox", { name: /Code editor for core\/main\.py/i });
    await user.click(editor);
    fireEvent.keyDown(editor, { key: "s", metaKey: true });

    const notSavedBadge = await screen.findByText("Not saved · disk full");
    expect(notSavedBadge.closest("[data-badge-kind='not-saved']")).toHaveClass("text-warning");
    expect(container.querySelector("[data-unlabelled-dot]")).toBeNull();

    const retryBtn = screen.getByRole("button", { name: /Retry save/i });
    expect(retryBtn.querySelector("kbd")).toHaveTextContent("⌘S");
    expect(screen.getByRole("button", { name: /Save as\.\.\./i })).toBeInTheDocument();

    await user.click(retryBtn);
    await waitFor(() => {
      expect(saveContentFn).toHaveBeenCalledTimes(2);
      expect(screen.queryByText("Not saved · disk full")).toBeNull();
    });

    // Seed saveError="disk full" stays pinned to main.py tab when switching to notes.txt
    const seeded = render(<FilesWorkspace fetchTreeFn={async () => SAMPLE_TREE} saveError="disk full" />);
    const tabsGroup = within(seeded.container).getByRole("group", { name: /Open file tabs/i });
    expect(await within(tabsGroup).findByText("Not saved · disk full")).toBeInTheDocument();
    await user.click(await within(seeded.container).findByRole("button", { name: /notes\.txt/i }));
    const mainTab = within(tabsGroup).getByRole("button", { name: /main\.py/i });
    const notesTab = within(tabsGroup).getByRole("button", { name: /notes\.txt/i });
    expect(mainTab).toHaveTextContent("Not saved · disk full");
    expect(notesTab).not.toHaveTextContent("Not saved");
    seeded.unmount();
  });

  it("enforces WCAG 2.1.2 no-keyboard-trap (Tab + Shift+Tab), large-file notice, and AMD Monaco setValue sync guard", async () => {
    const user = userEvent.setup();
    const { unmount } = render(
      <FilesWorkspace fetchTreeFn={async () => SAMPLE_TREE} fetchContentFn={async (path) => ({ path, language: "python", content: "x".repeat(520 * 1024) })} />,
    );

    expect(await screen.findByText(/Tab indents · Esc then Tab moves focus/i)).toBeInTheDocument();
    expect(await screen.findByText(/Large file \(>512 KB\)/i)).toBeInTheDocument();
    const editor = screen.getByRole("textbox", { name: /Code editor for core\/main\.py/i }) as HTMLTextAreaElement;

    await user.click(editor);
    editor.setSelectionRange(0, 0);
    await user.keyboard("{Tab}");
    expect(editor.value.startsWith("  ")).toBe(true);
    expect(document.activeElement).toBe(editor);

    await user.keyboard("{Escape}");
    const rawTabCheck = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
    fireEvent(editor, rawTabCheck);
    expect(rawTabCheck.defaultPrevented).toBe(false);

    // Escape -> Shift keydown -> Shift+Tab must NOT reset Esc-mode on bare Shift keydown
    await user.keyboard("{Escape}");
    fireEvent.keyDown(editor, { key: "Shift", shiftKey: true });
    const shiftTabCheck = new KeyboardEvent("keydown", { key: "Tab", shiftKey: true, bubbles: true, cancelable: true });
    fireEvent(editor, shiftTabCheck);
    expect(shiftTabCheck.defaultPrevented).toBe(false);

    await user.keyboard("{Escape}");
    await user.tab();
    expect(document.activeElement).not.toBe(editor);

    await user.click(editor);
    await user.keyboard("a{Tab}");
    expect(document.activeElement).toBe(editor);
    unmount();

    // Verify AMD window.require + editor.main.css + setValue sync guard + cursor position decoupling
    const disposeSpy = vi.fn();
    const defineThemeSpy = vi.fn();
    const requireConfigSpy = vi.fn();
    const setPositionSpy = vi.fn();
    let currentVal = "";
    const changeHolder: { cb: (() => void) | null } = { cb: null };
    const amdRequire = Object.assign(
      vi.fn((deps: string[], cb: () => void) => {
        if (deps.includes("vs/editor/editor.main")) {
          (window as unknown as Record<string, unknown>).monaco = {
            editor: {
              defineTheme: defineThemeSpy, setTheme: vi.fn(),
              create: vi.fn((_el: HTMLElement, opts: { value?: string }) => {
                currentVal = opts.value ?? "";
                return {
                  getValue: () => currentVal,
                  setValue: (v: string) => { currentVal = v; changeHolder.cb?.(); },
                  setPosition: setPositionSpy,
                  revealLineInCenter: vi.fn(),
                  onDidChangeModelContent: (fn: () => void) => { changeHolder.cb = fn; return { dispose: vi.fn() }; },
                  dispose: disposeSpy,
                };
              }),
            },
          };
          cb();
        }
      }),
      { config: requireConfigSpy },
    );
    (window as unknown as Record<string, unknown>).require = amdRequire;
    try {
      const mounted = render(<FilesWorkspace initialActiveLine={5} fetchTreeFn={async () => SAMPLE_TREE} fetchContentFn={async (path) => ({ path, language: "python", content: "app = FastAPI()\n" })} />);
      await waitFor(() => expect(defineThemeSpy).toHaveBeenCalledWith("keelway-dark", expect.objectContaining({ colors: { "editor.background": "#090d12" } })));
      expect(defineThemeSpy).toHaveBeenCalledWith("keelway-light", expect.objectContaining({ colors: { "editor.background": "#f8fafc" } }));
      expect(requireConfigSpy).toHaveBeenCalledWith({ paths: { vs: "/studio/assets/monaco/vs" } });
      expect(document.head.querySelector('link[href="/studio/assets/monaco/vs/editor/editor.main.css"]')).not.toBeNull();
      await waitFor(() => expect(currentVal).toBe("app = FastAPI()\n"));
      const openTabs = within(mounted.container).getByRole("group", { name: /Open file tabs/i });
      expect(within(openTabs).getByRole("button", { name: /main\.py/i })).not.toHaveTextContent("Modified");
      const initialPosCalls = setPositionSpy.mock.calls.length;
      act(() => {
        currentVal = "app = FastAPI()\n# user typed\n";
        changeHolder.cb?.();
      });
      await waitFor(() => expect(within(openTabs).getByRole("button", { name: /main\.py/i })).toHaveTextContent("Modified"));
      expect(setPositionSpy).toHaveBeenCalledTimes(initialPosCalls);
      mounted.unmount();
      expect(disposeSpy).toHaveBeenCalledTimes(1);
    } finally {
      document.head.querySelectorAll("[data-keelway-monaco-css], [data-keelway-monaco]").forEach((el) => el.remove());
      delete (window as unknown as Record<string, unknown>).monaco;
      delete (window as unknown as Record<string, unknown>).require;
    }
  });

  it("switches Code | Unified diff | Split diff with dual-cue +/- lines, AI #1283 gutter, and commits via Radix Dialog", async () => {
    const user = userEvent.setup();
    const fetchProposalFn = vi.fn(async (): Promise<GitCommitProposal> => ({
      clean: false, branch: "feat/unified-dev-app", filesCount: 2, patchHash: "9a8b7c6d",
      files: [{ path: "core/main.py", status: "M" }, { path: "core/security/policy.py", status: "A" }],
      proposedTitle: "feat(core): enforce strict studio CSP",
      proposedMessage: "feat(core): enforce strict studio CSP\n\n- [M] core/main.py",
    }));
    const commitFn = vi.fn(async (message: string) => ({
      ok: true, commitSha: "f0e1d2c3b4a59687", branch: "feat/unified-dev-app", message, author: "You <local@keelway.dev>", clean: true,
    }));

    const { container } = render(
      <FilesWorkspace fetchTreeFn={async () => SAMPLE_TREE} fetchDiffFn={async () => SAMPLE_DIFFS} fetchProposalFn={fetchProposalFn} commitFn={commitFn} />,
    );

    expect((await screen.findAllByText(/AI #1283/i)).length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /Unified diff/i }));
    const addLine = container.querySelector("[data-diff-line='add']") as HTMLElement;
    const delLine = container.querySelector("[data-diff-line='del']") as HTMLElement;
    expect(addLine.getAttribute("style")).toContain("--diff-add-bg");
    expect(delLine.getAttribute("style")).toContain("--diff-del-bg");
    expect(addLine).toHaveTextContent("+");
    expect(delLine).toHaveTextContent("-");

    await user.click(screen.getByRole("button", { name: /Split diff/i }));
    expect(container.querySelectorAll("[data-split-side='before']").length).toBeGreaterThan(0);
    expect(container.querySelectorAll("[data-split-side='after']").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/AI #1283/i).length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: /Commit 4 files/i }));
    const dialog = await screen.findByRole("dialog");
    expect(fetchProposalFn).toHaveBeenCalledTimes(1);
    const msgBox = await within(dialog).findByRole("textbox", { name: /Commit message/i });
    await waitFor(() => expect(msgBox).toHaveValue("feat(core): enforce strict studio CSP\n\n- [M] core/main.py"));

    await user.click(within(dialog).getByRole("button", { name: /^Commit changes$/i }));
    await waitFor(() => {
      expect(commitFn).toHaveBeenCalledWith(
        "feat(core): enforce strict studio CSP\n\n- [M] core/main.py",
        ["core/main.py", "core/security/policy.py"],
      );
    });
  });

  it("passes axe-core WCAG 2.2 AA across dark, light, dir='rtl', and while Commit Dialog is open", async () => {
    const user = userEvent.setup();
    try {
      for (const [theme, dir] of [["dark", "ltr"], ["light", "ltr"], ["dark", "rtl"]] as const) {
        document.documentElement.setAttribute("data-theme", theme);
        document.documentElement.setAttribute("dir", dir);

        const { unmount } = render(
          <main aria-label="Files workspace test host">
            <FilesWorkspace initialSaveError="disk full" />
          </main>,
        );
        await screen.findByRole("textbox", { name: /Code editor/i });
        expect(await runAxe(document.body)).toHaveNoViolations();

        if (theme === "dark" && dir === "rtl") {
          await user.click(screen.getByRole("button", { name: /Commit .* file/i }));
          await screen.findByRole("dialog");
          expect(await runAxe(document.body)).toHaveNoViolations();
        }
        unmount();
      }
    } finally {
      document.documentElement.setAttribute("data-theme", "dark");
      document.documentElement.setAttribute("dir", "ltr");
    }
  });
});
