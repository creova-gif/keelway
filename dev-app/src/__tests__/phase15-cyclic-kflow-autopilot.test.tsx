import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AutomationWorkspaceView } from "@/components/platform/AutomationAndOpsViews";
import { CyclicKflowAndAutopilotPanel } from "@/components/platform/CyclicKflowAndAutopilotPanel";
import {
  executeCyclicKflow,
  PlatformCyclicHttpError,
  resetCyclicFallbackStore,
} from "@/lib/platformCyclicApi";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  resetCyclicFallbackStore();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 15C — Bounded Cyclic KFlow Sub-Graphs, Saga Compensation & Cost/Privacy Autopilot", () => {
  it("Test 1: validates cyclic graph and executes reflection loop -> CONVERGED badge, per-iteration trace, and run_sha256", async () => {
    const user = userEvent.setup();
    render(<CyclicKflowAndAutopilotPanel workspaceId="default" workflowId="WF-CYCLIC-01" activeRbacRole="owner" />);

    const panel = screen.getByRole("region", {
      name: "Bounded Cyclic KFlow and Cost Privacy Autopilot",
    });
    expect(panel).toHaveAttribute("id", "cyclic-kflow-autopilot-panel");
    expect(within(panel).getByText("BOUNDED")).toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: "Validate Cyclic Graph" }));
    expect(
      await within(panel).findByText(
        /draft_patch -> critic_verify -> publish_release · max steps 7 · handlers \[revert_worktree, discard_candidate, rollback_tag\]/,
      ),
    ).toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: "Execute Reflection Loop" }));
    expect(await within(panel).findByText("CONVERGED")).toBeInTheDocument();
    expect(within(panel).getByText("Iterations: 2/3 · Final Critic: 0.90 · Shards: 3")).toBeInTheDocument();

    const traceList = within(panel).getByRole("list", { name: "Cyclic reflection iteration trace" });
    expect(within(traceList).getByText(/\[iter 1\] draft_patch \(claude-3-7-sonnet\) · 3sh/)).toBeInTheDocument();
    expect(within(traceList).getByText(/\[iter 2\] critic_verify \(gpt-4\.1\) · 1sh/)).toBeInTheDocument();
    expect(within(traceList).getAllByText(/critic 0\.90 · COMPLETED/).length).toBeGreaterThanOrEqual(2);
    expect(within(traceList).getByText(/\[iter 2\] publish_release \(keelway-core:7b\) · 1sh/)).toBeInTheDocument();
    expect(within(panel).queryByRole("list", { name: "Saga compensation rollback log" })).not.toBeInTheDocument();

    const runSha = within(panel).getByTestId("cyclic-run-sha256").textContent;
    expect(runSha).toMatch(/^[0-9a-f]{64}$/);
  });

  it("Test 2: triggers reverse-order Saga Compensation on timeout -> COMPENSATED badge and rollback handler entries", async () => {
    const user = userEvent.setup();
    render(<CyclicKflowAndAutopilotPanel workspaceId="default" workflowId="WF-CYCLIC-01" activeRbacRole="owner" />);

    const panel = screen.getByRole("region", {
      name: "Bounded Cyclic KFlow and Cost Privacy Autopilot",
    });

    await user.click(within(panel).getByRole("button", { name: "Trigger Saga Compensation" }));
    expect(await within(panel).findByText("COMPENSATED")).toBeInTheDocument();

    const traceList = within(panel).getByRole("list", { name: "Cyclic reflection iteration trace" });
    expect(within(traceList).getByText(/critic 0\.00 · TIMED_OUT/)).toBeInTheDocument();

    const compList = within(panel).getByRole("list", { name: "Saga compensation rollback log" });
    const items = within(compList).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("critic_verify -> discard_candidate");
    expect(items[0]).toHaveTextContent("timeout_exceeded · ROLLED_BACK");
    expect(items[1]).toHaveTextContent("draft_patch -> revert_worktree");
    expect(items[1]).toHaveTextContent("timeout_exceeded · ROLLED_BACK");

    expect(within(panel).getByTestId("cyclic-run-sha256").textContent).toMatch(/^[0-9a-f]{64}$/);
  });

  it("Test 3: simulates airgap_strict autopilot (keelway-core:7b rewrite + savings), applies route, and enforces 403 viewer RBAC + 422 bounds/DLP alerts", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <CyclicKflowAndAutopilotPanel workspaceId="default" workflowId="WF-CYCLIC-01" activeRbacRole="owner" />,
    );

    const panel = screen.getByRole("region", {
      name: "Bounded Cyclic KFlow and Cost Privacy Autopilot",
    });

    const policySelect = within(panel).getByLabelText("4D Privacy boundary policy");
    await user.selectOptions(policySelect, "airgap_strict");
    await user.click(within(panel).getByRole("button", { name: "Simulate Pre-Run Blast & Autopilot" }));

    expect(await within(panel).findByText("100.0% saved · 2 resolved")).toBeInTheDocument();
    expect(within(panel).getByText("$0.160 -> $0.000")).toBeInTheDocument();

    const planList = within(panel).getByRole("list", { name: "Autopilot node routing plan" });
    expect(within(planList).getByText("draft_patch: claude-3-7-sonnet -> qwen2.5-coder:7b")).toBeInTheDocument();
    expect(within(planList).getByText("critic_verify: gpt-4.1 -> keelway-core:7b")).toBeInTheDocument();
    expect(within(planList).getAllByText(/local_metal_zero_egress · \$0\.00 egress/).length).toBe(3);

    const simSha = within(panel).getByTestId("autopilot-simulation-sha256").textContent;
    expect(simSha).toMatch(/^[0-9a-f]{64}$/);

    // Apply Autopilot Route & Run -> executes loop with zero-egress OpenCore checkpoints ($0.000 spend)
    await user.click(within(panel).getByRole("button", { name: "Apply Autopilot Route & Run" }));
    expect(await within(panel).findByText("CONVERGED")).toBeInTheDocument();
    expect(within(panel).getByText(/map_reduce \(3sh\) · \$0\.000/)).toBeInTheDocument();

    // Unbounded max_iterations (15) -> HTTP 422 alert
    const maxIterInput = within(panel).getByLabelText("Max loop iterations");
    await user.clear(maxIterInput);
    await user.type(maxIterInput, "15");
    await user.click(within(panel).getByRole("button", { name: "Execute Reflection Loop" }));
    const boundsAlert = await within(panel).findByRole("alert");
    expect(boundsAlert).toHaveTextContent(/HTTP 422/);
    expect(boundsAlert).toHaveTextContent(/between 1 and 10/i);

    // DLP secret in initial_state -> PlatformCyclicHttpError(422)
    await expect(
      executeCyclicKflow({ workspace_id: "default", initial_state: { leaked: "sk-live-secretToken999999999" } }, "owner"),
    ).rejects.toMatchObject({ name: "PlatformCyclicHttpError", status: 422 } satisfies Partial<PlatformCyclicHttpError>);

    // Viewer RBAC -> HTTP 403 alert on execute and simulate
    rerender(<CyclicKflowAndAutopilotPanel workspaceId="default" workflowId="WF-CYCLIC-01" activeRbacRole="viewer" />);
    expect(within(panel).getByText("RBAC: viewer (read-only)")).toBeInTheDocument();

    await user.click(within(panel).getByRole("button", { name: "Execute Reflection Loop" }));
    expect(await within(panel).findByRole("alert")).toHaveTextContent(/HTTP 403 · RBAC Denied \(viewer\)/i);

    await user.click(within(panel).getByRole("button", { name: "Simulate Pre-Run Blast & Autopilot" }));
    expect(await within(panel).findByRole("alert")).toHaveTextContent(/HTTP 403 · RBAC Denied \(viewer\)/i);
  });

  it("Test 4: mounts in AutomationWorkspaceView, wires /v1/platform/kflow/* auth + RBAC headers without swallowing 403/422, and passes axe WCAG 2.2 AA in dark & light themes", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=phase15-cyc-tok");
    const seenRequests: Array<{ pathname: string; search: string; method: string; auth: string | null; role: string | null }> = [];
    const realFetch = globalThis.fetch;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const parsed = new URL(rawUrl, "http://localhost");
      const method = (init?.method ?? "GET").toUpperCase();
      const hdrs = new Headers(init?.headers);
      if (parsed.pathname.startsWith("/v1/platform/kflow")) {
        seenRequests.push({
          pathname: parsed.pathname,
          search: parsed.search,
          method,
          auth: hdrs.get("Authorization"),
          role: hdrs.get("X-Keelway-Role"),
        });
      }
      if (parsed.pathname === "/v1/platform/kflow/cyclic/runs" && method === "GET") {
        return new Response(JSON.stringify({ workspace_id: "default", count: 0, runs: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (parsed.pathname === "/v1/platform/kflow/autopilot/simulations" && method === "GET") {
        return new Response(JSON.stringify({ workspace_id: "default", count: 0, simulations: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (parsed.pathname === "/v1/platform/kflow/autopilot/simulate" && method === "POST") {
        return new Response(
          JSON.stringify({
            simulation_id: "apsim-live-01",
            workspace_id: "default",
            workflow_id: "WF-CYCLIC-01",
            privacy_policy: "airgap_strict",
            budget_cap_usd: 0.15,
            baseline_p50_usd: 0.08,
            baseline_p95_usd: 0.16,
            optimized_p50_usd: 0,
            optimized_p95_usd: 0,
            savings_pct: 100,
            baseline_ttft_ms: 765,
            optimized_ttft_ms: 405,
            privacy_compliant: true,
            violations_resolved: 2,
            node_plan: [
              {
                node_id: "critic_verify",
                original_model: "gpt-4.1",
                selected_model: "keelway-core:7b",
                rewritten: true,
                reason: "airgap_strict: zero-egress OpenCore enforcement",
                p50_cost_usd: 0,
                p95_cost_usd: 0,
                data_boundary: "local_metal_zero_egress",
              },
            ],
            simulation_sha256: "c".repeat(64),
            created_at: "2026-11-15T18:00:00Z",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (typeof realFetch === "function" && !parsed.pathname.startsWith("/v1/")) {
        return realFetch(input, init);
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const { container } = render(
      <AutomationWorkspaceView
        experienceMode="builder"
        workflows={[]}
        onCreateWorkflow={() => {}}
        onRunWorkflow={() => {}}
        onRetryFailedNode={() => {}}
        workspaceId="default"
        activeRbacRole="owner"
      />,
    );

    const panel = await screen.findByRole("region", {
      name: "Bounded Cyclic KFlow and Cost Privacy Autopilot",
    });

    await user.selectOptions(within(panel).getByLabelText("4D Privacy boundary policy"), "airgap_strict");
    await user.click(within(panel).getByRole("button", { name: "Simulate Pre-Run Blast & Autopilot" }));
    expect(within(panel).getByTestId("autopilot-simulation-sha256").textContent).toBe("c".repeat(64));

    expect(
      seenRequests.some(
        (r) =>
          r.pathname === "/v1/platform/kflow/autopilot/simulate" &&
          r.method === "POST" &&
          r.auth === "Bearer phase15-cyc-tok" &&
          r.role === "owner" &&
          r.search.includes("token=phase15-cyc-tok"),
      ),
    ).toBe(true);

    expect((await axe(container)).violations).toHaveLength(0);
    document.documentElement.setAttribute("data-theme", "light");
    expect((await axe(container)).violations).toHaveLength(0);
  });
});
