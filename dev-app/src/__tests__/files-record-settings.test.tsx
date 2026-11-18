import React from "react";
import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FilesWorkspace } from "@/components/screens/FilesWorkspace";
import { RecordAuditLedger } from "@/components/screens/RecordAuditLedger";
import { SettingsWorkspace } from "@/components/screens/SettingsWorkspace";
import { App } from "@/App";
import { getFallbackAuditEntries, getFallbackMerkleProof } from "@/lib/apiFallbacks";
import type {
  AuditMerkleProof,
  ChainVerificationState,
  CodeSymbolItem,
  FileDiffHunk,
  GitCommitProposal,
  WorkspaceFileNode,
} from "@/lib/types";
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
    expect(sidebar).toHaveClass("w-full", "md:w-sidebar");
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
      await waitFor(() => expect(defineThemeSpy).toHaveBeenCalledWith("keelway-dark", expect.objectContaining({ colors: { "editor.background": "#09090b" } })));
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

describe("RecordAuditLedger (Screen 06)", () => {
  it("renders all 7 canonical forensic columns, model+prompt provenance, human-only approval, and keyboard row navigation", async () => {
    const user = userEvent.setup();
    const entries = getFallbackAuditEntries();

    render(
      <React.StrictMode>
        <RecordAuditLedger
          initialEntries={entries}
          initialChainState={{ status: "verified", totalEntries: 1283, merkleRoot: "e3b0c442", verifiedAt: "2026-11-14T02:15:00Z" }}
          defaultInspectorOpen={false}
        />
      </React.StrictMode>,
    );

    const table = screen.getByRole("table", { name: /Record SHA-256 audit ledger/i });
    const headers = within(table).getAllByRole("columnheader").map((th) => th.textContent?.trim());
    expect(headers).toEqual(["When (ET)", "Who", "What", "Model", "Approval", "Outcome", "Integrity"]);

    expect(within(table).getAllByText("coder-7b 2.5.1 · p-14").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("Allow once · you").length).toBeGreaterThan(0);
    expect(within(table).getByText("Denied · policy")).toBeInTheDocument();
    expect(within(table).getByText("Passed")).toBeInTheDocument();
    expect(within(table).getByText("Allowed")).toBeInTheDocument();
    expect(within(table).getByText("Blocked")).toBeInTheDocument();

    // Keyboard ArrowDown -> ArrowDown -> ArrowUp row navigation & inspector sync
    const row1283Btn = within(table).getByRole("button", { name: /#1283/i });
    const row1282Btn = within(table).getByRole("button", { name: /#1282/i });
    const row1279Btn = within(table).getByRole("button", { name: /#1279/i });
    row1283Btn.focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("complementary", { name: /Entry #1283 details/i })).toBeInTheDocument();

    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(row1282Btn);
    expect(await screen.findByRole("complementary", { name: /Entry #1282 details/i })).toBeInTheDocument();

    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(row1279Btn);
    expect(await screen.findByRole("complementary", { name: /Entry #1279 details/i })).toBeInTheDocument();

    await user.keyboard("{ArrowUp}");
    expect(document.activeElement).toBe(row1282Btn);
    expect(await screen.findByRole("complementary", { name: /Entry #1282 details/i })).toBeInTheDocument();
  });

  it("renders intact green chain verification vs broken chain alert (#1279) with Open entry #1279 & Export report recovery", async () => {
    const user = userEvent.setup();
    const entries = getFallbackAuditEntries();
    const exportBundleFn = vi.fn().mockResolvedValue({
      format: "keelway-record-bundle/v1",
      generatedAt: "2026-11-14T02:20:00Z",
      jsonl: '{"seq":1279}\n',
      csv: "seq,hash\n1279,7f6e5d4c\n",
      verifierScript: "#!/usr/bin/env python3\n",
      chainStatus: "broken" as const,
    });

    const intact = render(
      <RecordAuditLedger
        initialEntries={entries}
        initialChainState={{ status: "verified", totalEntries: 1283, merkleRoot: "e3b0c44298fc1c14" }}
        defaultInspectorOpen={false}
      />,
    );
    const verifiedBanner = screen.getByRole("status");
    expect(verifiedBanner).toHaveAttribute("data-callout-variant", "chain-verified");
    expect(verifiedBanner).toHaveTextContent("Chain verified · 1,283 entries · no gaps");
    intact.unmount();

    const brokenState: ChainVerificationState = {
      status: "broken",
      totalEntries: 1283,
      brokenAtSeq: 1279,
      expectedPrevHash: "9999aaaa",
      actualPrevHash: "00112233",
    };
    render(
      <RecordAuditLedger
        initialEntries={entries}
        initialChainState={brokenState}
        defaultInspectorOpen={false}
        exportBundleFn={exportBundleFn}
      />,
    );

    const alertBanner = screen.getByRole("alert");
    expect(alertBanner).toHaveAttribute("data-callout-variant", "chain-broken");
    expect(alertBanner).toHaveTextContent("Chain broken at entry #1279: hash doesn't match the previous entry");
    expect(alertBanner).toHaveTextContent("Entries after #1279 can't be trusted.");

    const brokenTable = screen.getByRole("table", { name: /Record SHA-256 audit ledger/i });
    expect(within(brokenTable).getByRole("button", { name: /Chain broken · #1279/i })).toBeInTheDocument();
    expect(within(brokenTable).getByRole("button", { name: /Untrusted · #1283/i })).toBeInTheDocument();

    // Filter out #1279 first, then verify Open entry #1279 clears filters and focuses #1279 row button
    await user.selectOptions(screen.getByLabelText(/Outcome/i), "passed");
    await user.click(within(alertBanner).getByRole("button", { name: /Open entry #1279/i }));
    const inspector = await screen.findByRole("complementary", { name: /Entry #1279 details/i });
    expect(inspector).toHaveClass("w-inspector");
    expect(within(inspector).getByText("Entry #1279")).toBeInTheDocument();
    await waitFor(() =>
      expect(document.activeElement).toBe(within(brokenTable).getByRole("button", { name: /#1279/i })),
    );

    await user.click(within(alertBanner).getByRole("button", { name: /Export report/i }));
    expect(exportBundleFn).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/keelway-record-bundle\/v1/i)).toBeInTheDocument();
  });

  it("opens 360px 4D Provenance & Merkle Inspector on #1283, jumps prev (#1282), triggers Open diff in Review, and closes on Escape", async () => {
    const user = userEvent.setup();
    const entries = getFallbackAuditEntries();
    const fetchMerkleProofFn = vi.fn(async (seq: number) => getFallbackMerkleProof(seq));
    const onOpenDiffInReview = vi.fn();
    const onSelectSeq = vi.fn();

    render(
      <RecordAuditLedger
        initialEntries={entries}
        initialChainState={{ status: "verified", totalEntries: 3 }}
        defaultInspectorOpen={false}
        fetchMerkleProofFn={fetchMerkleProofFn}
        onOpenDiffInReview={onOpenDiffInReview}
        onSelectSeq={onSelectSeq}
      />,
    );

    const table = screen.getByRole("table", { name: /Record SHA-256 audit ledger/i });
    await user.click(within(table).getByRole("button", { name: /#1283/i }));

    const inspector = await screen.findByRole("complementary", { name: /Entry #1283 details/i });
    expect(inspector).toHaveClass("w-inspector");
    expect(onSelectSeq).toHaveBeenCalledWith(1283);
    expect(fetchMerkleProofFn).toHaveBeenCalledWith(1283);

    expect(within(inspector).getByText(/sha256:9f4c2e8a71b0d43e6f92a1c88e051d2b/i)).toBeInTheDocument();
    expect(within(inspector).getByText(/local_loopback/i)).toBeInTheDocument();
    expect(within(inspector).getByText(/opencore-local/i)).toBeInTheDocument();
    expect(within(inspector).getByText(/8f3d9a12c4e7b0516a98e2d3f4c5b6a7/i)).toBeInTheDocument();
    expect(await within(inspector).findByText(/Verified/i)).toBeInTheDocument();
    expect(within(inspector).getByText(/2 sibling hashes/i)).toBeInTheDocument();

    await user.click(within(inspector).getByRole("button", { name: /Open diff in Review/i }));
    expect(onOpenDiffInReview).toHaveBeenCalledWith("core/main.py", 1283);

    await user.click(within(inspector).getByRole("button", { name: /\(#1282\)/i }));
    const prevInspector = await screen.findByRole("complementary", { name: /Entry #1282 details/i });
    expect(fetchMerkleProofFn).toHaveBeenCalledWith(1282);
    expect(within(prevInspector).getByRole("button", { name: /Open diff in Review/i })).toBeDisabled();

    // Escape while an open [role="dialog"] or defaultPrevented event is active MUST leave inspector open
    const modalStub = document.createElement("div");
    modalStub.setAttribute("role", "dialog");
    document.body.appendChild(modalStub);
    try {
      await user.keyboard("{Escape}");
      expect(screen.getByRole("complementary", { name: /Entry #1282 details/i })).toBeInTheDocument();
    } finally {
      modalStub.remove();
    }
    const preventedEsc = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
    preventedEsc.preventDefault();
    window.dispatchEvent(preventedEsc);
    expect(screen.getByRole("complementary", { name: /Entry #1282 details/i })).toBeInTheDocument();

    // Focus inside inspector restores focus to #1282 row button on Escape close
    within(prevInspector).getByRole("button", { name: /Close entry inspector/i }).focus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("complementary", { name: /Entry #1282 details/i })).toBeNull();
    expect(document.activeElement).toBe(within(table).getByRole("button", { name: /#1282/i }));
  });

  it("handles out-of-order Merkle proof races without stale flash, Merkle fetch errors, and stable fetchEntriesFn across selectedSeq updates", async () => {
    const entries = getFallbackAuditEntries();
    let resolve1283!: (proof: AuditMerkleProof) => void;
    let resolve1282!: (proof: AuditMerkleProof) => void;

    const fetchEntriesFn = vi.fn(async () => entries);
    const verifyChainFn = vi.fn(async (): Promise<ChainVerificationState> => ({ status: "verified", totalEntries: 3 }));
    const onChainStateChange = vi.fn();
    const fetchMerkleProofFn = vi.fn((seq: number) => {
      if (seq === 1283) {
        return new Promise<AuditMerkleProof>((res) => { resolve1283 = res; });
      }
      if (seq === 1282) {
        return new Promise<AuditMerkleProof>((res) => { resolve1282 = res; });
      }
      return Promise.reject(new Error("merkle db locked"));
    });

    const { rerender } = render(
      <RecordAuditLedger
        fetchEntriesFn={fetchEntriesFn}
        verifyChainFn={verifyChainFn}
        fetchMerkleProofFn={fetchMerkleProofFn}
        selectedSeq={1283}
        verifyRequestNonce={0}
        onChainStateChange={onChainStateChange}
      />,
    );

    expect(await screen.findByRole("complementary", { name: /Entry #1283 details/i })).toBeInTheDocument();
    expect(fetchEntriesFn).toHaveBeenCalledTimes(1);

    // Rapidly switch controlled selectedSeq 1283 -> 1282 BEFORE 1283 resolves; fetchEntriesFn must stay at 1 call
    rerender(
      <RecordAuditLedger
        fetchEntriesFn={fetchEntriesFn}
        verifyChainFn={verifyChainFn}
        fetchMerkleProofFn={fetchMerkleProofFn}
        selectedSeq={1282}
        verifyRequestNonce={0}
        onChainStateChange={onChainStateChange}
      />,
    );
    const inspector1282 = await screen.findByRole("complementary", { name: /Entry #1282 details/i });
    expect(fetchEntriesFn).toHaveBeenCalledTimes(1);
    expect(within(inspector1282).getByText(/Verifying Merkle inclusion path/i)).toBeInTheDocument();

    // Resolve #1282 first, then resolve stale #1283 with a distinct merkleRoot — #1282 proof must NOT be overwritten
    await act(async () => {
      resolve1282({ ...getFallbackMerkleProof(1282), merkleRoot: "root-for-1282-fresh" });
    });
    expect(await within(inspector1282).findByText("root-for-1282-fresh")).toBeInTheDocument();

    await act(async () => {
      resolve1283({ ...getFallbackMerkleProof(1283), merkleRoot: "stale-root-for-1283" });
    });
    expect(within(inspector1282).queryByText("stale-root-for-1283")).toBeNull();
    expect(within(inspector1282).getByText("root-for-1282-fresh")).toBeInTheDocument();

    // Switch to #1279 where fetchMerkleProofFn rejects -> shows clean error notice & verifyRequestNonce triggers re-verify
    rerender(
      <RecordAuditLedger
        fetchEntriesFn={fetchEntriesFn}
        verifyChainFn={verifyChainFn}
        fetchMerkleProofFn={fetchMerkleProofFn}
        selectedSeq={1279}
        verifyRequestNonce={1}
        onChainStateChange={onChainStateChange}
      />,
    );
    const inspector1279 = await screen.findByRole("complementary", { name: /Entry #1279 details/i });
    expect(fetchEntriesFn).toHaveBeenCalledTimes(1);
    expect(await within(inspector1279).findByText("Unable to load Merkle inclusion proof.")).toBeInTheDocument();
    await waitFor(() => expect(verifyChainFn).toHaveBeenCalledTimes(2));
    expect(onChainStateChange).toHaveBeenCalledWith(expect.objectContaining({ status: "verified", totalEntries: 3 }));
  });

  it("supports 6-dimension filtering, Verify chain, Export, error/retry/empty states, and passes axe-core across dark, light, and dir='rtl'", async () => {
    const user = userEvent.setup();
    const entries = getFallbackAuditEntries();
    const verifyChainFn = vi.fn().mockResolvedValue({
      status: "verified" as const,
      totalEntries: 3,
      merkleRoot: "e3b0c44298fc1c14",
      verifiedAt: "2026-11-14T02:25:00Z",
    });
    const exportBundleFn = vi.fn().mockResolvedValue({
      format: "keelway-record-bundle/v1",
      generatedAt: "2026-11-14T02:25:00Z",
      jsonl: '{"seq":1283}\n',
      csv: "seq,hash\n1283,8f3d9a12\n",
      verifierScript: "#!/usr/bin/env python3\n",
      chainStatus: "verified" as const,
    });

    // Loading, empty, and Error + Retry operational states
    const loadingView = render(<RecordAuditLedger initialEntries={[]} loading />);
    expect(screen.getByText(/Loading SHA-256 Record entries/i)).toBeInTheDocument();
    loadingView.unmount();

    const emptyView = render(<RecordAuditLedger initialEntries={[]} initialChainState={{ status: "verified", totalEntries: 0 }} />);
    expect(screen.getByText("No entries recorded yet")).toBeInTheDocument();
    emptyView.unmount();

    const failingFetch = vi.fn().mockRejectedValueOnce(new Error("sqlite wal busy")).mockResolvedValueOnce(entries);
    const errRender = render(<RecordAuditLedger fetchEntriesFn={failingFetch} verifyChainFn={verifyChainFn} />);
    expect(await screen.findByText(/sqlite wal busy/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Retry/i }));
    expect(await screen.findByText(/Showing 3 of 3 entries/i)).toBeInTheDocument();
    errRender.unmount();

    // Controlled selectedSeq jump from external caller (TasksWorkspace / App.tsx)
    const controlled = render(
      <RecordAuditLedger initialEntries={entries} initialChainState={{ status: "verified", totalEntries: 3 }} selectedSeq={1283} />,
    );
    expect(await screen.findByRole("complementary", { name: /Entry #1283 details/i })).toBeInTheDocument();
    controlled.rerender(
      <RecordAuditLedger initialEntries={entries} initialChainState={{ status: "verified", totalEntries: 3 }} selectedSeq={1279} />,
    );
    expect(await screen.findByRole("complementary", { name: /Entry #1279 details/i })).toBeInTheDocument();
    controlled.unmount();

    // Filter bar + Verify chain + Export + axe-core WCAG 2.2 AA
    try {
      for (const [theme, dir] of [["dark", "ltr"], ["light", "ltr"], ["dark", "rtl"]] as const) {
        document.documentElement.setAttribute("data-theme", theme);
        document.documentElement.setAttribute("dir", dir);

        const { unmount } = render(
          <main aria-label="Record workspace test host">
            <RecordAuditLedger
              initialEntries={entries}
              initialChainState={{ status: "verified", totalEntries: 3 }}
              verifyChainFn={verifyChainFn}
              exportBundleFn={exportBundleFn}
            />
          </main>,
        );

        expect(await screen.findByRole("complementary", { name: /Entry #1283 details/i })).toBeInTheDocument();

        if (theme === "dark" && dir === "ltr") {
          expect(screen.getByLabelText(/Target/i)).toBeInTheDocument();
          expect(screen.getByLabelText(/Who/i)).toBeInTheDocument();
          expect(screen.getByLabelText(/Action/i)).toBeInTheDocument();
          expect(screen.getByLabelText(/Model/i)).toBeInTheDocument();
          expect(screen.getByLabelText(/Date/i)).toBeInTheDocument();

          await user.selectOptions(screen.getByLabelText(/Who/i), "human");
          expect(screen.getByText("Showing 1 of 3 entries")).toBeInTheDocument();
          await user.selectOptions(screen.getByLabelText(/Who/i), "all");

          const outcomeSelect = screen.getByLabelText(/Outcome/i);
          await user.selectOptions(outcomeSelect, "blocked");
          expect(screen.getByText("Showing 1 of 3 entries")).toBeInTheDocument();
          const table = screen.getByRole("table", { name: /Record SHA-256 audit ledger/i });
          expect(within(table).getByRole("button", { name: /#1279/i })).toBeInTheDocument();
          expect(within(table).queryByRole("button", { name: /#1283/i })).toBeNull();

          const searchBox = screen.getByRole("searchbox", { name: /Search Record entries/i });
          await user.type(searchBox, "no_such_entry_xyz");
          expect(screen.getByText("No Record entries match the current filters")).toBeInTheDocument();

          await user.click(screen.getAllByRole("button", { name: /Clear filters/i })[0]);
          expect(screen.getByText("Showing 3 of 3 entries")).toBeInTheDocument();

          await user.click(screen.getByRole("button", { name: /Verify chain/i }));
          expect(verifyChainFn).toHaveBeenCalled();

          await user.click(screen.getByRole("button", { name: /Export…/i }));
          expect(exportBundleFn).toHaveBeenCalledTimes(1);
        }

        expect(await runAxe(document.body)).toHaveNoViolations();
        unmount();
      }
    } finally {
      document.documentElement.setAttribute("data-theme", "dark");
      document.documentElement.setAttribute("dir", "ltr");
    }
  });
});

describe("SettingsWorkspace & App Integration (Screens 08-11)", () => {
  it("renders Settings sub-navigation (8 sections) with prompt-drift callout and mounts unified App shell", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<SettingsWorkspace />);

    const nav = screen.getByRole("navigation", { name: /Settings sections/i });
    expect(within(nav).getByRole("button", { name: /Permissions & Manifests/i })).toHaveAttribute("aria-current", "page");
    expect(await screen.findByText("Prompt version changed: p-13 → p-14")).toBeInTheDocument();
    expect(screen.getByText("Only a person, at this keyboard")).toBeInTheDocument();

    await user.click(within(nav).getByRole("button", { name: /Network & Egress/i }));
    expect(
      await screen.findByText("Set to keep your use on this machine. Network use isn't measured yet."),
    ).toBeInTheDocument();
    unmount();

    window.history.replaceState({}, "", "/app/?token=smoke-tok");
    const appRender = render(<App />);
    try {
      const rail = screen.getByRole("navigation", { name: /Primary navigation/i });
      await user.click(within(rail).getByRole("button", { name: /^Settings$/i }));
      expect(await screen.findByText("Prompt version changed: p-13 → p-14")).toBeInTheDocument();
      expect(window.location.search).toContain("token=smoke-tok");
    } finally {
      appRender.unmount();
      window.history.replaceState({}, "", "/");
    }
  });
});
