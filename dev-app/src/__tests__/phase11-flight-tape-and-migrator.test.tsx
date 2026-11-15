import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/App";
import { resetLocalDevxState } from "@/lib/platformDevxApi";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  resetLocalDevxState();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 11C — Flight-Tape Time-Travel Debugger, OTel GenAI Wedge & LangGraph AST Migrator UI", () => {
  it("ingests 3-step OTel GenAI traces with DLP scrubbing, forks counterfactual steps reusing cached upstream work at $0, promotes traces to Golden Evals, enforces viewer RBAC, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Agents$/i }));

    const debuggerSec = screen.getByRole("region", {
      name: /Flight-tape time-travel debugger and OTel trace evaluator/i,
    });
    expect(within(debuggerSec).getByText("$0 Local SQLite WAL Traces")).toBeInTheDocument();

    const stepSelect = within(debuggerSec).getByLabelText("Counterfactual fork step index") as HTMLSelectElement;
    const modelInput = within(debuggerSec).getByLabelText("Counterfactual override model") as HTMLInputElement;
    const promptInput = within(debuggerSec).getByLabelText("Counterfactual prompt override") as HTMLInputElement;

    expect(stepSelect.value).toBe("1");
    expect(modelInput.value).toBe("keelway-core:7b");
    expect(promptInput.value).toBe("Synthesize concise root-cause resolution strictly from cached tool evidence.");

    await user.click(within(debuggerSec).getByRole("button", { name: /^Ingest OTel GenAI Trace$/i }));

    const stepList = within(debuggerSec).getByRole("list", { name: /Flight-tape execution steps/i });
    expect(within(stepList).getByText("triage_router")).toBeInTheDocument();
    expect(within(stepList).getByText("mcp_billing_lookup")).toBeInTheDocument();
    expect(within(stepList).getByText("synthesis_critic")).toBeInTheDocument();
    expect(within(stepList).getByText(/\[REDACTED_SECRET\]/i)).toBeInTheDocument();

    const shaDigests = within(debuggerSec).getAllByText(/^sha256:[0-9a-f]+/i);
    expect(shaDigests[0]).toHaveClass("max-w-[240px]", "truncate");

    await user.click(within(debuggerSec).getByRole("button", { name: /^Replay Counterfactual Fork$/i }));

    const statusBanner = await within(debuggerSec).findByRole("status");
    expect(statusBanner).toHaveTextContent(/fork-/i);
    expect(statusBanner).toHaveTextContent(/cached_steps_reused:\s*1/i);
    expect(statusBanner).toHaveTextContent(/cost_delta_usd:\s*-0\.0179/i);
    expect(within(stepList).getByText("Cached Upstream · $0")).toBeInTheDocument();

    await user.click(within(debuggerSec).getByRole("button", { name: /^Promote Trace to Golden Eval$/i }));
    expect(await within(debuggerSec).findByRole("status")).toHaveTextContent(/evalcase-/i);

    const evalList = within(debuggerSec).getByRole("list", { name: /Promoted golden eval dataset cases/i });
    expect(within(evalList).getByText(/evalcase-/i)).toBeInTheDocument();

    const rbacSelect = screen.getByLabelText(/Active RBAC role/i);
    await user.selectOptions(rbacSelect, "viewer");
    expect(within(debuggerSec).getByRole("button", { name: /^Ingest OTel GenAI Trace$/i })).toBeDisabled();
    expect(within(debuggerSec).getByRole("button", { name: /^Replay Counterfactual Fork$/i })).toBeDisabled();
    expect(within(debuggerSec).getByRole("button", { name: /^Promote Trace to Golden Eval$/i })).toBeDisabled();

    expect((await axe(container)).violations).toHaveLength(0);
    document.documentElement.setAttribute("data-theme", "light");
    expect((await axe(container)).violations).toHaveLength(0);
  });

  it("converts cyclic Python StateGraph with interrupt() + LLMChain into bounded KFlow + p10_human_gate blueprint, enforces viewer RBAC, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Automation$/i }));

    const migratorSec = screen.getByRole("region", {
      name: /LangGraph to KFlow static AST migrator/i,
    });
    const codeArea = within(migratorSec).getByLabelText("LangGraph source code") as HTMLTextAreaElement;
    expect(codeArea.value).toContain('.add_node("draft", draft_fn)');
    expect(codeArea.value).toContain('.add_node("human_review", review_fn)');
    expect(codeArea.value).toContain('interrupt({"reason": "deploy"})');
    expect(codeArea.value).toContain("from langchain.chains import LLMChain");

    await user.click(within(migratorSec).getByRole("button", { name: /^Convert LangGraph to KFlow$/i }));

    const diagStatus = await within(migratorSec).findByRole("status");
    expect(within(diagStatus).getByText(/p10_human_gate · human_review/i)).toBeInTheDocument();
    expect(within(diagStatus).getByText(/Bounded Cycle · max_iterations:\s*5/i)).toBeInTheDocument();

    const warningsList = within(migratorSec).getByRole("list", { name: /Legacy LangChain deprecation advisories/i });
    expect(within(warningsList).getByText(/LLMChain/i)).toBeInTheDocument();

    expect(within(migratorSec).getByText(/KFlowBlueprint/i)).toBeInTheDocument();
    const shaEl = within(migratorSec).getByText(/^sha256:[0-9a-f]+/i);
    expect(shaEl).toHaveClass("max-w-[240px]", "truncate");

    await user.selectOptions(screen.getByLabelText(/Active RBAC role/i), "viewer");
    expect(within(migratorSec).getByRole("button", { name: /^Convert LangGraph to KFlow$/i })).toBeDisabled();
    expect(codeArea).toBeDisabled();

    expect((await axe(container)).violations).toHaveLength(0);
  });

  it("wires all 6 /v1/platform/* DevX routes with ?token=, Bearer auth & X-Keelway-Role, supports live empty-tape sample ingest, and surfaces HTTP 400 errors via alert", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=phase11-devx-tok");
    const calls: Array<{ pathname: string; method: string; url: string; auth: string | null; role: string | null }> = [];
    let rejectMigrate = true;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const pathname = new URL(url, "http://localhost").pathname;
      const method = (init?.method ?? "GET").toUpperCase();
      const hdrs = new Headers(init?.headers);
      calls.push({ pathname, method, url, auth: hdrs.get("Authorization"), role: hdrs.get("X-Keelway-Role") });

      if (pathname === "/v1/platform/traces" && method === "GET") {
        return new Response(JSON.stringify({ workspace_id: "default", total_tapes: 0, tapes: [] }), {
          status: 200, headers: { "Content-Type": "application/json" },
        });
      }
      if (pathname === "/v1/platform/eval/dataset" && method === "GET") {
        return new Response(JSON.stringify({ workspace_id: "default", total_cases: 0, cases: [] }), {
          status: 200, headers: { "Content-Type": "application/json" },
        });
      }
      if (pathname === "/v1/platform/traces/ingest" && method === "POST") {
        return new Response(
          JSON.stringify({
            tape: {
              trace_id: "trace-live-77",
              workspace_id: "default",
              title: "Live SQLite WAL Trace",
              total_cost_usd: 0.018,
              dlp_redactions: 1,
              tape_sha256: "sha256:1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/traces/trace-live-77/replay" && method === "POST") {
        return new Response(
          JSON.stringify({
            fork_trace_id: "fork-live-88",
            parent_trace_id: "trace-live-77",
            cached_steps_reused: 1,
            cost_delta_usd: -0.018,
            total_cost_usd: 0,
            tape_sha256: "sha256:aaaabbbbccccddddeeeeffff0000111122223333444455556666777788889999",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/eval/dataset/promote" && method === "POST") {
        return new Response(
          JSON.stringify({
            eval_case: {
              case_id: "evalcase-live-99",
              trace_id: "fork-live-88",
              title: "Golden Eval · Live Fork",
              step_count: 3,
              case_sha256: "sha256:9999888877776666555544443333222211110000ffffeeeeddddccccbbbbaaaa",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/migrate/langgraph" && method === "POST") {
        if (rejectMigrate) {
          return new Response(JSON.stringify({ detail: "AST SyntaxError: unexpected indent on line 4." }), {
            status: 400, headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({
            workspace_id: "default",
            workflow_name: "migrated-release-review-kflow",
            nodes: [
              { id: "draft", handler: "draft_fn", kind: "agent_task", requires_p10: false },
              { id: "human_review", handler: "review_fn", kind: "p10_human_gate", requires_p10: true },
            ],
            edges: [{ source: "human_review", target: "draft", condition: "revise", is_back_edge: true }],
            p10_gates_injected: ["human_review"],
            cycles_detected: 1,
            bounded_loop_policies: [{ from_node: "human_review", to_node: "draft", max_iterations: 4 }],
            legacy_warnings: ["LLMChain is deprecated; migrate to typed KFlowNode."],
            kflow_sdk_code: 'workflow = KFlowBlueprint(name="migrated-release-review-kflow")',
            migration_sha256: "sha256:4444555566667777888899990000111122223333aaaabbbbccccddddeeeeffff",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });
    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });

    await user.click(within(platformNav).getByRole("button", { name: /^Agents$/i }));
    const debuggerSec = screen.getByRole("region", {
      name: /Flight-tape time-travel debugger and OTel trace evaluator/i,
    });

    const sampleBtn = await within(debuggerSec).findByRole("button", { name: /^Ingest Sample OTel Trace$/i });
    await user.click(sampleBtn);
    await user.click(within(debuggerSec).getByRole("button", { name: /^Replay Counterfactual Fork$/i }));
    expect(await within(debuggerSec).findByRole("status")).toHaveTextContent(/fork-live-88/i);

    await user.click(within(debuggerSec).getByRole("button", { name: /^Promote Trace to Golden Eval$/i }));
    expect(await within(debuggerSec).findByRole("status")).toHaveTextContent(/evalcase-live-99/i);

    await user.click(within(platformNav).getByRole("button", { name: /^Automation$/i }));
    const migratorSec = screen.getByRole("region", { name: /LangGraph to KFlow static AST migrator/i });
    await user.click(within(migratorSec).getByRole("button", { name: /^Convert LangGraph to KFlow$/i }));
    expect(await within(migratorSec).findByRole("alert")).toHaveTextContent(/AST SyntaxError/i);

    rejectMigrate = false;
    await user.click(within(migratorSec).getByRole("button", { name: /^Convert LangGraph to KFlow$/i }));
    expect(await within(migratorSec).findByRole("status")).toHaveTextContent(/max_iterations:\s*4/i);

    for (const ep of [
      "/v1/platform/traces",
      "/v1/platform/eval/dataset",
      "/v1/platform/traces/ingest",
      "/v1/platform/traces/trace-live-77/replay",
      "/v1/platform/eval/dataset/promote",
      "/v1/platform/migrate/langgraph",
    ]) {
      expect(
        calls.some(
          (c) => c.pathname === ep && c.url.includes("token=phase11-devx-tok") && c.auth === "Bearer phase11-devx-tok" && c.role === "owner",
        ),
      ).toBe(true);
    }
  });
});
