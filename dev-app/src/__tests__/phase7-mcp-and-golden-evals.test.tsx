import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/App";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 7D — Live MCP Inspector & 16-Probe Golden Eval Scorecard", () => {
  it("registers loopback SSE MCP server, blocks SSRF & unsafe stdio, invokes workspace.list_files with SHA-256 receipt, enforces RBAC, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Agents$/i }));

    const mcpSection = screen.getByRole("region", {
      name: /Model Context Protocol server and tool inspector/i,
    });
    expect(within(mcpSection).getByText("keelway-core-mcp")).toBeInTheDocument();
    expect(within(mcpSection).getAllByText(/protocol: 2025-06-18/i).length).toBeGreaterThan(0);

    // 1. Block cloud metadata SSRF http://169.254.169.254/sse
    const nameInput = within(mcpSection).getByLabelText("MCP server name");
    const transportSelect = within(mcpSection).getByLabelText("MCP transport");
    const endpointInput = within(mcpSection).getByLabelText("MCP endpoint or command");
    const registerBtn = within(mcpSection).getByRole("button", { name: /Register MCP Server/i });

    await user.type(nameInput, "rogue-metadata-mcp");
    await user.type(endpointInput, "http://169.254.169.254/sse");
    await user.click(registerBtn);
    expect(within(mcpSection).getByRole("alert")).toHaveTextContent(/SSRF|Blocked|169\.254\.169\.254/i);
    expect(within(mcpSection).queryByText("rogue-metadata-mcp")).toBeNull();

    // 2. Block unsafe stdio shell metacharacters
    await user.selectOptions(transportSelect, "stdio");
    await user.clear(endpointInput);
    await user.type(endpointInput, "npx mcp-server; rm -rf /");
    await user.click(registerBtn);
    expect(within(mcpSection).getByRole("alert")).toHaveTextContent(/Blocked|Shell metacharacters/i);

    // 3. Register valid loopback SSE MCP server
    await user.selectOptions(transportSelect, "sse");
    await user.clear(nameInput);
    await user.type(nameInput, "loopback-ast-mcp");
    await user.clear(endpointInput);
    await user.type(endpointInput, "http://127.0.0.1:8788/sse");
    await user.click(registerBtn);
    expect(within(mcpSection).queryByRole("alert")).toBeNull();
    expect(within(mcpSection).getByText("loopback-ast-mcp")).toBeInTheDocument();
    expect(within(mcpSection).getByText(/http:\/\/127\.0\.0\.1:8788\/sse/i)).toBeInTheDocument();

    // 4. Invoke workspace.list_files & verify execution result region + SHA-256 receipt
    const toolSelect = within(mcpSection).getByLabelText("MCP tool selector") as HTMLSelectElement;
    expect(toolSelect.value).toBe("workspace.list_files");
    const argsInput = within(mcpSection).getByLabelText("MCP tool JSON arguments") as HTMLInputElement;
    expect(argsInput.value).toBe('{"subpath": "core", "limit": 5}');

    const invokeBtn = within(mcpSection).getByRole("button", { name: /Invoke MCP Tool/i });
    await user.click(invokeBtn);

    const execResult = await within(mcpSection).findByRole("region", { name: /MCP tool execution result/i });
    expect(within(execResult).getByText(/workspace\.list_files/i)).toBeInTheDocument();
    expect(within(execResult).getByText(/sha256:/i)).toBeInTheDocument();
    expect(within(execResult).getByText(/core\/main\.py/i)).toBeInTheDocument();

    // 5. Verify RBAC lock: builder lacks webhooks:manage (Register disabled), viewer locks both Register & Invoke
    const rbacSelect = screen.getByLabelText(/Active RBAC role/i);
    await user.selectOptions(rbacSelect, "builder");
    expect(within(mcpSection).getByRole("button", { name: /Register MCP Server/i })).toBeDisabled();
    expect(within(mcpSection).getByRole("button", { name: /Invoke MCP Tool/i })).toBeEnabled();

    await user.selectOptions(rbacSelect, "viewer");
    expect(within(mcpSection).getByRole("button", { name: /Register MCP Server/i })).toBeDisabled();
    expect(within(mcpSection).getByRole("button", { name: /Invoke MCP Tool/i })).toBeDisabled();

    const axeResults = await axe(container);
    expect(axeResults.violations).toHaveLength(0);
  });

  it("runs 16-Probe Golden Suite in SecurityWorkspaceView, filters categories, renders 4 category scores + evidence, enforces viewer RBAC, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Security$/i }));

    const evalSection = screen.getByRole("region", {
      name: /Golden benchmark and adversarial red-team suite/i,
    });
    const runBtn = within(evalSection).getByRole("button", { name: /Run 16-Probe Golden Suite/i });
    const categorySelect = within(evalSection).getByLabelText("Golden eval category") as HTMLSelectElement;
    expect(categorySelect.value).toBe("all");

    await user.click(runBtn);

    // KPI strip: Pass Rate 100% (16/16), Duration, SHA-256 Receipt
    expect(await within(evalSection).findByText(/100% \(16\/16\)/i)).toBeInTheDocument();
    expect(within(evalSection).getByText(/ms$/i)).toBeInTheDocument();
    expect(within(evalSection).getByText(/^sha256:/i)).toBeInTheDocument();

    // All 4 category scores present
    for (const catId of ["workspace_ast", "governance_p10", "security_redteam", "routing_pricing"]) {
      expect(within(evalSection).getAllByText(catId).length).toBeGreaterThan(0);
    }
    expect(within(evalSection).getAllByText("4/4 (100%)")).toHaveLength(4);

    // 16 probe items with PASSED badges & concrete verification evidence
    const probeList = within(evalSection).getByRole("list", { name: /Golden evaluation probe results/i });
    expect(within(probeList).getAllByRole("listitem")).toHaveLength(16);
    expect(within(probeList).getAllByText("PASSED")).toHaveLength(16);
    expect(within(probeList).getByText(/169\.254\.169\.254/i)).toBeInTheDocument();

    // Filter category -> security_redteam shows 4 probes; governance_p10 shows 4 probes
    await user.selectOptions(categorySelect, "security_redteam");
    expect(within(probeList).getAllByRole("listitem")).toHaveLength(4);
    expect(within(probeList).getByText("RED-01")).toBeInTheDocument();
    expect(within(probeList).queryByText("AST-01")).toBeNull();

    await user.selectOptions(categorySelect, "governance_p10");
    expect(within(probeList).getAllByRole("listitem")).toHaveLength(4);
    expect(within(probeList).getByText("P10-01")).toBeInTheDocument();

    // Viewer RBAC locks Run 16-Probe Golden Suite
    await user.selectOptions(screen.getByLabelText(/Active RBAC role/i), "viewer");
    expect(within(evalSection).getByRole("button", { name: /Run 16-Probe Golden Suite/i })).toBeDisabled();

    const axeResults = await axe(container);
    expect(axeResults.violations).toHaveLength(0);
  });

  it("wires live /v1/platform/mcp/* and /v1/platform/evals/* endpoints with studio token & DLP redaction badge when runtime is connected", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=mcp-eval-tok-7d");
    const calls: Array<{ pathname: string; method: string; url: string }> = [];

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const pathname = new URL(url, "http://localhost").pathname;
      const method = (init?.method ?? "GET").toUpperCase();
      calls.push({ pathname, method, url });

      if (pathname === "/v1/platform/mcp/call" && method === "POST") {
        return new Response(
          JSON.stringify({
            ok: true,
            tool_name: "vault.list_metadata",
            protocol_version: "2025-06-18",
            redacted: true,
            duration_ms: 6,
            result: { secrets: [{ name: "BYOM_API_KEY", masked: "sk-p****1122" }] },
            receipt_sha256: "sha256:abcdef0123456789",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/evals/golden" && method === "POST") {
        return new Response(
          JSON.stringify({
            eval_run_id: "eval_live_01",
            workspace_id: "default",
            category: "all",
            total_cases: 16,
            passed_cases: 16,
            failed_cases: 0,
            pass_rate: 1.0,
            duration_ms: 19,
            categories: {
              workspace_ast: { total: 4, passed: 4, pass_rate: 1.0 },
              governance_p10: { total: 4, passed: 4, pass_rate: 1.0 },
              security_redteam: { total: 4, passed: 4, pass_rate: 1.0 },
              routing_pricing: { total: 4, passed: 4, pass_rate: 1.0 },
            },
            cases: Array.from({ length: 16 }, (_, i) => ({
              id: `LIVE-${String(i + 1).padStart(2, "0")}`,
              category: (["workspace_ast", "governance_p10", "security_redteam", "routing_pricing"] as const)[Math.floor(i / 4)],
              title: `Live probe #${i + 1}`,
              passed: true,
              duration_ms: 1,
              evidence: "Verified against live FastAPI runtime.",
            })),
            receipt_sha256: "fedcba9876543210",
            created_at: "2026-11-14T23:59:00Z",
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
    const mcpSection = screen.getByRole("region", { name: /Model Context Protocol server and tool inspector/i });
    await user.selectOptions(within(mcpSection).getByLabelText("MCP tool selector"), "vault.list_metadata");
    await user.click(within(mcpSection).getByRole("button", { name: /Invoke MCP Tool/i }));

    const execResult = await within(mcpSection).findByRole("region", { name: /MCP tool execution result/i });
    expect(within(execResult).getByText("DLP Redacted")).toBeInTheDocument();
    expect(within(execResult).getByText("sha256:abcdef0123456789")).toBeInTheDocument();

    await user.click(within(platformNav).getByRole("button", { name: /^Security$/i }));
    const evalSection = screen.getByRole("region", { name: /Golden benchmark and adversarial red-team suite/i });
    await user.click(within(evalSection).getByRole("button", { name: /Run 16-Probe Golden Suite/i }));
    expect(await within(evalSection).findByText("100% (16/16)")).toBeInTheDocument();
    expect(within(evalSection).getByText("sha256:fedcba9876543210")).toBeInTheDocument();

    expect(calls.some((c) => c.pathname === "/v1/platform/mcp/call" && c.url.includes("token=mcp-eval-tok-7d"))).toBe(true);
    expect(calls.some((c) => c.pathname === "/v1/platform/evals/golden" && c.url.includes("token=mcp-eval-tok-7d"))).toBe(true);
  });
});
