import { readFileSync } from "node:fs";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SettingsWorkspace } from "@/components/screens/SettingsWorkspace";
import { App } from "@/App";
import { runAxe } from "@/test/setup";
import "@/styles/tokens.css";

afterEach(() => {
  document.documentElement.setAttribute("data-theme", "dark");
  document.documentElement.setAttribute("data-density", "default");
  document.documentElement.setAttribute("lang", "en");
  document.documentElement.setAttribute("dir", "ltr");
  document.documentElement.removeAttribute("data-reduce-motion");
  window.history.replaceState({}, "", "/app/");
});

describe("Screen 08 — SettingsPermissionsPanel (Permissions & Agent Manifests)", () => {
  it("renders p-13 -> p-14 prompt-drift banner, clears drift on Re-confirm, and preserves immutable P-10 invariants", async () => {
    const user = userEvent.setup();
    render(
      <React.StrictMode>
        <SettingsWorkspace defaultSubSection="permissions" />
      </React.StrictMode>,
    );

    const driftBanner = screen.getByText("Prompt version changed: p-13 → p-14").closest("[data-callout-variant='prompt-drift']");
    if (!(driftBanner instanceof HTMLElement)) throw new Error("Expected prompt-drift banner element");
    expect(within(driftBanner).getByText("2 Allow always rules are paused until you re-confirm them.")).toBeInTheDocument();
    expect(within(driftBanner).getByRole("button", { name: /Review 2 rules/i })).toBeInTheDocument();

    // Immutable invariants card
    expect(screen.getByText("Network and deploy")).toBeInTheDocument();
    expect(screen.getByText(/Domain-regulated actions CRE-231 \/ CRE-42/i)).toBeInTheDocument();
    expect(screen.getAllByText("Always ask").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Only a person, at this keyboard")).toBeInTheDocument();
    expect(screen.getByText(/Agents and CLI scripts cannot approve P-10 gates/i)).toBeInTheDocument();

    // Re-confirm one row first -> banner updates to 1 rule
    const rulesTable = screen.getByRole("table", { name: /Scoped Allow always rules/i });
    const firstReconfirmBtn = within(rulesTable).getAllByRole("button", { name: /^Re-confirm$/i })[0]!;
    await user.click(firstReconfirmBtn);
    expect(screen.getByText("1 Allow always rule is paused until you re-confirm it.")).toBeInTheDocument();
    expect(within(rulesTable).getByText("Active")).toBeInTheDocument();

    // Re-confirm all clears the drift banner completely
    await user.click(screen.getByRole("button", { name: /Re-confirm all/i }));
    expect(screen.queryByText(/Prompt version changed:/i)).toBeNull();
    expect(within(rulesTable).getAllByText("Active")).toHaveLength(2);

    // Revoke all transitions cleanly to honest empty state
    await user.click(screen.getByRole("button", { name: /Revoke all/i }));
    expect(screen.getByText("No standing Allow always rules — Keelway asks every time.")).toBeInTheDocument();
  });

  it("loads keelway.agent/v1 manifests, toggles Kill-Switch, and validates live manifest JSON via /v1/studio/manifests/inspect", async () => {
    const user = userEvent.setup();
    render(<SettingsWorkspace defaultSubSection="permissions" />);

    const manifestTable = await screen.findByRole("table", { name: /Agent manifest registry/i });
    expect(within(manifestTable).getByText("test-fixer@1.2.0")).toBeInTheDocument();
    expect(within(manifestTable).getByText(/Static guard: write\/exec tools gated by workspace Seatbelt scope/i)).toBeInTheDocument();
    expect(within(manifestTable).getAllByText("keelway.agent/v1").length).toBeGreaterThan(0);
    expect(within(manifestTable).getAllByText("Verified").length).toBeGreaterThan(0);

    const toggleBtn = within(manifestTable).getByRole("button", { name: /Kill-switch for test-fixer@1.2.0/i });
    expect(toggleBtn).toHaveAttribute("aria-pressed", "true");
    await user.click(toggleBtn);
    await waitFor(() => expect(toggleBtn).toHaveAttribute("aria-pressed", "false"));
    expect(toggleBtn).toHaveTextContent(/Disabled/i);

    // Validate prefilled manifest JSON, then validate a network-enabled high-risk manifest & invalid JSON
    const inspectorInput = screen.getByLabelText(/Manifest JSON \(keelway\.agent\/v1\)/i);
    await user.click(screen.getByRole("button", { name: /Validate manifest/i }));
    const inspectRegion = await screen.findByTestId("manifest-inspect-result");
    expect(within(inspectRegion).getByText("Valid")).toBeInTheDocument();
    expect(within(inspectRegion).getByText(/P-10 human gate required/i)).toBeInTheDocument();

    fireEvent.change(inspectorInput, {
      target: {
        value: JSON.stringify({
          schemaVersion: "keelway.agent/v1",
          name: "deploy-bot",
          version: "0.1.0",
          permissions: { network: true },
          tools: ["curl_deploy"],
        }),
      },
    });
    await user.click(screen.getByRole("button", { name: /Validate manifest/i }));
    expect(await within(inspectRegion).findByText(/high/i)).toBeInTheDocument();
    expect(within(inspectRegion).getByText(/Network capability enabled/i)).toBeInTheDocument();

    fireEvent.change(inspectorInput, { target: { value: "{ broken json" } });
    await user.click(screen.getByRole("button", { name: /Validate manifest/i }));
    expect(await within(inspectRegion).findByText("Invalid")).toBeInTheDocument();
  });
});

describe("Screen 09 — SettingsModelsPanel (Models & 4D Hybrid Routing)", () => {
  it("loads OpenCore weights, pauses Allow always rules on active model switch, and fail-closes private prompts to external cloud", async () => {
    const user = userEvent.setup();
    render(<SettingsWorkspace defaultSubSection="permissions" />);

    // First clear initial p-13 -> p-14 drift on Permissions tab so all standing rules are Active
    await user.click(screen.getByRole("button", { name: /Re-confirm all/i }));
    expect(screen.queryByText(/Allow always rules are paused/i)).toBeNull();

    // Navigate to Models & 4D Routing
    const nav = screen.getByRole("navigation", { name: /Settings sections/i });
    await user.click(within(nav).getByRole("button", { name: /Models & 4D Routing/i }));

    expect(
      await screen.findByText("Changing the active model pauses standing Allow always rules until re-confirmed."),
    ).toBeInTheDocument();
    const weightsTable = await screen.findByRole("table", { name: /OpenCore local weights/i });
    expect(within(weightsTable).getByText(/coder-7b/i)).toBeInTheDocument();
    expect(within(weightsTable).getByText(/reasoner-14b/i)).toBeInTheDocument();

    // Connectors card distinguishes public cloud vs self-hosted VPC
    expect(screen.getByText(/Managed Public Cloud · Leaves this machine/i)).toBeInTheDocument();
    expect(screen.getByText("Self-Hosted VPC")).toBeInTheDocument();
    expect(screen.getAllByText(/Not configured · stays local by default/i).length).toBeGreaterThan(0);

    // Switch active model to reasoner-14b -> standing Allow always rules must require re-confirmation
    await user.click(within(weightsTable).getByRole("button", { name: /Set active reasoner-14b/i }));

    // Dry-run 4D Routing: 1) select candidate model + local loopback -> Routed local with 4D tuple
    const modelSelect = screen.getByLabelText(/Candidate model/i);
    await user.selectOptions(modelSelect, "reasoner-14b@1.4.0");
    await user.click(screen.getByRole("button", { name: /Explain 4D route \(\$0\.00 · 0 tokens\)/i }));
    const routeReceipt = await screen.findByTestId("routing-explain-receipt");
    expect(within(routeReceipt).getByText("Routed local")).toBeInTheDocument();
    expect(within(routeReceipt).getByText("License")).toBeInTheDocument();
    expect(within(routeReceipt).getByText("Hosting")).toBeInTheDocument();
    expect(within(routeReceipt).getByText("Operator")).toBeInTheDocument();
    expect(within(routeReceipt).getByText("Data Boundary")).toBeInTheDocument();
    expect(within(routeReceipt).getAllByText("local_loopback").length).toBeGreaterThan(0);

    // Dry-run 4D Routing: 2) privacy="standard" + external cloud endpoint -> Routed cloud
    const privacySelect = screen.getByLabelText(/Privacy classification/i);
    await user.selectOptions(privacySelect, "standard");
    const endpointInput = screen.getByLabelText(/Candidate endpoint/i);
    await user.clear(endpointInput);
    await user.type(endpointInput, "https://api.external-vendor.example/v1");
    await user.click(screen.getByRole("button", { name: /Explain 4D route \(\$0\.00 · 0 tokens\)/i }));
    expect(await within(routeReceipt).findByText("Routed cloud")).toBeInTheDocument();

    // Dry-run 4D Routing: 3) privacy="private" + external cloud endpoint -> Blocked · fail-closed
    await user.selectOptions(privacySelect, "private");
    await user.click(screen.getByRole("button", { name: /Explain 4D route \(\$0\.00 · 0 tokens\)/i }));

    const blockedAlert = await screen.findByRole("alert");
    expect(within(blockedAlert).getByText("Blocked · fail-closed")).toBeInTheDocument();
    expect(within(blockedAlert).getAllByText("external_vendor_api").length).toBeGreaterThan(0);
    expect(within(blockedAlert).getByText(/private data cannot cross external_vendor_api boundary/i)).toBeInTheDocument();

    // Return to Permissions & Manifests and confirm standing rules were paused by the model switch
    await user.click(within(nav).getByRole("button", { name: /Permissions & Manifests/i }));
    expect(await screen.findByText(/2 Allow always rules are paused until you re-confirm them\./i)).toBeInTheDocument();
  });
});

describe("Screen 10 — SettingsGovernancePanel (Governance, Tenant Keys & Spend Caps)", () => {
  it("renders SQLite WAL strip, updates residency & OpenCore fallback policy, and enforces one-time kw_live_* key save gate", async () => {
    const user = userEvent.setup();
    const initialRender = render(<SettingsWorkspace defaultSubSection="governance" />);

    expect(await screen.findByText("SQLite WAL Crash-Safe")).toBeInTheDocument();
    expect(screen.getByText(".keelway/governance.db")).toBeInTheDocument();

    // Update DataResidencyZone -> africa_sovereign
    const residencySelect = await screen.findByLabelText(/Data residency zone/i);
    expect(residencySelect).toHaveValue("local_only");
    await user.selectOptions(residencySelect, "africa_sovereign");
    await waitFor(() => expect(residencySelect).toHaveValue("africa_sovereign"));

    // Daily ($1.42 / $10.00) and Monthly ($18.40 / $150.00) USD spend meters + DLP toggle + OpenCore fallback + SBOM
    expect(screen.getByRole("progressbar", { name: /Daily USD spend/i })).toBeInTheDocument();
    expect(screen.getByText("$1.42 / $10.00")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: /Monthly USD spend/i })).toBeInTheDocument();
    expect(screen.getByText("$18.40 / $150.00")).toBeInTheDocument();
    expect(screen.getByText("keelway-core:7b")).toBeInTheDocument();

    const dlpCheckbox = screen.getByRole("checkbox", { name: /Redact secrets & PII before external egress/i });
    expect(dlpCheckbox).toBeChecked();
    await user.click(dlpCheckbox);
    await waitFor(() => expect(dlpCheckbox).not.toBeChecked());
    const fallbackCheckbox = screen.getByRole("checkbox", {
      name: /Auto-fallback to local OpenCore when budget exceeded/i,
    });
    expect(fallbackCheckbox).toBeChecked();
    await user.click(fallbackCheckbox);
    await waitFor(() => expect(fallbackCheckbox).not.toBeChecked());

    await user.click(screen.getByRole("button", { name: /Inspect SBOM/i }));
    expect(await screen.findByText(/SPDX-2\.3/i)).toBeInTheDocument();

    // Mint scoped kw_live_* key -> One-time reveal modal with soft-locked Done button
    await user.click(screen.getByRole("button", { name: /\+ Mint scoped key/i }));
    const dialog = await screen.findByRole("dialog", { name: /Mint scoped key/i });
    const labelInput = within(dialog).getByLabelText(/Key label/i);
    await user.clear(labelInput);
    await user.type(labelInput, "ci-audit-bot");
    await user.click(within(dialog).getByRole("button", { name: /Generate scoped key/i }));

    const secretCode = await within(dialog).findByTestId("minted-plaintext-secret");
    const mintedToken = secretCode.textContent ?? "";
    expect(mintedToken).toMatch(/^kw_live_/);
    expect(
      within(dialog).getByText(/Keelway stores only its SHA-256 digest and cannot show it again/i),
    ).toBeInTheDocument();

    const doneBtn = within(dialog).getByRole("button", { name: /^Done$/i });
    expect(doneBtn).toHaveAttribute("aria-disabled", "true");
    expect(within(dialog).getByText("Confirm you have saved this key before closing")).toBeInTheDocument();

    // Clicking Done or pressing Escape BEFORE checking "I have saved this key" MUST NOT close modal
    await user.click(doneBtn);
    expect(screen.getByRole("dialog", { name: /Mint scoped key/i })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog", { name: /Mint scoped key/i })).toBeInTheDocument();

    // Checking "I have saved this key" unlocks Done and closes cleanly
    const savedCheckbox = within(dialog).getByRole("checkbox", { name: /I have saved this key/i });
    await user.click(savedCheckbox);
    expect(doneBtn).not.toHaveAttribute("aria-disabled", "true");
    await user.click(doneBtn);
    await waitFor(() => expect(screen.queryByRole("dialog", { name: /Mint scoped key/i })).toBeNull());

    // Prefix-only table now lists ci-audit-bot without plaintext secret + inline Verify key check
    const keysTable = screen.getByRole("table", { name: /Scoped tenant API keys/i });
    expect(within(keysTable).getByText("ci-audit-bot")).toBeInTheDocument();

    const verifyInput = screen.getByLabelText(/Verify scoped key/i);
    await user.type(verifyInput, mintedToken);
    await user.click(screen.getByRole("button", { name: /^Verify key$/i }));
    expect(await screen.findByText("Key valid")).toBeInTheDocument();
    initialRender.unmount();

    // Ephemeral non-WAL warning badge when persistence.healthy === false
    render(
      <SettingsWorkspace
        defaultSubSection="governance"
        fetchPersistenceFn={async () => ({
          engine: "In-Memory",
          journalMode: "MEMORY",
          synchronous: "OFF",
          dbPath: ":memory:",
          walBytes: 0,
          foreignKeys: true,
          healthy: false,
        })}
      />,
    );
    expect(await screen.findByText("Ephemeral memory · not WAL")).toBeInTheDocument();
  });
});

