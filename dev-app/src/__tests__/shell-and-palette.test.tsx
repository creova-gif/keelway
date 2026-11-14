import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DevAppShell } from "@/components/shell/DevAppShell";
import { CommandPalette } from "@/components/shell/CommandPalette";
import { OnboardingModal } from "@/components/shell/OnboardingModal";
import type {
  CodeSymbolItem,
  DoctorCheckItem,
  EgressTelemetryState,
  SidebarTaskItem,
  WorkspaceFileNode,
} from "@/lib/types";
import { runAxe } from "@/test/setup";
import "@/styles/tokens.css";

const SAMPLE_TASKS: SidebarTaskItem[] = [
  { id: "task-done-1", title: "Refactor loopback token middleware", status: "done", branch: "feat/loopback-auth", modelLabel: "coder-7b v2.5.1", updatedAt: "12m ago" },
  { id: "task-running-1", title: "Stream pytest suite in Seatbelt", status: "running", branch: "feat/unified-dev-app", modelLabel: "coder-7b v2.5.1", updatedAt: "1m ago" },
  { id: "task-approval-1", title: "Update CSP headers in core/main.py", status: "needs_approval", branch: "feat/csp-hardening", modelLabel: "coder-7b v2.5.1", updatedAt: "just now", pendingApprovalId: "prop-101" },
  { id: "task-queued-1", title: "Generate SPDX 2.3 SBOM snapshot", status: "queued", branch: "chore/sbom", modelLabel: "coder-7b v2.5.1", updatedAt: "5m ago" },
  { id: "task-approval-2", title: "Run alembic migration in sandbox", status: "needs_approval", branch: "feat/wal-migration", modelLabel: "coder-7b v2.5.1", updatedAt: "2m ago", pendingApprovalId: "prop-102" },
];

const SAMPLE_FILES: WorkspaceFileNode[] = [
  {
    path: "core",
    name: "core",
    type: "directory",
    children: [
      { path: "core/main.py", name: "main.py", type: "file", language: "python", gitStatus: "M" },
      { path: "core/security/policy.py", name: "policy.py", type: "file", language: "python" },
    ],
  },
  { path: "README.md", name: "README.md", type: "file", language: "markdown" },
];

const SAMPLE_SYMBOLS: CodeSymbolItem[] = [
  { name: "requires_human_quorum", kind: "function", path: "core/security/policy.py", line: 14, signature: "def requires_human_quorum(tier: int, network_egress: bool) -> bool" },
  { name: "VerifyChainService", kind: "class", path: "core/audit/ledger.py", line: 42 },
];

