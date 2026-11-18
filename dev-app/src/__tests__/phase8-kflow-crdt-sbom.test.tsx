import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { App } from "@/App";
import { resetLocalKflowCrdtState } from "@/lib/platformKflowApi";
import { axe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  vi.restoreAllMocks();
  resetLocalKflowCrdtState();
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("dir", "ltr");
  window.history.replaceState({}, "", "/app/");
});

describe("Phase 8C — Live KFlow Topological Runner, KSpaces CRDT Sync & CycloneDX 1.5 SBOM", () => {
  it("executes Topological KFlow DAG, holds at P-10 checkpoint, enforces RBAC (blocks builder/admin/viewer, allows owner), completes DAG, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Automation$/i }));

    const kflowSection = screen.getByRole("region", {
      name: /Topological KFlow DAG runner and KSpaces CRDT sync/i,
    });
    const p10Checkbox = within(kflowSection).getByLabelText("Require P-10 gate on final DAG step") as HTMLInputElement;
    if (!p10Checkbox.checked) await user.click(p10Checkbox);
    expect(p10Checkbox.checked).toBe(true);

    const execBtn = within(kflowSection).getByRole("button", { name: /Execute Topological DAG/i });
    await user.click(execBtn);

    expect(await within(kflowSection).findByText("awaiting_p10")).toBeInTheDocument();
    expect(within(kflowSection).getByText("Wave 0 -> Wave 1")).toBeInTheDocument();
    expect(within(kflowSection).getByText("Held at P-10 node: n-2")).toBeInTheDocument();
    expect(within(kflowSection).getAllByText(/^sha256:/i).length).toBeGreaterThan(0);

    const rbacSelect = screen.getByLabelText(/Active RBAC role/i);

    await user.selectOptions(rbacSelect, "builder");
    expect(within(kflowSection).getByRole("button", { name: /Approve Held DAG Node/i })).toBeDisabled();
    expect(within(kflowSection).getByText(/RBAC Lock \(builder\)/i)).toBeInTheDocument();

    await user.selectOptions(rbacSelect, "admin");
    expect(within(kflowSection).getByRole("button", { name: /Approve Held DAG Node/i })).toBeDisabled();

    await user.selectOptions(rbacSelect, "viewer");
    expect(within(kflowSection).getByRole("button", { name: /Execute Topological DAG/i })).toBeDisabled();
    expect(within(kflowSection).getByRole("button", { name: /Approve Held DAG Node/i })).toBeDisabled();

    await user.selectOptions(rbacSelect, "owner");
    const approveBtn = within(kflowSection).getByRole("button", { name: /Approve Held DAG Node/i });
    expect(approveBtn).toBeEnabled();
    await user.click(approveBtn);

    expect(await within(kflowSection).findByText("completed")).toBeInTheDocument();
    expect(within(kflowSection).queryByText("Held at P-10 node: n-2")).toBeNull();

    const axeResults = await axe(container);
    expect(axeResults.violations).toHaveLength(0);
  });

  it("syncs KSpaces CRDT operations across multiple peers, updates vector clock & SHA-256 state digest, locks mutations for viewer, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });

    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });
    await user.click(within(platformNav).getByRole("button", { name: /^Automation$/i }));

    const crdtRegion = screen.getByRole("region", { name: /KSpaces CRDT state synchronization/i });
    const peerInput = within(crdtRegion).getByLabelText("CRDT peer ID") as HTMLInputElement;
    const keyInput = within(crdtRegion).getByLabelText("CRDT entry key") as HTMLInputElement;
    const valInput = within(crdtRegion).getByLabelText("CRDT entry value") as HTMLInputElement;
    const syncBtn = within(crdtRegion).getByRole("button", { name: /Sync CRDT Operation/i });

    expect(peerInput.value).toBe("peer-local-ide");
    expect(keyInput.value).toBe("sprint.active_focus");
    expect(valInput.value).toBe("KEEL-GA-015");

    await user.click(syncBtn);
    expect(await within(crdtRegion).findByText("peer-local-ide: 1")).toBeInTheDocument();
    expect(within(crdtRegion).getByText("Active CRDT Keys: 1")).toBeInTheDocument();
    expect(within(crdtRegion).getByText(/sprint\.active_focus = KEEL-GA-015/i)).toBeInTheDocument();
    const digestAfterPeer1 = within(crdtRegion).getByText(/^sha256:[0-9a-f]+/i).textContent;

    await user.clear(peerInput);
    await user.type(peerInput, "peer-ci-runner");
    await user.clear(keyInput);
    await user.type(keyInput, "release.gate_status");
    await user.clear(valInput);
    await user.type(valInput, "verified-ga");
    await user.click(syncBtn);

    expect(await within(crdtRegion).findByText("peer-ci-runner: 2")).toBeInTheDocument();
    expect(within(crdtRegion).getByText("peer-local-ide: 1")).toBeInTheDocument();
    expect(within(crdtRegion).getByText("Active CRDT Keys: 2")).toBeInTheDocument();
    const digestAfterPeer2 = within(crdtRegion).getByText(/^sha256:[0-9a-f]+/i).textContent;
    expect(digestAfterPeer2).not.toBe(digestAfterPeer1);

    await user.selectOptions(screen.getByLabelText(/Active RBAC role/i), "viewer");
    expect(within(crdtRegion).getByRole("button", { name: /Sync CRDT Operation/i })).toBeDisabled();

    const axeResults = await axe(container);
    expect(axeResults.violations).toHaveLength(0);
  });

  it("generates & verifies CycloneDX 1.5 SBOM in SecurityWorkspaceView, wires live /v1/platform/* endpoints without masking HTTP 400/403, and passes axe WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=phase8-sbom-tok");
    const calls: Array<{ pathname: string; method: string; url: string; role: string | null }> = [];
    let rejectNextKflow = false;

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      const pathname = new URL(url, "http://localhost").pathname;
      const method = (init?.method ?? "GET").toUpperCase();
      const hdrs = new Headers(init?.headers);
      calls.push({ pathname, method, url, role: hdrs.get("X-Keelway-Role") });

      if (pathname === "/v1/platform/security/sbom" && method === "GET") {
        return new Response(
          JSON.stringify({
            workspace_id: "default",
            verified: true,
            verification_status: "VERIFIED",
            bom_format: "CycloneDX",
            spec_version: "1.5",
            serial_number: "urn:uuid:3e671687-395b-41f5-a30f-998877665544",
            component_count: 34,
            root_digest_sha256: "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            provenance_signature: "hmac-sha256:live-sig-8c",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (pathname === "/v1/platform/automation/workflows/execute" && method === "POST" && rejectNextKflow) {
        return new Response(JSON.stringify({ detail: "Cycle detected in workflow graph." }), {
          status: 400,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "Content-Type": "application/json" } });
    });

    const { container } = render(<App />);
    await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });
    const platformNav = screen.getByRole("navigation", { name: "Unified platform views" });

    await user.click(within(platformNav).getByRole("button", { name: /^Security$/i }));
    const sbomSection = screen.getByRole("region", {
      name: /CycloneDX 1.5 SBOM and supply-chain provenance/i,
    });
    await user.click(within(sbomSection).getByRole("button", { name: /Generate & Verify CycloneDX 1.5 SBOM/i }));

    expect(await within(sbomSection).findByText("CycloneDX · v1.5")).toBeInTheDocument();
    expect(within(sbomSection).getByText("VERIFIED")).toBeInTheDocument();
    expect(within(sbomSection).getByText("34 components")).toBeInTheDocument();
    expect(within(sbomSection).getByText(/sha256:0123456789abcdef/i)).toBeInTheDocument();
    expect(within(sbomSection).getByText(/urn:uuid:3e671687-395b-41f5-a30f-998877665544/i)).toBeInTheDocument();

    const axeSecurity = await axe(container);
    expect(axeSecurity.violations).toHaveLength(0);

    // Verify HTTP 400 from backend is surfaced via alert and never masked by offline fallback
    rejectNextKflow = true;
    await user.click(within(platformNav).getByRole("button", { name: /^Automation$/i }));
    const kflowSection = screen.getByRole("region", { name: /Topological KFlow DAG runner and KSpaces CRDT sync/i });
    await user.click(within(kflowSection).getByRole("button", { name: /Execute Topological DAG/i }));
    expect(await within(kflowSection).findByRole("alert")).toHaveTextContent(/Cycle detected in workflow graph/i);

    expect(calls.some((c) => c.pathname === "/v1/platform/security/sbom" && c.url.includes("token=phase8-sbom-tok") && c.role === "owner")).toBe(true);
  });
});