describe("Screen 11 — SettingsSystemPanels (Network, Appearance, Labs, General & Keyboard)", () => {
  it("renders Orla's exact copy, guards Alt+A Air-Gap shortcut when typing in inputs, updates theme/density/RTL, and upgrades Labs from Simulated to Live", async () => {
    const user = userEvent.setup();
    const initialRender = render(<SettingsWorkspace defaultSubSection="network" />);

    expect(
      await screen.findByText("Set to keep your use on this machine. Network use isn't measured yet."),
    ).toBeInTheDocument();
    expect(screen.getByText("No counter yet")).toBeInTheDocument();
    expect((await screen.findAllByText(/NIST SP 800-53 SC-7/i)).length).toBeGreaterThan(0);
    expect(await screen.findByText("SC-7 Verified")).toBeInTheDocument();
    expect(screen.getByText("127.0.0.1:7420")).toBeInTheDocument();

    const airGapBtn = screen.getByRole("button", { name: /Air-Gap Lock/i });
    expect(airGapBtn).toHaveAttribute("aria-pressed", "false");

    // Global Alt+A toggles Air-Gap when focus is NOT in an input
    fireEvent.keyDown(window, { key: "a", code: "KeyA", altKey: true });
    await waitFor(() => expect(airGapBtn).toHaveAttribute("aria-pressed", "true"));

    // Navigate to Permissions, focus the Manifest JSON textarea, and verify Alt+A does NOT toggle Air-Gap
    const nav = screen.getByRole("navigation", { name: /Settings sections/i });
    await user.click(within(nav).getByRole("button", { name: /Permissions & Manifests/i }));
    const manifestBox = screen.getByLabelText(/Manifest JSON \(keelway\.agent\/v1\)/i);
    manifestBox.focus();
    fireEvent.keyDown(manifestBox, { key: "a", code: "KeyA", altKey: true });

    await user.click(within(nav).getByRole("button", { name: /Network & Egress/i }));
    expect((await screen.findByRole("button", { name: /Air-Gap Lock/i }))).toHaveAttribute("aria-pressed", "true");

    // Appearance, Density & Locale updates document.documentElement attributes live
    await user.click(within(nav).getByRole("button", { name: /Appearance & Density/i }));
    await user.click(screen.getByRole("button", { name: /^Light$/i }));
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    await user.click(screen.getByRole("button", { name: /Compact · 24px/i }));
    expect(document.documentElement.getAttribute("data-density")).toBe("compact");
    await user.click(screen.getByRole("button", { name: /Comfortable · 32px/i }));
    expect(document.documentElement.getAttribute("data-density")).toBe("comfortable");

    await user.selectOptions(screen.getByLabelText(/Interface locale/i), "ar");
    expect(document.documentElement.getAttribute("lang")).toBe("ar");
    expect(document.documentElement.getAttribute("dir")).toBe("rtl");

    const reduceMotionBox = screen.getByRole("checkbox", { name: /Reduce motion/i });
    await user.click(reduceMotionBox);
    expect(document.documentElement.getAttribute("data-reduce-motion")).toBe("true");
    const tokensCss = readFileSync("src/styles/tokens.css", "utf8");
    expect(tokensCss).toContain('[data-reduce-motion="true"]');

    // Labs 6-card workbench upgrades Model benchmark & Agent swarm from Simulated (hatched + dashed) to Live (solid)
    await user.click(within(nav).getByRole("button", { name: /^Labs$/i }));
    const benchCard = screen.getByTestId("labs-card-benchmark");
    expect(benchCard).toHaveClass("border-dashed");
    const simBadge = within(benchCard).getByText("Simulated").closest("[data-badge-kind='simulated']");
    expect(simBadge).toHaveClass("kw-badge-simulated");

    expect(screen.getByText("Concept only. Approval rules stay per action, per person.")).toBeInTheDocument();
    expect(screen.getByText("python3 cli.py audit verify")).toBeInTheDocument();

    await user.click(within(benchCard).getByRole("button", { name: /Run local benchmark/i }));
    await waitFor(() => {
      expect(within(benchCard).getByText("Live")).toBeInTheDocument();
      expect(benchCard).not.toHaveClass("border-dashed");
    });

    // General & Keyboard sections render cleanly
    await user.click(within(nav).getByRole("button", { name: /General & Workspace/i }));
    expect(screen.getByRole("button", { name: /Re-open first-run setup/i })).toBeInTheDocument();

    await user.click(within(nav).getByRole("button", { name: /Keyboard Shortcuts/i }));
    expect(screen.getByRole("table", { name: /Keyboard shortcuts reference/i })).toBeInTheDocument();
    initialRender.unmount();

    // Honest SC-7 audit drift badge when fetchAirGapAuditFn reports sc7Compliant === false
    render(
      <SettingsWorkspace
        defaultSubSection="network"
        fetchAirGapAuditFn={async () => ({
          mode: "connected_warning",
          cloudCallsCount: 1,
          bytesSent: null,
          airGapLocked: false,
          endpoints: [],
          sc7Compliant: false,
          sc7Checks: [
            { id: "AIRGAP-01-CREDS", label: "Zero Cloud API Keys in Environment", passed: false, detail: "OPENAI_API_KEY exposed" },
          ],
        })}
      />,
    );
    expect(await screen.findByText("SC-7 Drift · cloud active")).toBeInTheDocument();
    expect(screen.getByText("OPENAI_API_KEY exposed")).toBeInTheDocument();
  });
});

