import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormalSafetyAndEdgeMeshPanel } from "@/components/platform/FormalSafetyAndEdgeMeshPanel";
import { SecurityWorkspaceView } from "@/components/platform/SecurityWorkspaceView";
import {
  canRbacMutateSafetyMesh,
  dispatchMeshHandoff,
  listMeshHandoffs,
  listSafetyVerifications,
  PlatformSafetyMeshHttpError,
  registerMeshNode,
  resetSafetyMeshFallbackStore,
  verifyWorkflowSafety,
} from "@/lib/platformSafetyMeshApi";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  resetSafetyMeshFallbackStore();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 17C — Formal Safety State-Machine Verifier & Federated Edge Mesh", () => {
  it("Test 1: loads initial mesh nodes, verifies state-machine safety (VIOLATION_FOUND + counterexample path), and injects P-10 guard to reach VERIFIED_SAFE", async () => {
    const user = userEvent.setup();
    render(<FormalSafetyAndEdgeMeshPanel workspaceId="default" activeRbacRole="owner" />);

    const panel = screen.getByRole("region", {
      name: "Formal safety state-machine verifier and federated edge mesh",
    });
    expect(
      within(panel).getByRole("heading", {
        name: "Formal Safety State-Machine Verifier & Federated Edge Mesh",
      }),
    ).toBeInTheDocument();

    // Verify seeded attested mesh nodes load on mount
    const nodeList = await within(panel).findByRole("list", { name: "Attested mesh nodes" });
    expect(await within(nodeList).findByText("edge-mac-m3-max")).toBeInTheDocument();
    expect(within(nodeList).getByText("edge_local")).toBeInTheDocument();
    expect(within(nodeList).getByText("apple_metal_secure_enclave")).toBeInTheDocument();
    expect(within(nodeList).getByText("cluster-h100-us-east")).toBeInTheDocument();
    expect(within(nodeList).getByText("cluster_burst")).toBeInTheDocument();
    expect(within(nodeList).getByText("nvidia_h100_cc")).toBeInTheDocument();

    // Verify preset & Air-Gap Zero-Egress Mode controls
    const wfSelect = within(panel).getByLabelText("Workflow State-Machine Preset");
    expect(wfSelect).toHaveValue("treasury-wire-approver");
    const airgapCheckbox = within(panel).getByLabelText("Air-Gap Zero-Egress Mode");
    expect(airgapCheckbox).not.toBeChecked();
    await user.click(airgapCheckbox);
    expect(airgapCheckbox).toBeChecked();

    // 1. Trigger Verify State-Machine Safety -> VIOLATION_FOUND
    await user.click(within(panel).getByRole("button", { name: "Verify State-Machine Safety" }));

    expect((await within(panel).findAllByText("VIOLATION_FOUND")).length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText(/states_explored: 3/)).toBeInTheDocument();

    const invList = within(panel).getByRole("list", { name: "Formal safety invariants" });
    expect(within(invList).getByText("no_unguarded_destructive_tool")).toBeInTheDocument();
    expect(within(invList).getByText("no_privilege_escalation")).toBeInTheDocument();
    expect(within(invList).getByText("bounded_termination")).toBeInTheDocument();
    expect(within(invList).getByText("airgap_zero_egress")).toBeInTheDocument();
    expect(within(invList).getAllByText("FAIL")).toHaveLength(1);
    expect(within(invList).getAllByText("PASS")).toHaveLength(3);

    expect(within(panel).getByTestId("safety-counterexample-path")).toHaveTextContent(
      "ingest_invoice → validate_vendor → execute_wire_transfer",
    );
    expect(within(panel).getByTestId("safety-proof-sha256").textContent).toMatch(/^sha256:[0-9a-f]+/);

    // 2. Trigger Inject P-10 Guard & Re-Verify -> VERIFIED_SAFE
    await user.click(within(panel).getByRole("button", { name: "Inject P-10 Guard & Re-Verify" }));

    expect((await within(panel).findAllByText("VERIFIED_SAFE")).length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText(/p10_guards_injected: execute_wire_transfer/)).toBeInTheDocument();
    const refreshedInvList = within(panel).getByRole("list", { name: "Formal safety invariants" });
    expect(within(refreshedInvList).getAllByText("PASS")).toHaveLength(4);
  });

  it("Test 2: dispatches attested edge-to-cluster handoff (ATTESTED_COMPLETE + zero_raw_pii_egress), supports PINNED_EDGE_ONLY, and hydrates persisted records", async () => {
    const user = userEvent.setup();
    await registerMeshNode(
      {
        workspace_id: "default",
        node_id: "edge-linux-tpm2",
        name: "Edge Linux TPM2 Gateway",
        tier: "edge_local",
        hardware_hal: "linux_tpm2",
        vram_gb: 32,
      },
      "owner",
    );

    const { unmount } = render(<FormalSafetyAndEdgeMeshPanel workspaceId="default" activeRbacRole="owner" />);
    const panel = screen.getByRole("region", {
      name: "Formal safety state-machine verifier and federated edge mesh",
    });

    const dataClassSelect = within(panel).getByLabelText("Data Classification");
    expect(dataClassSelect).toHaveValue("restricted_pii");
    const allowBurstCheckbox = within(panel).getByLabelText("Allow Sanitized Cluster Burst");
    expect(allowBurstCheckbox).toBeChecked();

    // Dispatch Attested Edge-to-Cluster Handoff -> ATTESTED_COMPLETE
    await user.click(within(panel).getByRole("button", { name: "Dispatch Attested Edge-to-Cluster Handoff" }));

    expect((await within(panel).findAllByText("ATTESTED_COMPLETE")).length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText("zero_raw_pii_egress")).toBeInTheDocument();
    expect(within(panel).getByText("total_cost_usd: $0.04")).toBeInTheDocument();

    const stagesList = within(panel).getByRole("list", { name: "Mesh handoff stage placements" });
    expect(within(stagesList).getByText(/edge_pii_scrub_intake/)).toBeInTheDocument();
    expect(within(stagesList).getByText(/tee_cohort_synthesis/)).toBeInTheDocument();
    expect(within(panel).getByTestId("mesh-handoff-attestation-sha256").textContent).toMatch(/^sha256:[0-9a-f]+/);

    // Uncheck Allow Sanitized Cluster Burst -> PINNED_EDGE_ONLY ($0.00)
    await user.click(allowBurstCheckbox);
    await user.click(within(panel).getByRole("button", { name: "Dispatch Attested Edge-to-Cluster Handoff" }));
    expect((await within(panel).findAllByText("PINNED_EDGE_ONLY")).length).toBeGreaterThanOrEqual(1);
    expect(within(panel).getByText("total_cost_usd: $0.00")).toBeInTheDocument();

    unmount();
    expect((await listMeshHandoffs("default")).length).toBe(2);

    // Direct fail-closed 422 check on raw restricted_pii cloud burst
    await expect(
      dispatchMeshHandoff({ workspace_id: "default", data_classification: "restricted_pii", force_raw_cloud_burst: true }, "owner"),
    ).rejects.toMatchObject({ name: "PlatformSafetyMeshHttpError", status: 422, code: "mesh_sovereignty_violation" } satisfies Partial<PlatformSafetyMeshHttpError>);
  });

  it("Test 3: enforces auditor and viewer read-only RBAC disabling all mutation buttons and rejecting direct mutating calls with 403", async () => {
    expect(canRbacMutateSafetyMesh("auditor")).toBe(false);
    expect(canRbacMutateSafetyMesh("viewer")).toBe(false);
    expect(canRbacMutateSafetyMesh("owner")).toBe(true);
    expect(canRbacMutateSafetyMesh("admin")).toBe(true);
    expect(canRbacMutateSafetyMesh("developer")).toBe(true);
    expect(canRbacMutateSafetyMesh("operator")).toBe(true);

    // Seed one verification first so auditor read-only hydration also exercises listSafetyVerifications
    await verifyWorkflowSafety({ workspace_id: "default", inject_p10_guards: true }, "owner");
    expect((await listSafetyVerifications("default")).length).toBe(1);

    render(<FormalSafetyAndEdgeMeshPanel workspaceId="default" activeRbacRole="auditor" />);
    const panel = screen.getByRole("region", {
      name: "Formal safety state-machine verifier and federated edge mesh",
    });

    expect(within(panel).getByText("RBAC: auditor (read-only)")).toBeInTheDocument();
    expect((await within(panel).findAllByText("VERIFIED_SAFE")).length).toBeGreaterThanOrEqual(1);

    expect(within(panel).getByRole("button", { name: "Verify State-Machine Safety" })).toBeDisabled();
    expect(within(panel).getByRole("button", { name: "Inject P-10 Guard & Re-Verify" })).toBeDisabled();
    expect(within(panel).getByRole("button", { name: "Dispatch Attested Edge-to-Cluster Handoff" })).toBeDisabled();

    await expect(verifyWorkflowSafety({ workspace_id: "default" }, "auditor")).rejects.toMatchObject({
      name: "PlatformSafetyMeshHttpError",
      status: 403,
    } satisfies Partial<PlatformSafetyMeshHttpError>);
  });

  it("Test 4: mounts in SecurityWorkspaceView, sends auth/role/actor headers, surfaces HTTP 422 sovereignty alerts, and passes axe WCAG 2.2 AA in dark & light themes", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=phase17-sec-tok");
    const seenCalls: Array<{ pathname: string; method: string; auth: string | null; role: string | null; actor: string | null }> = [];
    const realFetch = globalThis.fetch;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const parsed = new URL(rawUrl, "http://localhost");
      const method = (init?.method ?? "GET").toUpperCase();
      const hdrs = new Headers(init?.headers);
      if (parsed.pathname.startsWith("/v1/platform/safety/") || parsed.pathname.startsWith("/v1/platform/mesh/")) {
        seenCalls.push({
          pathname: parsed.pathname,
          method,
          auth: hdrs.get("Authorization"),
          role: hdrs.get("X-Keelway-Role"),
          actor: hdrs.get("X-Keelway-Actor"),
        });
      }
      if (parsed.pathname === "/v1/platform/safety/verifications") {
        return new Response(JSON.stringify({ workspace_id: "default", count: 0, verifications: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (parsed.pathname === "/v1/platform/mesh/nodes") {
        return new Response(
          JSON.stringify({
            workspace_id: "default",
            count: 2,
            nodes: [
              { node_id: "edge-mac-m3-max", workspace_id: "default", name: "Edge Mac Studio", tier: "edge_local", hardware_hal: "apple_metal_secure_enclave", region: "local-loopback", vram_gb: 64, status: "ONLINE", attestation_sha256: "sha256:11223344556677889900aabbccddeeff", registered_at: "2026-11-16T00:00:00Z" },
              { node_id: "cluster-h100-us-east", workspace_id: "default", name: "Cluster H100", tier: "cluster_burst", hardware_hal: "nvidia_h100_cc", region: "us-east-tee", vram_gb: 80, status: "ONLINE", attestation_sha256: "sha256:ffeeddccbbaa00998877665544332211", registered_at: "2026-11-16T00:00:00Z" },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (parsed.pathname === "/v1/platform/mesh/handoffs") {
        return new Response(JSON.stringify({ workspace_id: "default", count: 0, handoffs: [] }), { status: 200, headers: { "Content-Type": "application/json" } });
      }
      if (parsed.pathname === "/v1/platform/mesh/dispatch" && method === "POST") {
        return new Response(
          JSON.stringify({ code: "mesh_sovereignty_violation", detail: "mesh_sovereignty_violation: Raw restricted_pii blocked from unattested cloud egress" }),
          { status: 422, headers: { "Content-Type": "application/json" } },
        );
      }
      if (typeof realFetch === "function" && !parsed.pathname.startsWith("/v1/")) {
        return realFetch(input, init);
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    const { container } = render(
      <SecurityWorkspaceView installedPackagesCount={12} workspaceId="default" activeRbacRole="owner" />,
    );

    const safetyMeshPanel = await screen.findByRole("region", {
      name: "Formal safety state-machine verifier and federated edge mesh",
    });
    await within(safetyMeshPanel).findByText("edge-mac-m3-max");

    await user.click(within(safetyMeshPanel).getByRole("button", { name: "Dispatch Attested Edge-to-Cluster Handoff" }));
    const alert = await within(safetyMeshPanel).findByRole("alert");
    expect(alert).toHaveTextContent("HTTP 422 · mesh_sovereignty_violation");

    expect(
      seenCalls.some(
        (c) =>
          c.pathname === "/v1/platform/mesh/dispatch" &&
          c.method === "POST" &&
          c.auth === "Bearer phase17-sec-tok" &&
          c.role === "owner" &&
          c.actor === "studio-owner",
      ),
    ).toBe(true);

    expect((await axe(container)).violations).toHaveLength(0);
    document.documentElement.setAttribute("data-theme", "light");
    expect((await axe(container)).violations).toHaveLength(0);
  });
});
