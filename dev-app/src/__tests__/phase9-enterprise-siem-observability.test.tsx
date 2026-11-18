import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/App";
import { resetLocalEnterpriseState, saveOidcConfig } from "@/lib/platformEnterpriseApi";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  resetLocalEnterpriseState();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 9C — Enterprise OIDC/SCIM 2.0, Dual-Human P-10 Quorum, SIEM & OpenTelemetry Observability", () => {
  it("provisions SCIM 2.0 users, enforces Dual-Human P-10 Quorum (2-of-2 + duplicate signer block + RBAC), and passes axe WCAG 2.2 AA on Security view", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Security$/i }));

    const entSection = screen.getByRole("region", {
      name: /Enterprise OIDC, SCIM 2.0 directory and dual-human P-10 quorum/i,
    });
    expect(within(entSection).getByText("https://idp.enterprise.example")).toBeInTheDocument();

    // Provision SCIM 2.0 user mapped to operator via keelway-operators group
    const emailInput = within(entSection).getByLabelText("SCIM user email") as HTMLInputElement;
    const groupSelect = within(entSection).getByLabelText("SCIM IdP group") as HTMLSelectElement;
    const provisionBtn = within(entSection).getByRole("button", { name: /Provision SCIM 2\.0 User/i });

    expect(emailInput.value).toBe("");
    await user.type(emailInput, "sre.lead@enterprise.example");
    await user.selectOptions(groupSelect, "keelway-operators");
    await user.click(provisionBtn);

    const scimList = within(entSection).getByRole("list", { name: /SCIM 2\.0 directory users/i });
    expect(await within(scimList).findByText("sre.lead@enterprise.example")).toBeInTheDocument();
    expect(within(scimList).getByText("operator")).toBeInTheDocument();
    expect(within(scimList).getAllByText("active").length).toBeGreaterThanOrEqual(2);

    // Dual-Human P-10 Quorum Gate (2-of-2)
    const proposalInput = within(entSection).getByLabelText("Quorum proposal ID") as HTMLInputElement;
    const approverInput = within(entSection).getByLabelText("Human approver identity") as HTMLInputElement;
    const signBtn = within(entSection).getByRole("button", { name: /Sign P-10 Quorum Approval/i });

    expect(proposalInput.value).toBe("prop-prod-deploy-001");
    expect(approverInput.value).toBe("alice@keelway.local");
    expect(within(entSection).getAllByText("0 / 2").length).toBeGreaterThan(0);

    // 1st human signer: alice@keelway.local -> 1 / 2 · awaiting_quorum
    await user.click(signBtn);
    expect((await within(entSection).findAllByText("1 / 2 · awaiting_quorum")).length).toBeGreaterThan(0);
    expect(within(entSection).getByText("alice@keelway.local")).toBeInTheDocument();

    // Duplicate signer attempt -> error alert
    await user.click(signBtn);
    const dupAlert = await within(entSection).findByRole("alert");
    expect(dupAlert).toHaveTextContent(/Duplicate signer rejected/i);

    // RBAC checks across roles
    const rbacSelect = screen.getByLabelText(/Active RBAC role/i);

    await user.selectOptions(rbacSelect, "viewer");
    expect(within(entSection).getByRole("button", { name: /Provision SCIM 2\.0 User/i })).toBeDisabled();
    expect(within(entSection).getByRole("button", { name: /Sign P-10 Quorum Approval/i })).toBeDisabled();

    await user.selectOptions(rbacSelect, "builder");
    expect(within(entSection).getByRole("button", { name: /Provision SCIM 2\.0 User/i })).toBeDisabled();
    expect(within(entSection).getByRole("button", { name: /Sign P-10 Quorum Approval/i })).toBeDisabled();

    await user.selectOptions(rbacSelect, "admin");
    expect(within(entSection).getByRole("button", { name: /Provision SCIM 2\.0 User/i })).toBeEnabled();
    expect(within(entSection).getByRole("button", { name: /Sign P-10 Quorum Approval/i })).toBeDisabled();

    // Operator is allowed to sign P-10 Quorum (2nd distinct human signer: bob@keelway.local -> quorum_approved)
    await user.selectOptions(rbacSelect, "operator");
    expect(within(entSection).getByRole("button", { name: /Provision SCIM 2\.0 User/i })).toBeDisabled();
    const operatorSignBtn = within(entSection).getByRole("button", { name: /Sign P-10 Quorum Approval/i });
    expect(operatorSignBtn).toBeEnabled();

    await user.clear(approverInput);
    await user.type(approverInput, "bob@keelway.local");
    await user.click(operatorSignBtn);

    expect((await within(entSection).findAllByText("2 / 2 · quorum_approved")).length).toBeGreaterThan(0);
    expect(within(entSection).getByText("bob@keelway.local")).toBeInTheDocument();
    expect(within(entSection).getByText(/^sha256:[0-9a-f]+/i)).toBeInTheDocument();

    const axeResults = await axe(container);
    expect(axeResults.violations).toHaveLength(0);
  });

  it("exports SIEM audit batches across OCSF & ArcSight CEF, refreshes OpenTelemetry/Prometheus telemetry, and passes axe WCAG 2.2 AA on Operations view", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Operations$/i }));

    const siemObsSection = screen.getByRole("region", {
      name: /SIEM audit streaming and OpenTelemetry observability/i,
    });

    const formatSelect = within(siemObsSection).getByLabelText("SIEM export format") as HTMLSelectElement;
    const exportBtn = within(siemObsSection).getByRole("button", { name: /Export SIEM Audit Batch/i });

    // Export OCSF v1.1 JSON
    expect(formatSelect.value).toBe("ocsf");
    await user.click(exportBtn);
    expect(await within(siemObsSection).findByText(/OCSF · 3 events/i)).toBeInTheDocument();
    const ocsfPreview = within(siemObsSection).getByRole("region", { name: /Exported SIEM audit records preview/i });
    expect(ocsfPreview).toHaveTextContent(/"class_uid":6003/);
    const ocsfSha = within(siemObsSection).getByText(/^sha256:[0-9a-f]+/i).textContent;

    // Export ArcSight CEF
    await user.selectOptions(formatSelect, "cef");
    await user.click(exportBtn);
    expect(await within(siemObsSection).findByText(/CEF · 3 events/i)).toBeInTheDocument();
    expect(within(siemObsSection).getByRole("region", { name: /Exported SIEM audit records preview/i })).toHaveTextContent(
      /CEF:0\|Keelway\|SovereignCore\|1\.1/,
    );
    const cefSha = within(siemObsSection).getByText(/^sha256:[0-9a-f]+/i).textContent;
    expect(cefSha).not.toBe(ocsfSha);

    // Refresh Telemetry Snapshot
    const refreshBtn = within(siemObsSection).getByRole("button", { name: /Refresh Telemetry Snapshot/i });
    await user.click(refreshBtn);

    expect(within(siemObsSection).getByText("keelway_kflow_runs_total")).toBeInTheDocument();
    expect(within(siemObsSection).getByText("keelway_crdt_entries_total")).toBeInTheDocument();
    expect(within(siemObsSection).getByText("keelway_mcp_servers_total")).toBeInTheDocument();
    expect(within(siemObsSection).getByText("keelway_scim_active_users")).toBeInTheDocument();
    expect(within(siemObsSection).getByText("keelway_p10_quorum_approved_total")).toBeInTheDocument();
    expect(within(siemObsSection).getByText("keelway_siem_exports_total")).toBeInTheDocument();

    const promPreview = within(siemObsSection).getByRole("region", { name: /Prometheus metrics exposition preview/i });
    expect(promPreview).toHaveTextContent(/keelway_siem_exports_total\{workspace_id="default"\} 2/);

    const axeResults = await axe(container);
    expect(axeResults.violations).toHaveLength(0);
  });

  it("wires exact /v1/platform/enterprise/* and /v1/platform/observability/metrics routes with session token & X-Keelway-Role headers and surfaces HTTP 4xx errors", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=phase9-ent-tok");
    const calls: Array<{ pathname: string; method: string; url: string; role: string | null }> = [];
    let rejectQuorum = false;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const pathname = new URL(url, "http://localhost").pathname;
      const method = (init?.method ?? "GET").toUpperCase();
      const hdrs = new Headers(init?.headers);
      calls.push({ pathname, method, url, role: hdrs.get("X-Keelway-Role") });

      if (pathname === "/v1/platform/enterprise/oidc" && method === "PUT") {
        return new Response(
          JSON.stringify({ workspace_id: "default", issuer: "https://sso.acme-corp.example", client_id: "keelway-enterprise" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/observability/metrics" && method === "GET") {
        return new Response(
          JSON.stringify({
            workspace_id: "default",
            counters: {
              keelway_kflow_runs_total: 12,
              keelway_crdt_entries_total: 19,
              keelway_mcp_servers_total: 5,
              keelway_scim_active_users: 7,
              keelway_p10_quorum_approved_total: 3,
              keelway_siem_exports_total: 9,
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/enterprise/p10-quorum/approve" && method === "POST" && rejectQuorum) {
        return new Response(JSON.stringify({ detail: "Initiator cannot self-approve P-10 proposal." }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    const savedOidc = await saveOidcConfig({ workspace_id: "default", issuer: "https://sso.acme-corp.example" }, "owner");
    expect(savedOidc.issuer).toBe("https://sso.acme-corp.example");

    render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });
    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });

    await user.click(within(platformNav).getByRole("button", { name: /^Operations$/i }));
    const siemObsSection = screen.getByRole("region", { name: /SIEM audit streaming and OpenTelemetry observability/i });
    await user.click(within(siemObsSection).getByRole("button", { name: /Refresh Telemetry Snapshot/i }));
    expect(await within(siemObsSection).findByText(/keelway_kflow_runs_total\{workspace_id="default"\} 12/)).toBeInTheDocument();

    rejectQuorum = true;
    await user.click(within(platformNav).getByRole("button", { name: /^Security$/i }));
    const entSection = screen.getByRole("region", {
      name: /Enterprise OIDC, SCIM 2.0 directory and dual-human P-10 quorum/i,
    });
    await user.click(within(entSection).getByRole("button", { name: /Sign P-10 Quorum Approval/i }));
    expect(await within(entSection).findByRole("alert")).toHaveTextContent(/Initiator cannot self-approve P-10 proposal/i);

    expect(
      calls.some(
        (c) =>
          c.pathname === "/v1/platform/observability/metrics" &&
          c.url.includes("token=phase9-ent-tok") &&
          c.role === "owner",
      ),
    ).toBe(true);
  });
});
