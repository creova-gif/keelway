import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentsWorkspaceView } from "@/components/platform/AgentsWorkspaceView";
import { StepDebuggerAndBridgePanel } from "@/components/platform/StepDebuggerAndBridgePanel";
import { resetDebuggerFallbackStore, startDebuggerSession } from "@/lib/platformDebuggerApi";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  resetDebuggerFallbackStore();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 14C — Live Step-Through Debugger, 4D CodeLens & VS Code / Cursor Bridge", () => {
  it("Test 1: renders panel, adds before_shell_tool conditional breakpoint, starts debug session, and verifies PAUSED state, hit_reason, call stack, and frame_sha256", async () => {
    const user = userEvent.setup();
    render(<StepDebuggerAndBridgePanel workspaceId="default" activeRbacRole="owner" />);

    const panel = screen.getByRole("region", {
      name: "Live Step-Through Debugger and VS Code Cursor Bridge",
    });
    expect(panel).toHaveAttribute("id", "step-debugger-bridge-panel");
    expect(within(panel).getByText("READY")).toBeInTheDocument();

    // Seeded default breakpoint is listed
    expect(await within(panel).findByText("Pause when step spend > $0.25")).toBeInTheDocument();

    // Execution step buttons are disabled prior to PAUSED session
    expect(within(panel).getByRole("button", { name: "Step Over (F10)" })).toBeDisabled();
    expect(within(panel).getByRole("button", { name: "Step Into (F11)" })).toBeDisabled();
    expect(within(panel).getByRole("button", { name: "Continue (F5)" })).toBeDisabled();

    // Add conditional breakpoint: before_shell_tool
    const conditionSelect = within(panel).getByLabelText("Breakpoint condition type");
    await user.selectOptions(conditionSelect, "before_shell_tool");
    await user.click(within(panel).getByRole("button", { name: "Add Conditional Breakpoint" }));
    expect(await within(panel).findByText("Pause before shell_exec tool")).toBeInTheDocument();

    // Start Debug Session -> immediately pauses on step 2/3 (verify_ledger)
    await user.click(within(panel).getByRole("button", { name: "Start Debug Session" }));
    expect(await within(panel).findByText("PAUSED")).toBeInTheDocument();
    expect(within(panel).getByText("Step 2/3 · Depth 0")).toBeInTheDocument();
    expect(within(panel).getByText(/cost_usd_gt \(0\.31 > 0\.25\)/)).toBeInTheDocument();
    expect(within(panel).getByText(/before_shell_tool \(shell_exec\)/)).toBeInTheDocument();

    const stackList = within(panel).getByRole("list", { name: "Debugger call stack" });
    expect(within(stackList).getByText(/\[depth 0\] verify_ledger \(shell_exec\)/)).toBeInTheDocument();
    expect(within(stackList).getByText("finops-auditor")).toBeInTheDocument();

    const shaEl = within(panel).getByTestId("debugger-frame-sha256");
    expect(shaEl.textContent).toMatch(/^[0-9a-f]{64}$/);

    // Removing the added breakpoint removes its pill cleanly
    await user.click(
      within(panel).getByRole("button", { name: "Remove breakpoint Pause before shell_exec tool" }),
    );
    expect(within(panel).queryByText("Pause before shell_exec tool")).not.toBeInTheDocument();
  });

  it("Test 2: exercises Step Into (F11), Apply State Patch (mutation_count & frame_sha256 update), Step Over (F10), and Continue (F5) -> COMPLETED", async () => {
    const user = userEvent.setup();
    render(<StepDebuggerAndBridgePanel workspaceId="default" activeRbacRole="owner" />);

    const panel = screen.getByRole("region", {
      name: "Live Step-Through Debugger and VS Code Cursor Bridge",
    });

    await user.click(within(panel).getByRole("button", { name: "Start Debug Session" }));
    expect(await within(panel).findByText("PAUSED")).toBeInTheDocument();
    const initialSha = within(panel).getByTestId("debugger-frame-sha256").textContent;
    expect(initialSha).toMatch(/^[0-9a-f]{64}$/);

    // Step Into (F11) -> depth increases to 1
    await user.click(within(panel).getByRole("button", { name: "Step Into (F11)" }));
    expect(await within(panel).findByText("Step 2/3 · Depth 1")).toBeInTheDocument();
    const stackList = within(panel).getByRole("list", { name: "Debugger call stack" });
    expect(
      within(stackList).getByText(/\[depth 1\] verify_ledger::shell_exec \(shell_exec\)/),
    ).toBeInTheDocument();
    const shaAfterStepInto = within(panel).getByTestId("debugger-frame-sha256").textContent;
    expect(shaAfterStepInto).not.toBe(initialSha);

    // Apply State Patch (override_route: "keelway-core:7b") -> mutation_count increments & frame_sha256 updates
    expect(within(panel).getByText("Mutations: 0")).toBeInTheDocument();
    expect((within(panel).getByLabelText("State variable key") as HTMLInputElement).value).toBe(
      "override_route",
    );
    expect((within(panel).getByLabelText("State variable value") as HTMLInputElement).value).toBe(
      "keelway-core:7b",
    );
    await user.click(within(panel).getByRole("button", { name: "Apply State Patch" }));
    expect(await within(panel).findByText("Mutations: 1")).toBeInTheDocument();
    expect(within(panel).getByText(/"override_route": "keelway-core:7b"/)).toBeInTheDocument();
    const shaAfterPatch = within(panel).getByTestId("debugger-frame-sha256").textContent;
    expect(shaAfterPatch).toMatch(/^[0-9a-f]{64}$/);
    expect(shaAfterPatch).not.toBe(shaAfterStepInto);

    // Step Over (F10) -> advances to Step 3/3 (approve_payout) at Depth 0
    await user.click(within(panel).getByRole("button", { name: "Step Over (F10)" }));
    expect(await within(panel).findByText("Step 3/3 · Depth 0")).toBeInTheDocument();
    expect(within(panel).getByText(/approve_payout · p10_settlement/)).toBeInTheDocument();

    // Continue (F5) -> finishes workflow -> COMPLETED
    await user.click(within(panel).getByRole("button", { name: "Continue (F5)" }));
    expect(await within(panel).findByText("COMPLETED")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Step Over (F10)" })).toBeDisabled();
    expect(within(panel).getByRole("button", { name: "Continue (F5)" })).toBeDisabled();
  });

  it("Test 3: blocks secret tokens in state_patch with HTTP 422 DLP alert and enforces HTTP 403 RBAC denial for viewer role", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <StepDebuggerAndBridgePanel workspaceId="default" activeRbacRole="owner" />,
    );

    const panel = screen.getByRole("region", {
      name: "Live Step-Through Debugger and VS Code Cursor Bridge",
    });

    await user.click(within(panel).getByRole("button", { name: "Start Debug Session" }));
    expect(await within(panel).findByText("PAUSED")).toBeInTheDocument();

    // 1. Quick-test button triggers 422 DLP Policy Violation
    await user.click(within(panel).getByRole("button", { name: "Test Secret DLP Block" }));
    const dlpAlert = await within(panel).findByRole("alert");
    expect(dlpAlert).toHaveTextContent(/422/);
    expect(dlpAlert).toHaveTextContent(/DLP Policy Violation/i);
    expect(within(panel).getByText("Mutations: 0")).toBeInTheDocument();

    // 2. Manual sk-... secret entry via Apply State Patch also blocks with 422
    const valInput = within(panel).getByLabelText("State variable value");
    await user.clear(valInput);
    await user.type(valInput, "sk-proj-unsafeSecretToken123456");
    await user.click(within(panel).getByRole("button", { name: "Apply State Patch" }));
    expect(await within(panel).findByRole("alert")).toHaveTextContent(
      /HTTP 422 · DLP Policy Violation/i,
    );

    // 3. Switch to activeRbacRole="viewer" -> mutations rejected with HTTP 403 RBAC alert
    rerender(<StepDebuggerAndBridgePanel workspaceId="default" activeRbacRole="viewer" />);
    expect(within(panel).getByText("RBAC: viewer (read-only)")).toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: "Start Debug Session" }));
    const rbacAlert = await within(panel).findByRole("alert");
    expect(rbacAlert).toHaveTextContent(/HTTP 403/);
    expect(rbacAlert).toHaveTextContent(/RBAC Denied \(viewer\)/i);

    await user.click(within(panel).getByRole("button", { name: "Add Conditional Breakpoint" }));
    expect(await within(panel).findByRole("alert")).toHaveTextContent(/HTTP 403/);
  });

  it("Test 4: mounts in AgentsWorkspaceView, renders 4D CodeLens items & Cursor/VS Code attach URIs, wires /v1/platform/debugger/* headers, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=phase14-dbg-tok");
    const seenRequests: Array<{ pathname: string; method: string; auth: string | null; role: string | null; body: string }> = [];
    const realFetch = globalThis.fetch;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const pathname = new URL(url, "http://localhost").pathname;
      const method = (init?.method ?? "GET").toUpperCase();
      const hdrs = new Headers(init?.headers);
      const rawBody = typeof init?.body === "string" ? init.body : "";
      if (pathname.startsWith("/v1/platform/debugger")) {
        seenRequests.push({
          pathname,
          method,
          auth: hdrs.get("Authorization"),
          role: hdrs.get("X-Keelway-Role"),
          body: rawBody,
        });
      }
      if (pathname === "/v1/platform/debugger/codelens" && method === "GET") {
        return new Response(
          JSON.stringify({
            workspace_id: "default",
            workflow_id: "WF-STUDIO-01",
            file_path: "workflows/refund_agent.py",
            bridge: {
              cursor_attach_uri: "cursor://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01",
              vscode_attach_uri: "vscode://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01",
            },
            lenses: [
              {
                symbol: "verify_ledger",
                line_start: 14,
                model_checkpoint: "keelway-core:7b",
                p50_ms: 218,
                avg_cost_usd: 0.31,
                provenance_4d: "Apache-2.0 · Local Metal · Seatbelt-Confined · Zero-Egress",
                attached_breakpoints: 1,
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/debugger/sessions" && method === "POST") {
        return new Response(
          JSON.stringify({
            session_id: "dbg-live-backend-01",
            workspace_id: "default",
            workflow_id: "WF-STUDIO-01",
            status: "PAUSED",
            current_step_index: 1,
            step_depth: 0,
            total_steps: 3,
            hit_reason: "cost_usd_gt (0.31 > 0.25)",
            active_step: {
              node_id: "verify_ledger",
              agent_id: "shell-auditor",
              tool_name: "shell_exec",
              cost_usd: 0.31,
              hybrid_score: 0.42,
              requires_p10: false,
              line_number: 14,
            },
            variables: { claim_id: "CLM-402", refund_usd: 180 },
            call_stack: [{ depth: 0, node_id: "verify_ledger", agent_id: "shell-auditor", line_number: 14 }],
            mutation_count: 0,
            frame_sha256: "b".repeat(64),
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (typeof realFetch === "function" && !pathname.startsWith("/v1/")) {
        return realFetch(input, init);
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const { container } = render(
      <AgentsWorkspaceView
        experienceMode="builder"
        agents={[]}
        teams={[]}
        onCreateCustomAgent={() => {}}
        onDispatchTeam={() => {}}
        onUpdateAgentModel={() => {}}
        onJumpToIdeTask={() => {}}
        workspaceId="default"
        activeRbacRole="owner"
      />,
    );

    const panel = await screen.findByRole("region", {
      name: "Live Step-Through Debugger and VS Code Cursor Bridge",
    });

    // Verify 4D Routing CodeLens items normalized from live FastAPI schema (p50_ms + bridge.*_attach_uri)
    const lensList = within(panel).getByRole("list", { name: "4D routing CodeLens items" });
    expect(await within(lensList).findByText("verify_ledger")).toBeInTheDocument();
    expect(within(lensList).getByText(/keelway-core:7b · P50 218ms · \$0\.31/)).toBeInTheDocument();
    expect(within(lensList).queryByText(/undefinedms/i)).not.toBeInTheDocument();
    expect(within(lensList).getByText(/Seatbelt-Confined · Zero-Egress/)).toBeInTheDocument();

    // Verify Cursor & VS Code IDE attach URI links normalized from bridge.*
    const cursorLink = within(panel).getByRole("link", { name: "Attach in Cursor" });
    const vscodeLink = within(panel).getByRole("link", { name: "Attach in VS Code" });
    expect(cursorLink.getAttribute("href")).toContain(
      "cursor://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01",
    );
    expect(vscodeLink.getAttribute("href")).toContain(
      "vscode://keelway.vscode-keelway/attach?port=7420&workspace=default&workflow=WF-STUDIO-01",
    );

    // Start session -> normalizes live backend active_step & call_stack (defaulting tool_name + frame_index)
    await user.click(within(panel).getByRole("button", { name: "Start Debug Session" }));
    expect(await within(panel).findByText("PAUSED")).toBeInTheDocument();
    expect(cursorLink.getAttribute("href")).toContain("session=dbg-live-backend-01");
    const stackList = within(panel).getByRole("list", { name: "Debugger call stack" });
    expect(within(stackList).getByText(/\[depth 0\] verify_ledger \(shell_exec\)/)).toBeInTheDocument();
    expect(within(stackList).getByText("shell-auditor")).toBeInTheDocument();
    expect(within(panel).getByTestId("debugger-frame-sha256").textContent).toBe("b".repeat(64));

    await startDebuggerSession({ workspace_id: "default", initial_variables: { ticket: "T-1" } }, "owner");
    const initStateCall = seenRequests.find(
      (r) => r.pathname === "/v1/platform/debugger/sessions" && r.method === "POST" && r.body.includes("T-1"),
    );
    expect(initStateCall).toBeDefined();
    expect(JSON.parse(initStateCall!.body)).toMatchObject({
      initial_state: { ticket: "T-1" },
      initial_variables: { ticket: "T-1" },
    });

    expect(
      seenRequests.some(
        (r) =>
          r.pathname === "/v1/platform/debugger/codelens" &&
          r.auth === "Bearer phase14-dbg-tok" &&
          r.role === "owner",
      ),
    ).toBe(true);

    // Zero axe-core WCAG 2.2 AA violations in both dark and light themes
    expect((await axe(container)).violations).toHaveLength(0);
    document.documentElement.setAttribute("data-theme", "light");
    expect((await axe(container)).violations).toHaveLength(0);
  });
});
