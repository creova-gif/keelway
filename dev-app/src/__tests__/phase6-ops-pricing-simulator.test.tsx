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

describe("Phase 6D — Operations Quota, Calibrated Pricing & MiroFish 5-Persona Simulator", () => {
  it("renders calibrated $15 BYOM & $29 Pro tier cards, runs 5-persona MiroFish simulation at $5,000 API spend (+$1000/mo savings), and passes axe-core WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Operations$/i }));

    const simSection = (await screen.findByRole("region", {
      name: /Calibrated pricing and MiroFish market simulator/i,
    }));

    // Verify all 4 calibrated tier cards render cleanly without STREAM jargon
    expect(within(simSection).getByText("Community $0 · 150K tok/day")).toBeInTheDocument();
    expect(within(simSection).getByText("BYOM $15/mo · 0% Markup · 500K tok/day")).toBeInTheDocument();
    expect(within(simSection).getByText("Keelway Pro $29/mo · 2.5M tok/day")).toBeInTheDocument();
    expect(within(simSection).getByText("Enterprise Custom VPC · 50M+ tok/day")).toBeInTheDocument();
    expect(simSection.textContent).not.toMatch(/STREAM\s*[1-5]/i);

    // Default seats = 8, adjust monthly API spend to 5000
    const seatsInput = within(simSection).getByLabelText("Simulation team seats") as HTMLInputElement;
    expect(seatsInput.value).toBe("8");

    const spendSelect = within(simSection).getByLabelText("Simulation monthly API spend") as HTMLSelectElement;
    expect(spendSelect.value).toBe("1200");
    await user.selectOptions(spendSelect, "5000");
    expect(spendSelect.value).toBe("5000");

    // Run 5-persona MiroFish pricing check
    await user.click(
      within(simSection).getByRole("button", { name: /Run 5-Persona MiroFish Pricing Check/i }),
    );

    // Verify KPI strip & proxy tax savings (+$1000/mo)
    expect(within(simSection).getByText("Personas supportive")).toBeInTheDocument();
    expect(within(simSection).getByText("5/5")).toBeInTheDocument();
    expect(within(simSection).getByText("100% vs 40% legacy")).toBeInTheDocument();
    expect(within(simSection).getByText("Hidden-fee distrust")).toBeInTheDocument();
    expect(within(simSection).getByText("0.00")).toBeInTheDocument();
    expect(within(simSection).getByText("Pro gross margin P50/P95")).toBeInTheDocument();
    expect(within(simSection).getByText("93.2% / 83.2%")).toBeInTheDocument();
    expect(within(simSection).getByText("Saved vs 20% proxy tax")).toBeInTheDocument();
    expect(within(simSection).getByText("+$1000/mo")).toBeInTheDocument();

    // Verify all 5 OASIS buyer/creator personas & MiroFish ReportAgent summary
    const verdictList = within(simSection).getByRole("list", { name: /Simulated buyer persona verdicts/i });
    for (const personaName of [
      "Amara Diallo",
      "Marcus Vance",
      "Elena Rostova",
      "David Okafor",
      "Priya Nair",
    ]) {
      expect(within(verdictList).getByText(personaName)).toBeInTheDocument();
    }
    expect(within(verdictList).getAllByText("Supportive")).toHaveLength(5);
    expect(within(simSection).getByText(/MiroFish ReportAgent/i)).toBeInTheDocument();

    expect(await axe(container)).toHaveNoViolations();
  });

  it("posts simulation payload to POST /v1/platform/pricing/simulate when backend runtime is connected", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=sim-tok-6d");
    const simRequests: Array<{ url: string; body: Record<string, unknown> }> = [];

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const pathname = new URL(url, "http://localhost").pathname;
      if (pathname === "/v1/platform/pricing/simulate" && (init?.method ?? "GET").toUpperCase() === "POST") {
        const parsed = JSON.parse(typeof init?.body === "string" ? init.body : "{}") as Record<string, unknown>;
        simRequests.push({ url, body: parsed });
        return new Response(
          JSON.stringify({
            schedule_id: "calibrated",
            supportive_rate: 1.0,
            legacy_supportive_rate: 0.4,
            hidden_fee_distrust_score: 0.0,
            pro_gross_margin_p50_pct: 93.2,
            pro_gross_margin_p95_pct: 83.2,
            proxy_tax_savings_monthly_usd: 3000,
            report_summary: "MiroFish ReportAgent verified live backend pricing simulation.",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });
    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Operations$/i }));

    const simSection = (await screen.findByRole("region", { name: /Calibrated pricing and MiroFish market simulator/i }));
    await user.selectOptions(within(simSection).getByLabelText("Simulation monthly API spend"), "15000");
    await user.click(within(simSection).getByRole("button", { name: /Run 5-Persona MiroFish Pricing Check/i }));

    expect(within(simSection).getByText("Saved vs 20% proxy tax")).toBeInTheDocument();
    expect(await within(simSection).findByText("+$3000/mo")).toBeInTheDocument();
    expect(within(simSection).getByText(/verified live backend pricing simulation/i)).toBeInTheDocument();
    expect(simRequests).toHaveLength(1);
    expect(simRequests[0]!.url).toContain("/v1/platform/pricing/simulate?token=sim-tok-6d");
    expect(simRequests[0]!.body).toMatchObject({ seats: 8, monthly_api_spend_usd: 15000, run_swarm: true });
  });
});