describe("Task 2 — 4-Rail DevAppShell, Honest 24px Status Bar, Cmd+K Palette & 2-Step Onboarding", () => {
  it("renders 48px Primary Rail, pins Needs approval tasks above running/queued/done with border-ochre, omits Right Gate Rail, and uses 0px sidebar on Record", () => {
    const onSelectSection = vi.fn();
    const onSelectTask = vi.fn();

    const { container, rerender } = render(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={onSelectSection}
        tasks={SAMPLE_TASKS}
        activeTaskId="task-running-1"
        onSelectTask={onSelectTask}
      >
        <div>Task conversation stream</div>
      </DevAppShell>,
    );

    const primaryNav = screen.getByRole("navigation", { name: /Primary/i });
    expect(primaryNav).toHaveClass("w-rail");

    const tasksRailBtn = within(primaryNav).getByRole("button", { name: "Tasks" });
    const filesRailBtn = within(primaryNav).getByRole("button", { name: "Files" });
    const recordRailBtn = within(primaryNav).getByRole("button", { name: "Record" });
    const settingsRailBtn = within(primaryNav).getByRole("button", { name: "Settings" });

    expect(tasksRailBtn).toHaveAttribute("aria-current", "page");
    expect(filesRailBtn).not.toHaveAttribute("aria-current");
    expect(recordRailBtn).not.toHaveAttribute("aria-current");
    expect(settingsRailBtn).not.toHaveAttribute("aria-current");

    // Strictly NO Right Gate Rail (01c) anywhere in the DOM
    expect(container.querySelector('[data-rail="gate"]')).toBeNull();
    expect(screen.queryByRole("complementary", { name: /Gate/i })).toBeNull();

    // Needs approval queue pinning inside <aside aria-label="Tasks">
    const tasksSidebar = screen.getByRole("complementary", { name: "Tasks" });
    expect(tasksSidebar).toHaveClass("w-sidebar");

    const taskButtons = within(tasksSidebar).getAllByRole("button", {
      name: /Update CSP headers|Run alembic migration|Stream pytest suite|Generate SPDX 2\.3|Refactor loopback token/i,
    });
    expect(taskButtons).toHaveLength(5);

    // Both needs_approval tasks MUST sort above running, queued, and done regardless of input order
    expect(taskButtons[0]).toHaveTextContent("Update CSP headers in core/main.py");
    expect(taskButtons[1]).toHaveTextContent("Run alembic migration in sandbox");
    expect(taskButtons[2]).toHaveTextContent("Stream pytest suite in Seatbelt");
    expect(taskButtons[3]).toHaveTextContent("Generate SPDX 2.3 SBOM snapshot");
    expect(taskButtons[4]).toHaveTextContent("Refactor loopback token middleware");

    expect(taskButtons[0]).toHaveClass("border-ochre");
    expect(taskButtons[1]).toHaveClass("border-ochre");
    expect(taskButtons[2]).not.toHaveClass("border-ochre");

    // Custom contextSidebarContent renders cleanly on non-Record sections (e.g. Files)
    rerender(
      <DevAppShell
        activeSection="files"
        onSelectSection={onSelectSection}
        contextSidebarLabel="Files explorer"
        contextSidebarContent={<div>Workspace file tree</div>}
      >
        <div>Code editor surface</div>
      </DevAppShell>,
    );
    expect(screen.getByRole("complementary", { name: "Files explorer" })).toHaveClass("w-sidebar");

    // When activeSection === "record", the 240px left context sidebar is omitted (0px) even if tasks/contextSidebarContent exist
    rerender(
      <DevAppShell
        activeSection="record"
        onSelectSection={onSelectSection}
        tasks={SAMPLE_TASKS}
        contextSidebarLabel="Should not render"
        contextSidebarContent={<div>Hidden on record</div>}
      >
        <div>Full-width SHA-256 Record table</div>
      </DevAppShell>,
    );
    expect(screen.queryByRole("complementary", { name: "Tasks" })).toBeNull();
    expect(screen.queryByRole("complementary", { name: "Should not render" })).toBeNull();
    expect(within(primaryNav).getByRole("button", { name: "Record" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("supports Skip links, F6 / Shift+F6 landmark cycling, Cmd+1..3 / Cmd+J / Cmd+Shift+A, and protects browser Cmd+Shift+R reload when isDesktopApp={false}", async () => {
    const user = userEvent.setup();
    const onSelectSection = vi.fn();
    const onJumpToApprovalHeading = vi.fn();
    const onToggleLogsDrawer = vi.fn();

    const { rerender } = render(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={onSelectSection}
        tasks={SAMPLE_TASKS}
        pendingApprovalCount={2}
        onJumpToApprovalHeading={onJumpToApprovalHeading}
        reviewDrawerOpen
        reviewDrawerContent={<div>Diff inspector content</div>}
        defaultLogsDrawerOpen={false}
        onToggleLogsDrawer={onToggleLogsDrawer}
        isDesktopApp={false}
      >
        <div>Main workspace body</div>
      </DevAppShell>,
    );

    // First two Tab stops are Skip to Agent workspace and Jump to pending approval (2)
    await user.tab();
    const skipMain = screen.getByRole("link", { name: "Skip to Agent workspace" });
    expect(skipMain).toHaveFocus();

    await user.tab();
    const jumpApproval = screen.getByRole("button", { name: "Jump to pending approval (2)" });
    expect(jumpApproval).toHaveFocus();
    await user.click(jumpApproval);
    expect(onJumpToApprovalHeading).toHaveBeenCalledTimes(1);

    // Cmd+J opens Logs drawer so all 5 landmarks participate in F6 cycle
    fireEvent.keyDown(window, { key: "j", metaKey: true });
    expect(onToggleLogsDrawer).toHaveBeenCalledWith(true);

    const sidebar = screen.getByRole("complementary", { name: "Tasks" });
    const main = screen.getByRole("main", { name: "Agent workspace" });
    const review = screen.getByRole("complementary", { name: "Review" });
    const logs = screen.getByRole("region", { name: /Logs and terminal/i });
    const statusBar = screen.getByRole("contentinfo", { name: /Workspace status bar/i });

    // Cmd+1 -> Primary/Sidebar, Cmd+2 -> Main, Cmd+3 -> Review
    fireEvent.keyDown(window, { key: "1", metaKey: true });
    expect(sidebar).toHaveFocus();

    fireEvent.keyDown(window, { key: "2", metaKey: true });
    expect(main).toHaveFocus();

    fireEvent.keyDown(window, { key: "3", metaKey: true });
    expect(review).toHaveFocus();

    // F6 forward cycle: from Sidebar -> Main -> Review -> Logs -> Status bar -> Sidebar
    sidebar.focus();
    expect(sidebar).toHaveFocus();

    fireEvent.keyDown(window, { key: "F6" });
    expect(main).toHaveFocus();

    fireEvent.keyDown(window, { key: "F6" });
    expect(review).toHaveFocus();

    fireEvent.keyDown(window, { key: "F6" });
    expect(logs).toHaveFocus();

    fireEvent.keyDown(window, { key: "F6" });
    expect(statusBar).toHaveFocus();

    fireEvent.keyDown(window, { key: "F6" });
    expect(sidebar).toHaveFocus();

    // Shift+F6 backward cycle: from Sidebar -> Status bar -> Logs
    fireEvent.keyDown(window, { key: "F6", shiftKey: true });
    expect(statusBar).toHaveFocus();

    fireEvent.keyDown(window, { key: "F6", shiftKey: true });
    expect(logs).toHaveFocus();

    // Cmd+Shift+A jumps to pending approval heading
    fireEvent.keyDown(window, { key: "A", metaKey: true, shiftKey: true });
    expect(onJumpToApprovalHeading).toHaveBeenCalledTimes(2);

    // Browser chord safety: Meta+Shift+R with isDesktopApp={false} MUST NOT preventDefault or switch to record
    const browserReloadEvent = new KeyboardEvent("keydown", {
      key: "R",
      metaKey: true,
      shiftKey: true,
      bubbles: true,
      cancelable: true,
    });
    const notCancelled = window.dispatchEvent(browserReloadEvent);
    expect(notCancelled).toBe(true);
    expect(browserReloadEvent.defaultPrevented).toBe(false);
    expect(onSelectSection).not.toHaveBeenCalledWith("record");

    // Desktop app shell: Meta+Shift+R with isDesktopApp={true} DOES preventDefault and switches to record
    rerender(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={onSelectSection}
        tasks={SAMPLE_TASKS}
        isDesktopApp={true}
      >
        <div>Main workspace body</div>
      </DevAppShell>,
    );

    const desktopRecordEvent = new KeyboardEvent("keydown", {
      key: "R",
      metaKey: true,
      shiftKey: true,
      bubbles: true,
      cancelable: true,
    });
    window.dispatchEvent(desktopRecordEvent);
    expect(desktopRecordEvent.defaultPrevented).toBe(true);
    expect(onSelectSection).toHaveBeenCalledWith("record");
  });

  it("renders all 5 Honest 24px Status Bar modes without false zero-egress claims and opens Radix Details popover", async () => {
    const user = userEvent.setup();
    const onSwitchToLocalModel = vi.fn();
    const onGoOffline = vi.fn();

    const baseUnmeasured: EgressTelemetryState = {
      mode: "unmeasured",
      cloudCallsCount: 0,
      bytesSent: null,
      airGapLocked: false,
      endpoints: [],
    };

    // 1a. Default unmeasured + offlineSetting={true}
    const { rerender } = render(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={() => {}}
        egress={baseUnmeasured}
        offlineSetting={true}
      >
        <div>Workspace</div>
      </DevAppShell>,
    );

    const bar = screen.getByRole("contentinfo", { name: /Workspace status bar/i });
    expect(bar).toHaveClass("h-statusbar");
    expect(bar).toHaveTextContent("Offline (setting)");
    expect(bar).toHaveTextContent("sent: unmeasured");
    expect(bar).toHaveTextContent("No counter yet");
    expect(bar).not.toHaveTextContent("0 B sent");

    // 1b. unmeasured + deployPending={true}
    rerender(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={() => {}}
        egress={baseUnmeasured}
        deployPending={true}
      >
        <div>Workspace</div>
      </DevAppShell>,
    );
    expect(bar).toHaveTextContent("Network: deploy pending, nothing sent yet");
    expect(bar).toHaveTextContent("sent: unmeasured");
    expect(bar).not.toHaveTextContent("0 B sent");

    // 1c. unmeasured + offlineSetting={false}
    rerender(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={() => {}}
        egress={baseUnmeasured}
        offlineSetting={false}
      >
        <div>Workspace</div>
      </DevAppShell>,
    );
    expect(bar).toHaveTextContent("Connected");
    expect(bar).toHaveTextContent("sent: unmeasured");
    expect(bar).toHaveTextContent("No counter yet");

    // 2. measured_offline
    rerender(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={() => {}}
        egress={{
          mode: "measured_offline",
          cloudCallsCount: 0,
          bytesSent: 0,
          airGapLocked: false,
          endpoints: [],
          lastCheckedAt: "14:02 ET",
        }}
      >
        <div>Workspace</div>
      </DevAppShell>,
    );
    expect(bar).toHaveTextContent(/Offline · verified/i);
    expect(bar).toHaveTextContent("0 B sent");
    expect(bar).toHaveTextContent("Live");

    // 3. air_gapped_verified
    rerender(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={() => {}}
        egress={{
          mode: "air_gapped_verified",
          cloudCallsCount: 0,
          bytesSent: null,
          airGapLocked: true,
          endpoints: [],
          lastCheckedAt: "14:03 ET",
        }}
      >
        <div>Workspace</div>
      </DevAppShell>,
    );
    expect(bar).toHaveTextContent(/Air-gapped · verified/i);
    expect(bar).toHaveTextContent("sent: unmeasured");

    // 4. unknown_probe_failed
    rerender(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={() => {}}
        egress={{
          mode: "unknown_probe_failed",
          cloudCallsCount: 0,
          bytesSent: null,
          airGapLocked: false,
          endpoints: [],
        }}
      >
        <div>Workspace</div>
      </DevAppShell>,
    );
    expect(bar).toHaveTextContent("Network: unknown (probe failed)");
    expect(bar).toHaveTextContent("sent: unmeasured");

    // 5. connected_warning + Radix Egress Details Popover
    rerender(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={() => {}}
        onSwitchToLocalModel={onSwitchToLocalModel}
        onGoOffline={onGoOffline}
        egress={{
          mode: "connected_warning",
          cloudCallsCount: 2,
          bytesSent: 14_336,
          airGapLocked: false,
          endpoints: [
            {
              host: "api.frontier-cloud.example",
              purpose: "Code synthesis",
              calls: 2,
              bytesSent: 14_336,
              modelId: "frontier-sonnet-4",
            },
          ],
        }}
      >
        <div>Workspace</div>
      </DevAppShell>,
    );

    expect(bar).toHaveTextContent("Connected");
    expect(bar).toHaveTextContent("Cloud used (2)");
    expect(bar).toHaveTextContent("14.0 KB sent");
    expect(bar).toHaveTextContent("Live");

    const detailsTrigger = within(bar).getByRole("button", { name: "Details" });
    await user.click(detailsTrigger);

    const popoverHeading = await screen.findByText("Data sent this session");
    expect(popoverHeading).toBeInTheDocument();
    expect(screen.getByText("api.frontier-cloud.example")).toBeInTheDocument();
    expect(screen.getByText("Every request is also a Record entry.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Switch to local model" }));
    expect(onSwitchToLocalModel).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Go offline" }));
    expect(onGoOffline).toHaveBeenCalledTimes(1);
  });

  it("supports Cmd+K CommandPalette prefix modes (>, #, @, /), keyboard selection, partial/total empty states, and enforces P-10 no-approval safety invariant", async () => {
    const user = userEvent.setup();
    const onRunCommand = vi.fn();
    const onSelectTask = vi.fn();
    const onApproveSpy = vi.fn();

    render(
      <div>
        <CommandPalette
          tasks={SAMPLE_TASKS}
          files={SAMPLE_FILES}
          symbols={SAMPLE_SYMBOLS}
          onRunCommand={onRunCommand}
          onSelectTask={onSelectTask}
        />
      </div>,
    );

    // Open via Cmd+K shortcut
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    const dialog = await screen.findByRole("dialog", { name: /Command palette/i });

    // P-10 permanent safety footer & zero approval actions
    expect(within(dialog).getByText("Approvals are never run from here")).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /Allow once/i })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: /Allow always/i })).toBeNull();
    expect(within(dialog).queryByRole("button", { name: /^Deny$/i })).toBeNull();

    const searchInput = within(dialog).getByRole("combobox");

    // 1. `>` Commands & KStack skills mode
    await user.clear(searchInput);
    await user.type(searchInput, ">");
    expect(within(dialog).getByText(/\/office-hours/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/\/review/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/\/ship/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/Verify chain/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/Toggle Air-Gap/i)).toBeInTheDocument();

    // 2. `@` AST Symbols mode
    await user.clear(searchInput);
    await user.type(searchInput, "@quorum");
    expect(within(dialog).getByText("requires_human_quorum")).toBeInTheDocument();
    expect(within(dialog).getByText(/core\/security\/policy\.py:14/)).toBeInTheDocument();

    // 3. `/` Models & Settings mode
    await user.clear(searchInput);
    await user.type(searchInput, "/");
    expect(within(dialog).getByText(/coder-7b v2\.5\.1/i)).toBeInTheDocument();
    expect(within(dialog).getByText(/Permissions/i)).toBeInTheDocument();

    // 4. `#` Tasks mode + selecting a Needs approval task navigates without approving
    await user.clear(searchInput);
    await user.type(searchInput, "#CSP");
    const pendingTaskOption = within(dialog).getByRole("option", {
      name: /Update CSP headers in core\/main\.py/i,
    });
    expect(within(pendingTaskOption).getByText("Needs approval")).toBeInTheDocument();

    // Keyboard Enter activates navigation to task without approving
    await user.keyboard("{Enter}");
    expect(onSelectTask).toHaveBeenCalledWith("task-approval-1");
    expect(onApproveSpy).not.toHaveBeenCalled();

    // Reopen palette to verify ArrowDown/ArrowUp + partial & total empty states
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    const reopenedDialog = await screen.findByRole("dialog", { name: /Command palette/i });
    const reopenedInput = within(reopenedDialog).getByRole("combobox");

    // Partial empty state: matches a Command ("Verify chain") while Tasks and Files have 0 matches
    await user.type(reopenedInput, "Verify chain");
    expect(
      within(reopenedDialog).getByText(/Tasks and files: no matches for "Verify chain"/i),
    ).toBeInTheDocument();

    await user.keyboard("{ArrowDown}{ArrowUp}{Enter}");
    expect(onRunCommand).toHaveBeenCalledWith("verify-chain");

    // Total empty state + [Clear query] button
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    const emptyDialog = await screen.findByRole("dialog", { name: /Command palette/i });
    const emptyInput = within(emptyDialog).getByRole("combobox");
    await user.type(emptyInput, "zzzz_nonexistent_token_999");

    expect(
      within(emptyDialog).getByText('No matches for "zzzz_nonexistent_token_999"'),
    ).toBeInTheDocument();
    const clearBtn = within(emptyDialog).getByRole("button", { name: "Clear query" });
    await user.click(clearBtn);
    expect(emptyInput).toHaveValue("");
  });

  it("renders 2-Step OnboardingModal with Honest Defaults (Step 1) and Workspace + System Doctor checks (Step 2)", async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    const openWorkspaceSpy = vi.fn().mockResolvedValue({
      ok: true,
      path: "/Users/dev/keelway",
      branch: "feat/unified-dev-app",
      filesCount: 64,
    });

    const initialChecks: DoctorCheckItem[] = [
      {
        id: "sandbox-isolation",
        label: "OS Sandbox Isolation (Seatbelt / Bubblewrap)",
        status: "ok",
        detail: "Seatbelt profile active",
      },
      {
        id: "opencore-weights",
        label: "Local OpenCore Runtime (coder-7b v2.5.1)",
        status: "warning",
        detail: "Model cached on disk, warm-up pending",
        remediation: "Run `keelway opencore warmup` to preload weights into memory.",
      },
      {
        id: "audit-sqlite-wal",
        label: "Append-Only Audit Ledger (SQLite WAL)",
        status: "failed",
        detail: "Write lock held by stale PID",
        remediation: "Remove stale `.keelway/audit.db-shm` or restart local daemon.",
      },
    ];

    const rerunChecks: DoctorCheckItem[] = initialChecks.map((c) => ({
      ...c,
      status: "ok",
      detail: "Verified healthy",
      remediation: undefined,
    }));

    const fetchDoctorSpy = vi
      .fn<() => Promise<DoctorCheckItem[]>>()
      .mockResolvedValueOnce(initialChecks)
      .mockResolvedValueOnce(rerunChecks);

    render(
      <OnboardingModal
        open={true}
        onComplete={onComplete}
        defaultWorkspacePath="/Users/dev/keelway"
        openWorkspaceFn={openWorkspaceSpy}
        fetchDoctorFn={fetchDoctorSpy}
      />,
    );

    const dialog = screen.getByRole("dialog");

    // Step 1: 3 transparent sovereign default cards
    expect(within(dialog).getByText(/Local ·/i)).toBeInTheDocument();
    expect(within(dialog).getByText("coder-7b v2.5.1")).toBeInTheDocument();
    expect(within(dialog).getByText(/Runs on this machine via OpenCore/i)).toBeInTheDocument();

    expect(within(dialog).getByText("Ask every time")).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        /Only a person, at this keyboard, can approve edits, commands, or network calls/i,
      ),
    ).toBeInTheDocument();

    expect(within(dialog).getByText("Offline (setting)")).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        "Set to keep your use on this machine. Network use isn't measured yet.",
      ),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("No counter yet")).toBeInTheDocument();

    // Advance to Step 2
    await user.click(within(dialog).getByRole("button", { name: "Continue to workspace check" }));

    expect(fetchDoctorSpy).toHaveBeenCalledTimes(1);
    expect(await within(dialog).findByText("Seatbelt profile active")).toBeInTheDocument();

    // Verify non-color badges (Passed, Warning, Failed) and remediation text
    expect(within(dialog).getByText("Passed")).toBeInTheDocument();
    expect(within(dialog).getByText("Warning")).toBeInTheDocument();
    expect(within(dialog).getByText("Failed")).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Run `keelway opencore warmup` to preload weights/i),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Remove stale `\.keelway\/audit\.db-shm`/i),
    ).toBeInTheDocument();

    // Open workspace
    const wsInput = within(dialog).getByLabelText(/Workspace/i);
    await user.clear(wsInput);
    await user.type(wsInput, "/Users/dev/keelway-repo");
    await user.click(within(dialog).getByRole("button", { name: "Open workspace" }));
    expect(openWorkspaceSpy).toHaveBeenCalledWith("/Users/dev/keelway-repo");

    // Re-run doctor
    await user.click(within(dialog).getByRole("button", { name: "Re-run doctor" }));
    expect(fetchDoctorSpy).toHaveBeenCalledTimes(2);
    expect(await within(dialog).findAllByText("Passed")).toHaveLength(3);

    // Complete onboarding
    await user.click(within(dialog).getByRole("button", { name: "Start using Keelway" }));
    expect(onComplete).toHaveBeenCalledTimes(1);
  });

  it("renders Mobile Companion bottom navigation (<768px / isMobileCompanion) with >=44px min-h-11 touch targets", () => {
    render(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={() => {}}
        tasks={SAMPLE_TASKS}
        isMobileCompanion={true}
      >
        <div>Mobile companion view</div>
      </DevAppShell>,
    );

    const companionNav = screen.getByRole("navigation", { name: "Companion navigation" });
    for (const label of ["Approvals", "Tasks", "Record", "Status"]) {
      const btn = within(companionNav).getByRole("button", { name: new RegExp(`^${label}`, "i") });
      expect(btn).toHaveClass("min-h-11");
    }
  });

  it("passes WCAG 2.2 AA axe-core checks across DevAppShell, open CommandPalette, and OnboardingModal in Dark, Light, and RTL modes", async () => {
    for (const theme of ["dark", "light"] as const) {
      for (const dir of ["ltr", "rtl"] as const) {
        document.documentElement.setAttribute("data-theme", theme);
        document.documentElement.setAttribute("dir", dir);

        // 1. DevAppShell with Review + Logs drawers open
        const shellRender = render(
          <DevAppShell
            activeSection="tasks"
            onSelectSection={() => {}}
            tasks={SAMPLE_TASKS}
            pendingApprovalCount={2}
            reviewDrawerOpen={true}
            reviewDrawerContent={<div>Contextual diff review</div>}
            logsDrawerOpen={true}
            workspaceBranch="feat/unified-dev-app"
            activeModelLabel="coder-7b v2.5.1"
          >
            <section aria-label="Task stream">
              <h1>Update CSP headers</h1>
              <p>Awaiting human review.</p>
            </section>
          </DevAppShell>,
        );
        expect(await runAxe(shellRender.container)).toHaveNoViolations();
        shellRender.unmount();

        // 2. Open CommandPalette
        const paletteRender = render(
          <CommandPalette
            open={true}
            onOpenChange={() => {}}
            tasks={SAMPLE_TASKS}
            files={SAMPLE_FILES}
            symbols={SAMPLE_SYMBOLS}
          />,
        );
        expect(await runAxe(document.body)).toHaveNoViolations();
        paletteRender.unmount();

        // 3. Open OnboardingModal (Step 1 & Step 2)
        const onboardingStep1 = render(
          <OnboardingModal open={true} initialStep={1} onComplete={() => {}} />,
        );
        expect(await runAxe(document.body)).toHaveNoViolations();
        onboardingStep1.unmount();

        const onboardingStep2 = render(
          <OnboardingModal open={true} initialStep={2} onComplete={() => {}} />,
        );
        await screen.findByText(/OS Sandbox Isolation/i);
        expect(await runAxe(document.body)).toHaveNoViolations();
        onboardingStep2.unmount();
      }
    }

    document.documentElement.setAttribute("dir", "ltr");
    document.documentElement.setAttribute("data-theme", "dark");
  });
});
