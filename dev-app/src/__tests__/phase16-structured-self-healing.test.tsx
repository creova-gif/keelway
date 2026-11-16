import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentsWorkspaceView } from "@/components/platform/AgentsWorkspaceView";
import { StructuredOutputAndSelfHealingPanel } from "@/components/platform/StructuredOutputAndSelfHealingPanel";
import {
  AGENT_DECISION_JSON_SCHEMA,
  canRbacMutateHealing,
  enforceStructuredOutput,
  PlatformHealingHttpError,
  PROVIDER_WIRE_FIXTURES,
  resetHealingFallbackStore,
} from "@/lib/platformHealingApi";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  resetHealingFallbackStore();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 16C — Structured-Output Normalizer & Autonomous Self-Healing Root-Causer", () => {
  it("Test 1: normalizes content blocks across provider wire formats with DLP scrubbing and enforces JSON Schema (REPAIRED_VALID + SCHEMA_REJECTED + run_sha256)", async () => {
    const user = userEvent.setup();
    render(<StructuredOutputAndSelfHealingPanel workspaceId="default" activeRbacRole="owner" />);

    const panel = screen.getByRole("region", {
      name: "Structured-output normalizer and self-healing root-causer",
    });
    expect(within(panel).getByRole("heading", { name: "Structured-Output Normalizer & Self-Healing Root-Causer" })).toBeInTheDocument();

    const providerSelect = within(panel).getByLabelText("Provider Wire Format");
    await user.click(within(panel).getByRole("button", { name: "Normalize Content Blocks" }));

    expect(await within(panel).findByText("deepseek_opencore · 5 blocks")).toBeInTheDocument();
    expect(within(panel).getByText("dlp_redactions: 1")).toBeInTheDocument();
    const blockList = within(panel).getByRole("list", { name: "Normalized content blocks" });
    expect(within(blockList).getByText("reasoning")).toBeInTheDocument();
    expect(within(blockList).getByText("tool_call")).toBeInTheDocument();
    expect(within(blockList).getByText("citation")).toBeInTheDocument();
    expect(within(blockList).getByText("structured_json")).toBeInTheDocument();
    expect(within(blockList).getByText("text")).toBeInTheDocument();
    expect(within(blockList).getByText(/\[REDACTED_SECRET\]/)).toBeInTheDocument();
    expect(within(blockList).queryByText(/sk-live-/)).not.toBeInTheDocument();
    expect(within(panel).getByTestId("healing-envelope-sha256").textContent).toMatch(/^[0-9a-f]{64}$/);

    // Verify anthropic, openai, and gemini wire formats normalize cleanly
    for (const fmt of ["anthropic", "openai", "gemini"] as const) {
      await user.selectOptions(providerSelect, fmt);
      await user.click(within(panel).getByRole("button", { name: "Normalize Content Blocks" }));
      expect(await within(panel).findByText(new RegExp(`^${fmt} · \\d+ blocks$`))).toBeInTheDocument();
    }

    // Switch back to deepseek_opencore and enforce JSON Schema Contract (strict_mode=false -> REPAIRED_VALID)
    await user.selectOptions(providerSelect, "deepseek_opencore");
    await user.click(within(panel).getByRole("button", { name: "Enforce JSON Schema Contract" }));

    expect((await within(panel).findAllByText("REPAIRED_VALID")).length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText(/repair_actions:.*strip_think_prefix.*strip_markdown_fence.*remove_trailing_commas/)).toBeInTheDocument();
    const preview = within(panel).getByLabelText("Validated JSON contract preview");
    expect(preview).toHaveTextContent('"confidence": 0.94');
    expect(preview).toHaveTextContent('"retry_budget": 2');
    expect(within(panel).getByTestId("structured-run-sha256").textContent).toMatch(/^[0-9a-f]{64}$/);

    // Toggle Strict Schema Mode (No Repair) -> SCHEMA_REJECTED
    await user.click(within(panel).getByLabelText("Strict Schema Mode (No Repair)"));
    await user.click(within(panel).getByRole("button", { name: "Enforce JSON Schema Contract" }));
    expect((await within(panel).findAllByText("SCHEMA_REJECTED")).length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText(/validation_errors:/)).toBeInTheDocument();
  });

  it("Test 2: diagnoses schema_mismatch root cause (unified diff + diagnosis_sha256) and applies patch to promote Golden Eval (VERIFIED_HEALED + case_id)", async () => {
    const user = userEvent.setup();
    render(<StructuredOutputAndSelfHealingPanel workspaceId="default" activeRbacRole="owner" />);

    const panel = screen.getByRole("region", {
      name: "Structured-output normalizer and self-healing root-causer",
    });

    const scenarioSelect = within(panel).getByLabelText("Failure Trace Scenario");
    expect(scenarioSelect).toHaveValue("schema_mismatch");

    await user.click(within(panel).getByRole("button", { name: "Diagnose Root Cause" }));
    expect((await within(panel).findAllByText("DIAGNOSED")).length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText("schema_mismatch")).toBeInTheDocument();
    expect(within(panel).getByText("94% confidence")).toBeInTheDocument();

    const diffPre = within(panel).getByLabelText("Proposed self-healing unified diff");
    expect(diffPre).toHaveTextContent("+Enforce JSON Schema AgentDecisionContract");
    const firstDiagSha = within(panel).getByTestId("healing-diagnosis-sha256").textContent;
    expect(firstDiagSha).toMatch(/^[0-9a-f]{64}$/);

    await user.click(within(panel).getByRole("button", { name: "Apply Patch & Promote Golden Eval" }));
    expect((await within(panel).findAllByText("VERIFIED_HEALED")).length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText(/\$0\.00 cached replay/)).toBeInTheDocument();
    const caseIdEl = within(panel).getByTestId("promoted-healing-eval-case-id");
    expect(caseIdEl.textContent).toMatch(/^evalcase-heal-[0-9a-f]+$/);
  });

  it("Test 3: enforces auditor read-only RBAC disabling mutation buttons while keeping Normalize Content Blocks enabled, plus API 403/422 guards", async () => {
    const user = userEvent.setup();
    expect(canRbacMutateHealing("auditor")).toBe(false);
    expect(canRbacMutateHealing("owner")).toBe(true);
    expect(canRbacMutateHealing("admin")).toBe(true);
    expect(canRbacMutateHealing("developer")).toBe(true);
    expect(canRbacMutateHealing("operator")).toBe(true);

    render(<StructuredOutputAndSelfHealingPanel workspaceId="default" activeRbacRole="auditor" />);

    const panel = screen.getByRole("region", {
      name: "Structured-output normalizer and self-healing root-causer",
    });
    expect(within(panel).getByText("RBAC: auditor (read-only)")).toBeInTheDocument();

    const normalizeBtn = within(panel).getByRole("button", { name: "Normalize Content Blocks" });
    const enforceBtn = within(panel).getByRole("button", { name: "Enforce JSON Schema Contract" });
    const diagnoseBtn = within(panel).getByRole("button", { name: "Diagnose Root Cause" });
    const applyBtn = within(panel).getByRole("button", { name: "Apply Patch & Promote Golden Eval" });

    expect(normalizeBtn).not.toBeDisabled();
    expect(enforceBtn).toBeDisabled();
    expect(diagnoseBtn).toBeDisabled();
    expect(applyBtn).toBeDisabled();

    // Auditor can still execute read:all normalization
    await user.click(normalizeBtn);
    expect(await within(panel).findByText("deepseek_opencore · 5 blocks")).toBeInTheDocument();

    // Direct API calls enforce 403 for auditor and 422 when fail_closed=true in strict mode
    await expect(
      enforceStructuredOutput(
        { json_schema: AGENT_DECISION_JSON_SCHEMA, raw_output: PROVIDER_WIRE_FIXTURES.deepseek_opencore.sample_raw_output },
        "auditor",
      ),
    ).rejects.toMatchObject({ name: "PlatformHealingHttpError", status: 403 } satisfies Partial<PlatformHealingHttpError>);

    await expect(
      enforceStructuredOutput(
        { json_schema: AGENT_DECISION_JSON_SCHEMA, raw_output: PROVIDER_WIRE_FIXTURES.deepseek_opencore.sample_raw_output, strict_mode: true, fail_closed: true },
        "owner",
      ),
    ).rejects.toMatchObject({ name: "PlatformHealingHttpError", status: 422 } satisfies Partial<PlatformHealingHttpError>);
  });

  it("Test 4: mounts in AgentsWorkspaceView below FlightTapeDebuggerPanel, propagates HTTP 403/422 from /v1/platform/healing/*, and passes axe WCAG 2.2 AA in dark & light themes", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=phase16-heal-tok");
    const seenHealingCalls: Array<{ pathname: string; method: string; auth: string | null; role: string | null }> = [];
    const realFetch = globalThis.fetch;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const parsed = new URL(rawUrl, "http://localhost");
      const method = (init?.method ?? "GET").toUpperCase();
      const hdrs = new Headers(init?.headers);
      if (parsed.pathname.startsWith("/v1/platform/healing")) {
        seenHealingCalls.push({
          pathname: parsed.pathname,
          method,
          auth: hdrs.get("Authorization"),
          role: hdrs.get("X-Keelway-Role"),
        });
      }
      if (parsed.pathname === "/v1/platform/healing/structured/runs") {
        return new Response(JSON.stringify({ workspace_id: "default", count: 0, runs: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (parsed.pathname === "/v1/platform/healing/root-cause/diagnoses") {
        return new Response(JSON.stringify({ workspace_id: "default", count: 0, diagnoses: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (parsed.pathname === "/v1/platform/healing/root-cause/diagnose" && method === "POST") {
        return new Response(JSON.stringify({ detail: "Simulated backend validation gate failure" }), { status: 422, headers: { "Content-Type": "application/json" } });
      }
      if (typeof realFetch === "function" && !parsed.pathname.startsWith("/v1/")) {
        return realFetch(input, init);
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
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

    const flightPanel = await screen.findByRole("region", { name: "Flight-tape time-travel debugger and OTel trace evaluator" });
    const healingPanel = await screen.findByRole("region", { name: "Structured-output normalizer and self-healing root-causer" });
    expect(flightPanel.compareDocumentPosition(healingPanel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    await user.click(within(healingPanel).getByRole("button", { name: "Diagnose Root Cause" }));
    const alert = await within(healingPanel).findByRole("alert");
    expect(alert).toHaveTextContent("HTTP 422 · Simulated backend validation gate failure");

    expect(
      seenHealingCalls.some(
        (c) =>
          c.pathname === "/v1/platform/healing/root-cause/diagnose" &&
          c.method === "POST" &&
          c.auth === "Bearer phase16-heal-tok" &&
          c.role === "owner",
      ),
    ).toBe(true);

    expect((await axe(container)).violations).toHaveLength(0);
    document.documentElement.setAttribute("data-theme", "light");
    expect((await axe(container)).violations).toHaveLength(0);
  });
});