describe("App.tsx Unified Orchestrator & End-to-End Accessibility", () => {
  it("navigates across Tasks -> Files -> Record -> Settings, routes ⌘K CommandPalette while preserving ?token=test-tok, opens Review diff from Record, and passes axe-core WCAG 2.2 AA", async () => {
    const user = userEvent.setup();
    window.history.replaceState({}, "", "/app/?token=test-tok");

    render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    );

    // 1. Starts on Tasks with seeded pending P-10 approval & 0 axe violations
    const rail = screen.getByRole("navigation", { name: /Primary navigation/i });
    expect(within(rail).getByRole("button", { name: /^Tasks$/i })).toHaveAttribute("aria-current", "page");
    expect(await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i })).toBeInTheDocument();
    expect(await runAxe(document.body)).toHaveNoViolations();

    // 2. Open CommandPalette via ⌘K -> jump to core/security/policy.py in Files
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    const paletteInput = await screen.findByRole("combobox", {
      name: /Search commands, tasks, files, symbols, and settings/i,
    });
    await user.type(paletteInput, "policy.py");
    await user.click(await screen.findByRole("option", { name: /policy\.py/i }));

    expect(within(rail).getByRole("button", { name: /^Files$/i })).toHaveAttribute("aria-current", "page");
    expect(await screen.findByRole("textbox", { name: /Code editor for core\/security\/policy\.py/i })).toBeInTheDocument();
    expect(window.location.search).toContain("token=test-tok");
    expect(window.location.search).toContain("section=files");

    // 3. Open CommandPalette -> run "Verify chain" -> switches to Record (0px collapsed sidebar)
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    const paletteInput2 = await screen.findByRole("combobox", {
      name: /Search commands, tasks, files, symbols, and settings/i,
    });
    await user.type(paletteInput2, ">Verify chain");
    await user.click(await screen.findByRole("option", { name: /Verify chain/i }));

    expect(within(rail).getByRole("button", { name: /^Record$/i })).toHaveAttribute("aria-current", "page");
    expect(await screen.findByRole("table", { name: /Record SHA-256 audit ledger/i })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: /Files explorer/i })).toBeNull();
    expect(window.location.search).toContain("token=test-tok");

    // 4. Click "Open diff in Review" on #1283 inspector -> opens Review changes drawer
    const inspector1283 = await screen.findByRole("complementary", { name: /Entry #1283 details/i });
    await user.click(within(inspector1283).getByRole("button", { name: /Open diff in Review/i }));
    const reviewDrawer = await screen.findByRole("complementary", { name: /Review changes/i });
    expect(within(reviewDrawer).getByText("core/main.py")).toBeInTheDocument();

    // 5. Switch to Settings -> Governance -> open Mint scoped key modal + run axe in dark, light, and dir="rtl"
    await user.click(within(rail).getByRole("button", { name: /^Settings$/i }));
    const settingsSidebar = await screen.findByRole("complementary", { name: /Settings navigation/i });
    await user.click(within(settingsSidebar).getByRole("button", { name: /Governance & Keys/i }));
    await user.click(await screen.findByRole("button", { name: /\+ Mint scoped key/i }));
    await screen.findByRole("dialog", { name: /Mint scoped key/i });
    expect(await runAxe(document.body)).toHaveNoViolations();

    document.documentElement.setAttribute("data-theme", "light");
    expect(await runAxe(document.body)).toHaveNoViolations();

    document.documentElement.setAttribute("dir", "rtl");
    expect(await runAxe(document.body)).toHaveNoViolations();
  });

  it("supports URL deep-links (?section=settings&settings=labs&onboarding=1), ⌘K Needs-approval task focus jump, and WebSocket cleanup", async () => {
    const user = userEvent.setup();
    const closeSpy = vi.fn();
    const wsHolder: { onMessage: ((ev: MessageEvent) => void) | null } = { onMessage: null };
    class MockWs {
      static OPEN = 1;
      static CONNECTING = 0;
      readyState = 1;
      onopen: (() => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;
      set onmessage(fn: ((ev: MessageEvent) => void) | null) {
        wsHolder.onMessage = fn;
      }
      close = closeSpy;
    }
    vi.stubGlobal("WebSocket", MockWs);

    try {
      window.history.replaceState({}, "", "/app/?token=ws-tok&section=settings&settings=labs&onboarding=1");
      const { unmount } = render(<App />);

      // Onboarding modal opens from ?onboarding=1
      const onboardingDialog = await screen.findByRole("dialog", { name: /Welcome to Keelway/i });
      await user.click(within(onboardingDialog).getByRole("button", { name: /Continue to workspace check/i }));
      await user.click(within(onboardingDialog).getByRole("button", { name: /Start using Keelway/i }));
      await waitFor(() => expect(screen.queryByRole("dialog", { name: /Workspace & Local System/i })).toBeNull());

      // Landed on Settings -> Labs; run swarm eval to upgrade Agent swarm (MiroFish) to Live
      const swarmCard = screen.getByTestId("labs-card-swarm");
      expect(swarmCard).toHaveClass("border-dashed");
      await user.click(within(swarmCard).getByRole("button", { name: /Run swarm eval/i }));
      await waitFor(() => expect(within(swarmCard).getByText("Live")).toBeInTheDocument());

      // Live WebSocket event updates Record #seq in status bar
      expect(wsHolder.onMessage).not.toBeNull();
      act(() => {
        wsHolder.onMessage?.(
          new MessageEvent("message", {
            data: JSON.stringify({ type: "audit.append", payload: { seq: 1290 }, timestamp: "2026-11-14T03:00:00Z" }),
          }),
        );
      });
      expect(await screen.findByText("Record #1290")).toBeInTheDocument();

      // Open ⌘K CommandPalette and select the Needs approval task -> navigates to Tasks & focuses P-10 heading without approving
      fireEvent.keyDown(window, { key: "k", metaKey: true });
      const combo = await screen.findByRole("combobox", {
        name: /Search commands, tasks, files, symbols, and settings/i,
      });
      await user.type(combo, "#Harden loopback CSP");
      await user.click(await screen.findByRole("option", { name: /Harden loopback CSP/i }));

      const p10Heading = await screen.findByRole("heading", { name: /Run pytest Studio CSP suite/i });
      await waitFor(() => expect(document.activeElement).toBe(p10Heading));
      expect(window.location.search).toContain("token=ws-tok");

      unmount();
      expect(closeSpy).toHaveBeenCalledTimes(1);

      // Mobile Companion (?companion=1): tapping "Status" renders SettingsSubNav so all 8 sections remain reachable
      window.history.replaceState({}, "", "/app/?token=ws-tok&companion=1");
      const companionRender = render(<App />);
      const companionBar = screen.getByRole("navigation", { name: /Companion navigation/i });
      await user.click(within(companionBar).getByRole("button", { name: /^Status$/i }));
      const mobileSettingsNav = await screen.findByRole("navigation", { name: /Settings sections/i });
      await user.click(within(mobileSettingsNav).getByRole("button", { name: /Network & Egress/i }));
      expect(
        await screen.findByText("Set to keep your use on this machine. Network use isn't measured yet."),
      ).toBeInTheDocument();
      companionRender.unmount();
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
