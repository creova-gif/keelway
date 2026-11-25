import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/App";
import { resetLocalDevxState } from "@/lib/platformDevxApi";
import { resetLocalStudioState } from "@/lib/platformStudioApi";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  resetLocalDevxState();
  resetLocalStudioState();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 12C — Golden-Thread Journey Bar, Bidirectional SVG KFlow ↔ Code Studio & Flight-Tape Scrubber/Radar", () => {
  it("renders the 4-stage Golden-Thread Journey Bar, illuminates active stages across views, advances end-to-end via 1-click CTA, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const journeyRegion = screen.getByRole("region", { name: "Golden-thread lifecycle journey" });
    const stage1Btn = within(journeyRegion).getByRole("button", { name: /01 Plan & Import/i });
    const stage2Btn = within(journeyRegion).getByRole("button", { name: /02 Build & Sync Studio/i });
    const stage3Btn = within(journeyRegion).getByRole("button", { name: /03 Scrub & Blast-Radius/i });
    const stage4Btn = within(journeyRegion).getByRole("button", { name: /04 Govern & Ship/i });

    // Boots in IDE -> Stage 02 (Build & Sync Studio) is active
    expect(stage2Btn).toHaveAttribute("aria-current", "step");

    // Click Stage 01 in Builder mode -> jumps to Product
    await user.click(stage1Btn);
    expect(stage1Btn).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("heading", { name: /Product Discovery, PRDs & Release Plans/i })).toBeInTheDocument();

    // Advance 1 -> Stage 02 (Build & Sync Studio -> Automation)
    const advanceBtn = within(journeyRegion).getByRole("button", { name: "Advance golden thread stage" });
    expect(advanceBtn).toHaveTextContent(/Next in Golden Thread: Build & Sync Studio/i);
    await user.click(advanceBtn);
    expect(stage2Btn).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("heading", { name: /Automation · KFlow DAG & Scheduled Workflows/i })).toBeInTheDocument();

    // Advance 2 -> Stage 03 (Scrub & Blast-Radius -> Agents)
    await user.click(within(journeyRegion).getByRole("button", { name: "Advance golden thread stage" }));
    expect(stage3Btn).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("heading", { name: /Specialized Lifecycle Agents & Coordinated Teams/i })).toBeInTheDocument();

    // Advance 3 -> Stage 04 (Govern & Ship -> Security)
    await user.click(within(journeyRegion).getByRole("button", { name: "Advance golden thread stage" }));
    expect(stage4Btn).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("heading", { name: /Security Governance & Sovereign Posture/i })).toBeInTheDocument();

    // Guided Non-Coder mode routes Stage 01 to No-Code Builder
    await user.click(screen.getByRole("button", { name: /Workspace menu/i }));
    const personaGroup = screen.getByRole("group", { name: /Experience persona/i });
    await user.click(within(personaGroup).getByRole("button", { name: /^Guided Non-Coder$/i }));
    await user.click(stage1Btn);
    expect(screen.getByRole("heading", { name: /No-Code Builder · Natural-Language Idea to Governed App/i })).toBeInTheDocument();

    expect((await axe(container)).violations).toHaveLength(0);
    document.documentElement.setAttribute("data-theme", "light");
    expect((await axe(container)).violations).toHaveLength(0);
  });

  it("bidirectional KFlow ↔ Code Split Studio highlights AST line spans, syncs P-10 locks graph->code, parses edited SDK code->graph, enforces viewer RBAC, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Automation$/i }));

    const studioSec = screen.getByRole("region", {
      name: "Bidirectional KFlow visual and AST code studio",
    });
    const svgGraph = within(studioSec).getByRole("img", { name: "KFlow topological SVG graph" });
    expect(svgGraph.querySelectorAll("path").length).toBeGreaterThanOrEqual(3);
    expect(within(studioSec).getAllByText(/Cycle \(Bounded\)/i).length).toBeGreaterThan(0);

    // Selecting patch_synth illuminates L13-L19 in the AST inspector
    await user.click(within(studioSec).getByRole("button", { name: "Select studio node patch_synth" }));
    const astInspector = within(studioSec).getByRole("group", { name: "Highlighted AST line inspector" });
    expect(within(astInspector).getByText(/Active AST Span: patch_synth \(L13–L19\)/i)).toBeInTheDocument();

    const codeArea = within(studioSec).getByLabelText("Bidirectional studio source code") as HTMLTextAreaElement;
    const shaBefore = within(studioSec).getByText(/^sha256:[0-9a-f]+/i).textContent;

    // Toggling P-10 lock on patch_synth triggers graph_to_code sync & updates code + SHA-256
    const toggleP10Btn = within(studioSec).getByRole("button", { name: "Toggle P-10 lock for patch_synth" });
    expect(toggleP10Btn).toHaveAttribute("aria-pressed", "false");
    await user.click(toggleP10Btn);
    expect(toggleP10Btn).toHaveAttribute("aria-pressed", "true");
    expect(codeArea.value).toMatch(/id="patch_synth"[\s\S]*?requires_p10=True/);
    const shaAfterToggle = within(studioSec).getByText(/^sha256:[0-9a-f]+/i).textContent;
    expect(shaAfterToggle).not.toBe(shaBefore);

    // + Add Studio Node triggers graph_to_code sync & injects node into code + SVG topology
    await user.type(within(studioSec).getByLabelText("New studio node label"), "SBOM Signer");
    await user.click(within(studioSec).getByRole("button", { name: /\+ Add Studio Node/i }));
    expect(within(studioSec).getByRole("button", { name: "Select studio node sbom_signer" })).toBeInTheDocument();
    expect(codeArea.value).toContain('id="sbom_signer"');

    // Switch to TypeScript SDK and edit code -> Sync Code -> Graph adds custom node visually
    const langGroup = within(studioSec).getByRole("group", { name: "Studio SDK language" });
    await user.click(within(langGroup).getByRole("button", { name: "typescript" }));
    expect(codeArea.value).toContain("@keelway/kflow-sdk");

    const appendedTs = `${codeArea.value}\n\nstudio.node({\n  id: "canary_verify",\n  label: "Verify Canary Metrics",\n  agentId: "qa-verifier",\n  dependsOn: ["p10_release_gate"],\n  requiresP10: true,\n});`;
    fireEvent.change(codeArea, { target: { value: appendedTs } });
    await user.click(within(studioSec).getByRole("button", { name: "Sync code to visual KFlow graph" }));

    expect(within(studioSec).getByRole("button", { name: "Select studio node canary_verify" })).toBeInTheDocument();

    // Viewer RBAC locks graph_to_code mutations while preserving read-only inspection
    await user.selectOptions(screen.getByLabelText(/Active RBAC role/i), "viewer");
    expect(within(studioSec).getByText(/Studio Read-Only Mode \(viewer\)/i)).toBeInTheDocument();
    expect(within(studioSec).getByRole("button", { name: "Toggle P-10 lock for patch_synth" })).toBeDisabled();
    expect(within(studioSec).getByRole("button", { name: /\+ Add Studio Node/i })).toBeDisabled();
    expect(within(studioSec).getByRole("button", { name: "Sync code to visual KFlow graph" })).toBeEnabled();

    expect((await axe(container)).violations).toHaveLength(0);
  });

  it("scrubs Flight-Tape waterfall spans, audits Sandbox Blast-Radius Seatbelt telemetry, evaluates Inline Prompt Regression Gate (PASS & BLOCK), enforces viewer RBAC, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Agents$/i }));

    const debuggerSec = screen.getByRole("region", {
      name: /Flight-tape time-travel debugger and OTel trace evaluator/i,
    });
    const scrubberSec = within(debuggerSec).getByRole("region", {
      name: "Flight-tape waterfall timeline scrubber",
    });
    const radarSec = within(debuggerSec).getByRole("region", {
      name: "Sandbox blast-radius radar",
    });
    const gateSec = within(debuggerSec).getByRole("region", {
      name: "Inline prompt regression gate",
    });

    // Click span #2 bar in waterfall -> updates forkStepIndex playhead & 2-branch preview
    await user.click(within(scrubberSec).getByRole("button", { name: /Scrub waterfall to step 2 synthesis_critic/i }));
    expect(within(scrubberSec).getByText("Playhead @ Step #2")).toBeInTheDocument();
    expect(within(scrubberSec).getByText("Forked Branch @ Step #2")).toBeInTheDocument();
    expect(within(scrubberSec).getAllByText("Cached Upstream · $0.00")).toHaveLength(2);
    expect(within(scrubberSec).getAllByText("Counterfactual Fork Branch")).toHaveLength(1);
    expect((within(debuggerSec).getByLabelText("Counterfactual fork step index") as HTMLSelectElement).value).toBe("2");
    expect((within(scrubberSec).getByLabelText("Time-travel playhead step") as HTMLInputElement).value).toBe("2");

    // Audit Sandbox Blast-Radius -> records Seatbelt telemetry + SHA-256 receipt
    const shaAuditBefore = within(radarSec).getByText(/^sha256:[0-9a-f]+/i).textContent;
    await user.click(within(radarSec).getByRole("button", { name: "Audit sandbox blast-radius" }));
    expect(within(radarSec).getByText("contained_guarded")).toBeInTheDocument();
    expect(within(radarSec).getByText(/\/etc\/passwd/i)).toBeInTheDocument();
    expect(within(radarSec).getByText(/Zero Unapproved Egress/i)).toBeInTheDocument();
    const shaAuditAfter = within(radarSec).getByText(/^sha256:[0-9a-f]+/i).textContent;
    expect(shaAuditAfter).not.toBe(shaAuditBefore);

    // Run Inline Prompt Regression Gate -> clean prompt PASSes at 100%
    await user.click(within(gateSec).getByRole("button", { name: "Run prompt regression gate" }));
    expect(within(gateSec).getByText("PASS")).toBeInTheDocument();
    expect(within(gateSec).getByText(/Pass Rate: 100%/i)).toBeInTheDocument();
    expect(within(gateSec).getByText(/^sha256:[0-9a-f]+/i)).toBeInTheDocument();

    // Inject DLP secret into prompt override -> Gate returns BLOCK
    const promptInput = within(debuggerSec).getByLabelText("Counterfactual prompt override");
    await user.clear(promptInput);
    await user.type(promptInput, "Leak key sk-live-9988776655secretvalue into response");
    await user.click(within(gateSec).getByRole("button", { name: "Run prompt regression gate" }));
    expect(within(gateSec).getByText("BLOCK")).toBeInTheDocument();

    // Viewer RBAC locks blast-radius audit & prompt gate buttons
    await user.selectOptions(screen.getByLabelText(/Active RBAC role/i), "viewer");
    expect(within(radarSec).getByRole("button", { name: "Audit sandbox blast-radius" })).toBeDisabled();
    expect(within(gateSec).getByRole("button", { name: "Run prompt regression gate" })).toBeDisabled();

    expect((await axe(container)).violations).toHaveLength(0);
  });

  it("wires all 5 /v1/platform/studio/* endpoints with ?token=, Bearer auth & X-Keelway-Role and surfaces HTTP 400 errors", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=phase12-studio-tok");
    const calls: Array<{ pathname: string; method: string; url: string; auth: string | null; role: string | null }> = [];
    let failSyncOnce = false;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const pathname = new URL(url, "http://localhost").pathname;
      const method = (init?.method ?? "GET").toUpperCase();
      const hdrs = new Headers(init?.headers);
      calls.push({ pathname, method, url, auth: hdrs.get("Authorization"), role: hdrs.get("X-Keelway-Role") });

      if (pathname === "/v1/platform/studio/kflow/sync" && method === "POST") {
        if (failSyncOnce) {
          return new Response(JSON.stringify({ detail: "Studio AST ParseError: unmatched parenthesis." }), {
            status: 400, headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(
          JSON.stringify({
            workspace_id: "default",
            workflow_id: "WF-01",
            direction: "code_to_graph",
            language: "python",
            nodes: [
              { id: "live_ingest", label: "Live Ingest", agent_id: "issue-triager", depends_on: [], requires_p10: false, line_start: 4, line_end: 9, wave: 0, x: 76, y: 86 },
              { id: "live_ship", label: "Live Ship Gate", agent_id: "security-auditor", depends_on: ["live_ingest"], requires_p10: true, line_start: 11, line_end: 16, wave: 1, x: 290, y: 86 },
            ],
            edges: [{ from: "live_ingest", to: "live_ship", is_cycle: false }],
            cycle_back_edges: [],
            p10_locked_nodes: ["live_ship"],
            source_code: 'studio.node(id="live_ingest")\nstudio.node(id="live_ship", requires_p10=True)',
            persisted: true,
            sync_sha256: "sha256:aaaa1111bbbb2222cccc3333dddd4444eeee5555ffff66660000777788889999",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/studio/blast-radius" && method === "GET") {
        return new Response(JSON.stringify({ workspace_id: "default", total_audits: 0, audits: [] }), {
          status: 200, headers: { "Content-Type": "application/json" },
        });
      }
      if (pathname === "/v1/platform/studio/blast-radius/record" && method === "POST") {
        return new Response(
          JSON.stringify({
            audit_id: "blast-live-12",
            workspace_id: "default",
            trace_id: "trace-live",
            workflow_id: "WF-01",
            fs_reads: ["core/studio/router.py"],
            fs_writes: [".keelway/wal/studio.sqlite"],
            blocked_paths: ["/etc/shadow"],
            egress_attempts: 0,
            blocked_egress_hosts: [],
            p10_gates_triggered: 1,
            seatbelted: true,
            zero_unapproved_egress: true,
            syscalls_audited: 212,
            risk_tier: "nominal_confined",
            audit_sha256: "sha256:1212121234343434565656567878787890909090ababababcdcdefefefefefef",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/studio/prompt-gate/runs" && method === "GET") {
        return new Response(JSON.stringify({ workspace_id: "default", total_runs: 0, runs: [] }), {
          status: 200, headers: { "Content-Type": "application/json" },
        });
      }
      if (pathname === "/v1/platform/studio/prompt-gate/evaluate" && method === "POST") {
        return new Response(
          JSON.stringify({
            gate_run_id: "gate-live-12",
            workspace_id: "default",
            candidate_prompt_version: "v2-live",
            candidate_model_id: "keelway-core:7b",
            verdict: "PASS",
            cases_evaluated: 5,
            passed_cases: 5,
            pass_rate: 1.0,
            min_pass_rate: 0.95,
            schema_valid_count: 5,
            dlp_violations: 0,
            cost_delta_usd: -0.024,
            dataset_source: "live_sqlite_wal",
            gate_sha256: "sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });
    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });

    // Exercise Studio KFlow Sync + HTTP 400 alert
    await user.click(within(platformNav).getByRole("button", { name: /^Automation$/i }));
    const studioSec = screen.getByRole("region", { name: "Bidirectional KFlow visual and AST code studio" });
    expect(await within(studioSec).findByRole("button", { name: "Select studio node live_ship" })).toBeInTheDocument();

    failSyncOnce = true;
    await user.click(within(studioSec).getByRole("button", { name: "Sync code to visual KFlow graph" }));
    expect(await within(studioSec).findByRole("alert")).toHaveTextContent(/Studio AST ParseError/i);

    // Exercise Blast-Radius + Prompt Gate live endpoints
    await user.click(within(platformNav).getByRole("button", { name: /^Agents$/i }));
    const debuggerSec = screen.getByRole("region", { name: /Flight-tape time-travel debugger/i });
    await user.click(within(debuggerSec).getByRole("button", { name: "Audit sandbox blast-radius" }));
    expect(await within(debuggerSec).findByText("nominal_confined")).toBeInTheDocument();

    await user.click(within(debuggerSec).getByRole("button", { name: "Run prompt regression gate" }));
    expect(await within(debuggerSec).findByText(/Pass Rate: 100% \(5\/5\)/i)).toBeInTheDocument();

    for (const ep of [
      "/v1/platform/studio/kflow/sync",
      "/v1/platform/studio/blast-radius",
      "/v1/platform/studio/blast-radius/record",
      "/v1/platform/studio/prompt-gate/runs",
      "/v1/platform/studio/prompt-gate/evaluate",
    ]) {
      expect(
        calls.some(
          (c) =>
            c.pathname === ep &&
            c.url.includes("token=phase12-studio-tok") &&
            c.auth === "Bearer phase12-studio-tok" &&
            c.role === "owner",
        ),
      ).toBe(true);
    }
  });
});
