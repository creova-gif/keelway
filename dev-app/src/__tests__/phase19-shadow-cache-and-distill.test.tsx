import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentsWorkspaceView } from "@/components/platform/AgentsWorkspaceView";
import { ShadowCacheAndDistillationPanel } from "@/components/platform/ShadowCacheAndDistillationPanel";
import { INITIAL_LIFECYCLE_AGENTS, INITIAL_MULTI_AGENT_TEAMS } from "@/lib/platformData";
import {
  canRbacMutateDistill,
  compileDistillationDataset,
  evaluateDistillationPromotion,
  evaluateShadowPrompt,
  fetchDistillationDatasets,
  fetchSemanticCacheStats,
  fetchShadowPairs,
  PlatformDistillHttpError,
  resetDistillFallbackStore,
} from "@/lib/platformDistillApi";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  resetDistillFallbackStore();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 19C — Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation UI", () => {
  it("Test 1: runs shadow evaluation -> exact & 3-gram shingle CACHE_HIT, enforces workspace/task isolation + DLP scrubbing, and switches tabs to compile dpo_preference dataset + PROMOTE_TO_OPENCORE gate", async () => {
    const user = userEvent.setup();
    const { unmount } = render(<ShadowCacheAndDistillationPanel workspaceId="default" activeRbacRole="owner" />);

    const panel = screen.getByRole("region", { name: "Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation" });
    expect(within(panel).getByRole("heading", { name: "Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation" })).toBeInTheDocument();
    expect(within(panel).getByTestId("kpi-cache-hit-rate")).toHaveTextContent("0.0%");

    // 1. First evaluation captures shadow pair & populates semantic prompt cache
    await user.click(within(panel).getByRole("button", { name: "Evaluate shadow prompt" }));
    expect(await within(panel).findByText("LOCAL_PARITY_READY")).toBeInTheDocument();
    expect(within(panel).getByTestId("shadow-match-type")).toHaveTextContent("match_type: cache_miss");
    expect(within(panel).getByTestId("shadow-event-sha256").textContent).toMatch(/^sha256:[0-9a-f]+/);
    expect(within(panel).getByTestId("kpi-captured-shadow-pairs")).toHaveTextContent("1");

    // 2. Re-run identical prompt -> CACHE_HIT (exact_sha256) with $0.0180 and 840 ms saved
    await user.click(within(panel).getByRole("button", { name: "Evaluate shadow prompt" }));
    expect(await within(panel).findByText("CACHE_HIT")).toBeInTheDocument();
    expect(within(panel).getByTestId("shadow-match-type")).toHaveTextContent("match_type: exact_sha256");
    expect(within(panel).getByTestId("shadow-cost-saved-usd")).toHaveTextContent("cost_saved_usd: $0.0180");
    expect(within(panel).getByTestId("kpi-cache-hit-rate")).toHaveTextContent("50.0%");
    expect(within(panel).getByTestId("kpi-total-usd-saved")).toHaveTextContent("$0.0180");
    expect(within(panel).getByTestId("kpi-latency-saved-ms")).toHaveTextContent("840 ms");

    // 3. Near-duplicate 3-gram shingle hit + cross-task/workspace isolation + DLP secret redaction
    const shingleHit = await evaluateShadowPrompt({ workspace_id: "default", task_tag: "code-patch", prompt: "Refactor retry loop with bounded exponential backoff in Python!" }, "owner");
    expect(shingleHit.verdict).toBe("CACHE_HIT");
    expect(shingleHit.match_type).toBe("semantic_shingle");

    const crossTask = await evaluateShadowPrompt({ workspace_id: "default", task_tag: "sql-gen", prompt: "Refactor retry loop with bounded exponential backoff in Python" }, "owner");
    expect(crossTask.verdict).not.toBe("CACHE_HIT");
    const crossWs = await evaluateShadowPrompt({ workspace_id: "hipaa-intake", task_tag: "code-patch", prompt: "Refactor retry loop with bounded exponential backoff in Python" }, "owner");
    expect(crossWs.verdict).not.toBe("CACHE_HIT");

    const dlpEval = await evaluateShadowPrompt({
      workspace_id: "default", task_tag: "secret-audit",
      prompt: "Rotate token sk-live-9876543210secretkey now",
      frontier_response: "Rotated ghp_abcdef1234567890 cleanly",
      local_response: "Stub draft",
    }, "owner");
    expect(dlpEval.verdict).toBe("SHADOW_CAPTURED");
    expect(dlpEval.scrubbed_prompt).toContain("[REDACTED_SECRET]");
    expect(dlpEval.scrubbed_prompt).not.toContain("sk-live-9876543210secretkey");

    // 4. Switch to Tab 2: QLoRA Distillation & Promotion Gate
    const distillTab = within(panel).getByRole("tab", { name: "QLoRA Distillation & Promotion Gate" });
    expect(distillTab).toHaveAttribute("aria-selected", "false");
    await user.click(distillTab);
    expect(distillTab).toHaveAttribute("aria-selected", "true");

    expect(within(panel).getByLabelText("Export Format")).toHaveValue("dpo_preference");
    await user.click(within(panel).getByRole("button", { name: "Compile QLoRA dataset" }));
    expect(await within(panel).findByTestId("distill-dataset-id")).toHaveTextContent(/^qlora-/);
    expect(within(panel).getByTestId("distill-export-format")).toHaveTextContent("dpo_preference");
    expect(within(panel).getByTestId("distill-lora-spec")).toHaveTextContent("LoRA r=16 / alpha=32");
    expect(within(panel).getByTestId("distill-dataset-sha256").textContent).toMatch(/^sha256:[0-9a-f]+/);
    const preview = within(panel).getByLabelText("Compiled QLoRA JSONL preview");
    expect(preview.textContent).toContain('"chosen"');
    expect(preview.textContent).not.toContain("sk-live-9876543210secretkey");

    await user.selectOptions(within(panel).getByLabelText("Export Format"), "sft_jsonl");
    await user.click(within(panel).getByRole("button", { name: "Compile QLoRA dataset" }));
    expect(await within(panel).findByTestId("distill-export-format")).toHaveTextContent("sft_jsonl");
    expect(within(panel).getByLabelText("Compiled QLoRA JSONL preview").textContent).toContain('"messages"');

    // Evaluate promotion gate -> PROMOTE_TO_OPENCORE (minPairs=1 default in UI)
    await user.click(within(panel).getByRole("button", { name: "Evaluate promotion gate" }));
    expect(await within(panel).findByText("PROMOTE_TO_OPENCORE")).toBeInTheDocument();
    expect(within(panel).getByTestId("promo-monthly-savings")).toHaveTextContent("$900.00 / mo saved");
    expect(within(panel).getByTestId("promo-gate-sha256").textContent).toMatch(/^sha256:[0-9a-f]+/);

    // Verify NEEDS_MORE_PAIRS and HOLD_ON_FRONTIER verdicts via API contract
    const needsMore = await evaluateDistillationPromotion({ workspace_id: "default", task_tag: "code-patch", min_pairs: 5 }, "owner");
    expect(needsMore.verdict).toBe("NEEDS_MORE_PAIRS");
    const holdFrontier = await evaluateDistillationPromotion({ workspace_id: "default", task_tag: "secret-audit", min_pairs: 1, min_avg_parity: 0.85 }, "owner");
    expect(holdFrontier.verdict).toBe("HOLD_ON_FRONTIER");

    // Remount to confirm stats, pairs, and dataset hydration
    unmount();
    expect((await fetchSemanticCacheStats("default")).total_hits).toBe(2);
    expect((await fetchShadowPairs("default")).count).toBe(3);
    expect((await fetchDistillationDatasets("default")).count).toBe(2);

    render(<ShadowCacheAndDistillationPanel workspaceId="default" activeRbacRole="owner" />);
    const hydrated = screen.getByRole("region", { name: "Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation" });
    expect(await within(hydrated).findByTestId("kpi-captured-shadow-pairs")).toHaveTextContent("3");
  });

  it("Test 2: mounts inside AgentsWorkspaceView with Bearer/RBAC headers on /v1/platform/distill/* and renders role='alert' on HTTP failure", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=phase19-distill-tok");
    const seen: Array<{ pathname: string; method: string; auth: string | null; role: string | null }> = [];
    const realFetch = globalThis.fetch;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const parsed = new URL(rawUrl, "http://localhost");
      const method = (init?.method ?? "GET").toUpperCase();
      const hdrs = new Headers(init?.headers);
      if (parsed.pathname.startsWith("/v1/platform/distill/")) {
        seen.push({ pathname: parsed.pathname, method, auth: hdrs.get("Authorization"), role: hdrs.get("X-Keelway-Role") });
      }
      if (parsed.pathname === "/v1/platform/distill/cache/stats") {
        return new Response(JSON.stringify({ workspace_id: "default", entry_count: 1, total_hits: 2, total_lookups: 3, hit_rate: 0.6667, total_cost_saved_usd: 0.036, total_latency_saved_ms: 1680, total_dlp_redactions: 0 }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (parsed.pathname === "/v1/platform/distill/shadow/pairs") {
        return new Response(JSON.stringify({ workspace_id: "default", count: 0, pairs: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (parsed.pathname === "/v1/platform/distill/datasets") {
        return new Response(JSON.stringify({ workspace_id: "default", count: 0, datasets: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (parsed.pathname === "/v1/platform/distill/shadow/evaluate" && method === "POST") {
        return new Response(JSON.stringify({ code: "distill_airgap_blocked", detail: "distill_airgap_blocked: Frontier shadow call denied under strict air-gap" }), { status: 403, headers: { "Content-Type": "application/json" } });
      }
      if (typeof realFetch === "function" && !parsed.pathname.startsWith("/v1/")) return realFetch(input, init);
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    render(
      <AgentsWorkspaceView
        experienceMode="builder"
        agents={INITIAL_LIFECYCLE_AGENTS}
        teams={INITIAL_MULTI_AGENT_TEAMS}
        onCreateCustomAgent={() => {}}
        onDispatchTeam={() => {}}
        onUpdateAgentModel={() => {}}
        onJumpToIdeTask={() => {}}
        workspaceId="default"
        activeRbacRole="owner"
      />,
    );

    const panel = await screen.findByRole("region", { name: "Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation" });
    expect(await within(panel).findByTestId("kpi-cache-hit-rate")).toHaveTextContent("66.7%");

    await user.click(within(panel).getByRole("button", { name: "Evaluate shadow prompt" }));
    const alert = await within(panel).findByRole("alert");
    expect(alert).toHaveTextContent("HTTP 403 · distill_airgap_blocked");

    expect(seen.some((c) => c.pathname === "/v1/platform/distill/shadow/evaluate" && c.method === "POST" && c.auth === "Bearer phase19-distill-tok" && c.role === "owner")).toBe(true);
  });

  it("Test 3: enforces auditor and viewer read-only RBAC across both tabs and rejects mutating API calls with 403", async () => {
    const user = userEvent.setup();
    expect(canRbacMutateDistill("auditor")).toBe(false);
    expect(canRbacMutateDistill("viewer")).toBe(false);
    expect(canRbacMutateDistill("owner")).toBe(true);
    expect(canRbacMutateDistill("developer")).toBe(true);

    const { rerender } = render(<ShadowCacheAndDistillationPanel workspaceId="default" activeRbacRole="auditor" />);
    const panel = screen.getByRole("region", { name: "Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation" });
    await within(panel).findByTestId("kpi-cache-hit-rate");

    expect(within(panel).getByText("RBAC: auditor (read-only)")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Evaluate shadow prompt" })).toBeDisabled();

    await user.click(within(panel).getByRole("tab", { name: "QLoRA Distillation & Promotion Gate" }));
    expect(within(panel).getByRole("button", { name: "Compile QLoRA dataset" })).toBeDisabled();
    expect(within(panel).getByRole("button", { name: "Evaluate promotion gate" })).toBeDisabled();

    rerender(<ShadowCacheAndDistillationPanel workspaceId="default" activeRbacRole="viewer" />);
    await within(panel).findByText("RBAC: viewer (read-only)");
    expect(within(panel).getByRole("button", { name: "Compile QLoRA dataset" })).toBeDisabled();
    expect(within(panel).getByRole("button", { name: "Evaluate promotion gate" })).toBeDisabled();

    await expect(evaluateShadowPrompt({ workspace_id: "default" }, "auditor")).rejects.toMatchObject({
      name: "PlatformDistillHttpError", status: 403,
    } satisfies Partial<PlatformDistillHttpError>);
    await expect(compileDistillationDataset({ workspace_id: "default" }, "viewer")).rejects.toMatchObject({
      name: "PlatformDistillHttpError", status: 403,
    } satisfies Partial<PlatformDistillHttpError>);
    await expect(evaluateDistillationPromotion({ workspace_id: "default" }, "auditor")).rejects.toMatchObject({
      name: "PlatformDistillHttpError", status: 403,
    } satisfies Partial<PlatformDistillHttpError>);
  });

  it("Test 4: passes axe-core WCAG 2.2 AA accessibility audit with 0 violations across both tabs in dark and light themes", async () => {
    const user = userEvent.setup();
    const { container } = render(<ShadowCacheAndDistillationPanel workspaceId="default" activeRbacRole="owner" />);
    const panel = screen.getByRole("region", { name: "Semantic Prompt Cache, Shadow Dual-Run & QLoRA Distillation" });

    await user.click(within(panel).getByRole("button", { name: "Evaluate shadow prompt" }));
    await within(panel).findByText("LOCAL_PARITY_READY");
    expect((await axe(container)).violations).toHaveLength(0);
    document.documentElement.setAttribute("data-theme", "light");
    expect((await axe(container)).violations).toHaveLength(0);

    document.documentElement.setAttribute("data-theme", "dark");
    await user.click(within(panel).getByRole("tab", { name: "QLoRA Distillation & Promotion Gate" }));
    await user.click(within(panel).getByRole("button", { name: "Compile QLoRA dataset" }));
    await user.click(within(panel).getByRole("button", { name: "Evaluate promotion gate" }));
    await within(panel).findByText("PROMOTE_TO_OPENCORE");

    expect((await axe(container)).violations).toHaveLength(0);
    document.documentElement.setAttribute("data-theme", "light");
    expect((await axe(container)).violations).toHaveLength(0);
  });
});
