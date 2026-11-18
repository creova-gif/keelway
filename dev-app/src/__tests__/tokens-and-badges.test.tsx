import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import {
  connectStudioWebSocket,
  createGitCommit,
  explainRouting,
  exportAuditBundle,
  fetchAgentManifests,
  fetchAirGapAudit,
  fetchFilesTree,
  fetchGitProposal,
  fetchSystemDoctor,
  inspectAgentManifest,
  mintScopedKey,
} from "@/lib/api";
import { decodeAirGapAudit } from "@/lib/apiDecoders";
import { isTrustedUserEvent, type StudioWsEvent } from "@/lib/types";
import { runAxe } from "@/test/setup";
import "@/styles/tokens.css";

describe("Tokens Rev 4 — SemanticBadge, Button & CalloutBanner primitives", () => {
  it("distinguishes neutral Ready from verified Passed (never green on Ready)", () => {
    const { rerender } = render(<SemanticBadge kind="ready" />);
    const readyBadge = screen.getByText("Ready").closest("[data-badge-kind='ready']");
    expect(readyBadge).not.toBeNull();
    expect(readyBadge).toHaveClass("text-fg-muted");
    expect(readyBadge).not.toHaveClass("text-ok");

    rerender(<SemanticBadge kind="passed" />);
    const passedBadge = screen.getByText("Passed").closest("[data-badge-kind='passed']");
    expect(passedBadge).not.toBeNull();
    expect(passedBadge).toHaveClass("text-ok");
    expect(passedBadge).toHaveTextContent("✓");
  });

  it("renders hatched Simulated badge and honest 'No counter yet' unmeasured badge", () => {
    const { rerender } = render(<SemanticBadge kind="simulated" />);
    const simulatedBadge = screen.getByText("Simulated").closest("[data-badge-kind='simulated']");
    expect(simulatedBadge).not.toBeNull();
    expect(simulatedBadge).toHaveClass("kw-badge-simulated");

    rerender(<SemanticBadge kind="unmeasured" />);
    const unmeasuredBadge = screen
      .getByText("No counter yet")
      .closest("[data-badge-kind='unmeasured']");
    expect(unmeasuredBadge).not.toBeNull();
  });

  it("reserves text-ochre strictly for Needs approval and uses text-warning for Re-confirm and Not saved", () => {
    render(
      <div>
        <SemanticBadge kind="needs-approval" />
        <SemanticBadge kind="reconfirm" />
        <SemanticBadge kind="not-saved" detail="disk full" />
      </div>,
    );

    const approvalBadge = screen
      .getByText("Needs approval")
      .closest("[data-badge-kind='needs-approval']");
    expect(approvalBadge).not.toBeNull();
    expect(approvalBadge).toHaveClass("text-ochre");
    expect(approvalBadge).not.toHaveClass("text-warning");

    const reconfirmBadge = screen
      .getByText("Re-confirm")
      .closest("[data-badge-kind='reconfirm']");
    expect(reconfirmBadge).not.toBeNull();
    expect(reconfirmBadge).toHaveClass("text-warning");
    expect(reconfirmBadge).not.toHaveClass("text-ochre");

    const notSavedBadge = screen
      .getByText("Not saved · disk full")
      .closest("[data-badge-kind='not-saved']");
    expect(notSavedBadge).not.toBeNull();
    expect(notSavedBadge).toHaveClass("text-warning");
    expect(notSavedBadge).not.toHaveClass("text-ochre");
  });

  it("renders all 18 canonical SemanticBadge kinds with non-color glyphs and visible labels", () => {
    const allKinds: SemanticBadgeKind[] = [
      "needs-approval",
      "running",
      "queued",
      "done",
      "ready",
      "passed",
      "failed",
      "reconfirm",
      "not-saved",
      "live",
      "estimated",
      "simulated",
      "prototype",
      "unmeasured",
      "ai",
      "opencore",
      "frontier",
      "locked",
    ];

    const { container } = render(
      <div>
        {allKinds.map((kind) => (
          <SemanticBadge key={kind} kind={kind} />
        ))}
      </div>,
    );

    for (const kind of allKinds) {
      const el = container.querySelector(`[data-badge-kind="${kind}"]`);
      expect(el).not.toBeNull();
      const glyph = el?.querySelector("[data-badge-glyph]");
      expect(glyph).not.toBeNull();
      expect((el?.textContent ?? "").trim().length).toBeGreaterThan(1);
    }
  });

  it("enforces clickOnly on Button: omits <kbd> shortcutHint, blocks untrusted synthetic events, and enforces native isTrusted in production", async () => {
    const user = userEvent.setup();
    const onApprove = vi.fn();

    const { container, rerender } = render(
      <Button variant="warning-cta" clickOnly shortcutHint="⌘⇧Y" onClick={onApprove}>
        Allow once
      </Button>,
    );

    // clickOnly must omit <kbd> shortcut hints
    expect(container.querySelector("kbd")).toBeNull();

    const button = screen.getByRole("button", { name: "Allow once" });

    // Untrusted synthetic script injection must be rejected
    const injectedClick = Object.assign(new MouseEvent("click", { bubbles: true, cancelable: true }), {
      __kwUntrustedSynthetic: true,
    });
    button.dispatchEvent(injectedClick);
    expect(onApprove).not.toHaveBeenCalled();

    // Production mode strictly enforces native event.isTrusted === true
    const rawSyntheticEvent = new MouseEvent("click", { bubbles: true });
    expect(rawSyntheticEvent.isTrusted).toBe(false);
    expect(isTrustedUserEvent(rawSyntheticEvent, "production")).toBe(false);
    expect(isTrustedUserEvent(injectedClick, "test")).toBe(false);

    // Trusted user interaction in test environment fires cleanly
    await user.click(button);
    expect(onApprove).toHaveBeenCalledTimes(1);

    // Non-clickOnly Button renders <kbd> shortcut hint and supports previewLocked aria-disabled
    const onLockedClick = vi.fn();
    rerender(
      <div>
        <span id="lock-msg">Generating diff preview…</span>
        <Button
          variant="primary"
          shortcutHint="⌘⇧Y"
          previewLocked
          lockReasonId="lock-msg"
          onClick={onLockedClick}
        >
          Allow with preview
        </Button>
      </div>,
    );

    const lockedBtn = screen.getByRole("button", { name: /Allow with preview/i });
    expect(container.querySelector("kbd")).toHaveTextContent("⌘⇧Y");
    expect(lockedBtn).toHaveAttribute("aria-disabled", "true");
    expect(lockedBtn).toHaveAttribute("aria-describedby", "lock-msg");
    fireEvent.click(lockedBtn);
    expect(onLockedClick).not.toHaveBeenCalled();

    // Direct aria-disabled="true" prop must not be overwritten and must suppress onClick
    const onDirectAriaDisabledClick = vi.fn();
    rerender(
      <Button variant="secondary" aria-disabled="true" onClick={onDirectAriaDisabledClick}>
        Caller soft-disabled
      </Button>,
    );
    const directSoftDisabledBtn = screen.getByRole("button", { name: "Caller soft-disabled" });
    expect(directSoftDisabledBtn).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(directSoftDisabledBtn);
    expect(onDirectAriaDisabledClick).not.toHaveBeenCalled();
  });

  it("renders persistent CalloutBanner variants (status vs alert) with zero auto-dismiss timers", () => {
    vi.useFakeTimers();
    try {
      const onReconfirm = vi.fn();
      const onInspectBroken = vi.fn();

      render(
        <div>
          <CalloutBanner
            variant="prompt-drift"
            title="Prompt version changed: p-13 → p-14"
            description="2 scoped rules paused until you review the updated system prompt."
            safeStateNote="Safe default: paused rules fall back to Ask every time."
            actions={
              <Button size="sm" variant="secondary" onClick={onReconfirm}>
                Re-confirm rules
              </Button>
            }
          />
          <CalloutBanner
            variant="chain-broken"
            title="Chain broken at entry #1279"
            description="SHA-256 prev_hash mismatch detected in local audit database."
            safeStateNote="Exports mark chain integrity as failed until investigated."
            actions={
              <Button size="sm" variant="danger" onClick={onInspectBroken}>
                Open entry #1279
              </Button>
            }
          />
        </div>,
      );

      const driftBanner = screen.getByRole("status");
      expect(driftBanner).toHaveTextContent("Prompt version changed: p-13 → p-14");

      const brokenBanner = screen.getByRole("alert");
      expect(brokenBanner).toHaveTextContent("Chain broken at entry #1279");

      // Advance 60 seconds — banners must NEVER auto-dismiss
      vi.advanceTimersByTime(60_000);
      expect(screen.getByRole("status")).toBeInTheDocument();
      expect(screen.getByRole("alert")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Re-confirm rules" }));
      fireEvent.click(screen.getByRole("button", { name: "Open entry #1279" }));
      expect(onReconfirm).toHaveBeenCalledTimes(1);
      expect(onInspectBroken).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("passes WCAG 2.2 AA axe-core checks across dark/light themes and density modes", async () => {
    for (const theme of ["dark", "light"] as const) {
      for (const density of ["compact", "default", "comfortable"] as const) {
        document.documentElement.setAttribute("data-theme", theme);
        document.documentElement.setAttribute("data-density", density);

        const { container, unmount } = render(
          <main aria-label={`Primitives ${theme} ${density}`}>
            <SemanticBadge kind="needs-approval" />
            <SemanticBadge kind="ready" />
            <SemanticBadge kind="passed" />
            <SemanticBadge kind="simulated" />
            <SemanticBadge kind="not-saved" detail="disk full" />
            <Button variant="primary" shortcutHint="⌘↵">
              Run task
            </Button>
            <Button variant="warning-cta" clickOnly>
              Allow once
            </Button>
            <CalloutBanner
              variant="runtime-unreachable"
              title="Local runtime unreachable"
              description="Loopback daemon on 127.0.0.1:7420 did not respond."
              actions={<Button size="sm">Retry connection</Button>}
            />
          </main>,
        );

        const results = await runAxe(container);
        expect(results).toHaveNoViolations();
        unmount();
      }
    }
  });

  it("attaches ?token= loopback headers on /v1/* requests and falls back cleanly with honest defaults", async () => {
    // Honest fallback snapshot when backend is offline
    const airgap = await fetchAirGapAudit();
    expect(airgap.mode).toBe("unmeasured");
    expect(airgap.bytesSent).toBeNull();

    // Fail-closed 4D routing dry-run fallback
    const blocked = await explainRouting({
      taskKind: "code_edit",
      privacy: "private",
      maxLatencyMs: 800,
      maxCostUsd: 0.05,
      candidateEndpoint: "https://api.external-vendor.example/v1",
    });
    expect(blocked.allowed).toBe(false);
    expect(blocked.decision).toBe("blocked_fail_closed");
    expect(blocked.dataBoundary).toBe("external_vendor_api");

    // Loopback ?token= header propagation when fetch is mocked
    const originalLocation = window.location.href;
    window.history.replaceState({}, "", "/app/?token=kw_session_test_token");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify([
          { id: "sandbox", label: "Seatbelt", status: "ok", detail: "Active" },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    try {
      const checks = await fetchSystemDoctor();
      expect(checks).toHaveLength(1);
      expect(fetchSpy).toHaveBeenCalledTimes(1);
      const [calledPath, calledInit] = fetchSpy.mock.calls[0];
      expect(calledPath).toBe("/v1/system/doctor");
      const headers = new Headers(calledInit?.headers);
      expect(headers.get("X-Studio-Token")).toBe("kw_session_test_token");
      expect(headers.get("Authorization")).toBe("Bearer kw_session_test_token");
    } finally {
      fetchSpy.mockRestore();
      window.history.replaceState({}, "", originalLocation);
    }
  });

  it("normalizes live FastAPI envelopes, snake_case payloads, NDJSON audit exports, and flat WebSocket frames", async () => {
    // Invalid manifest JSON fails fast locally without needing a network round-trip
    const badManifest = await inspectAgentManifest("{invalid json");
    expect(badManifest.valid).toBe(false);
    expect(badManifest.errors[0]).toMatch(/Invalid JSON/i);

    const fetchSpy = vi.spyOn(globalThis, "fetch");
    try {
      // 1. fetchFilesTree root directory object envelope
      fetchSpy.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            name: "keelway",
            path: ".",
            type: "directory",
            children: [
              { name: "cli.py", path: "cli.py", type: "file", git_status: "M" },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
      const tree = await fetchFilesTree();
      expect(tree).toHaveLength(1);
      expect(tree[0]).toMatchObject({
        name: "cli.py",
        path: "cli.py",
        type: "file",
        language: "python",
        gitStatus: "M",
      });

      // 2. fetchAgentManifests { manifests, count, signing_key_present } envelope
      fetchSpy.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            count: 1,
            signing_key_present: true,
            manifests: [
              {
                id: "sec-scanner@2.0.0",
                name: "sec-scanner",
                version: "2.0.0",
                description: "Scans workspace dependencies",
                enabled: true,
                signature_status: "valid",
                governance_summary: { tools: ["read_file", "scan_sbom"], network: "none", max_tier: 1 },
                canonical_json: '{"name":"sec-scanner"}',
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
      const manifests = await fetchAgentManifests();
      expect(manifests).toHaveLength(1);
      expect(manifests[0]).toMatchObject({
        id: "sec-scanner@2.0.0",
        signatureStatus: "verified",
        networkAllowed: false,
        maxTier: 1,
        tools: ["read_file", "scan_sbom"],
      });

      // 3. exportAuditBundle plain-text application/x-ndjson response
      const ndjsonBody = [
        JSON.stringify({
          seq: 10,
          timestamp: "2026-11-14T02:00:00Z",
          actor: "alice",
          role: "engineer",
          action: "workspace_open",
          resource: "/repo",
          allowed: true,
          entry_hash: "abc123hash",
        }),
        JSON.stringify({
          seq: 11,
          timestamp: "2026-11-14T02:01:00Z",
          actor: "4d-router",
          role: "policy",
          action: "egress_blocked",
          resource: "https://cloud.example",
          allowed: false,
          entry_hash: "def456hash",
        }),
      ].join("\n");
      fetchSpy.mockResolvedValueOnce(
        new Response(ndjsonBody, {
          status: 200,
          headers: { "Content-Type": "application/x-ndjson; charset=utf-8" },
        }),
      );
      const bundle = await exportAuditBundle();
      expect(bundle.jsonl).toContain("abc123hash");
      expect(bundle.csv).toContain("workspace_open");
      expect(bundle.csv).toContain("egress_blocked");

      // 4. explainRouting snake_case FastAPI response
      fetchSpy.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            decision_id: "rdec_123456",
            requested_model: "llama-3.3-70b",
            selected_provider: null,
            fallback_chain: [],
            reason: "private: blocked because data_boundary=external_vendor_api",
            governance_provenance: { data_boundary: "external_vendor_api" },
            estimated_cost_usd: 0,
            privacy_level: "private",
            privacy_compliant: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
      const routeExplanation = await explainRouting({
        taskKind: "refactor auth",
        privacy: "private",
        maxLatencyMs: 500,
        maxCostUsd: 0.02,
        candidateEndpoint: "https://openweight.vendor.example/v1",
      });
      expect(routeExplanation.allowed).toBe(false);
      expect(routeExplanation.decision).toBe("blocked_fail_closed");
      expect(routeExplanation.dataBoundary).toBe("external_vendor_api");
      expect(Array.isArray(routeExplanation.evaluatedCandidates)).toBe(true);
      expect(routeExplanation.evaluatedCandidates.length).toBeGreaterThan(0);

      // 5. mintScopedKey + fetchGitProposal + createGitCommit snake_case FastAPI responses
      fetchSpy.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            key_id: "key_live_01",
            tenant_id: "default",
            name: "ci-runner",
            key_prefix: "kw_live_0011",
            scopes: ["audit:read"],
            created_at: "2026-11-14T02:30:00Z",
            revoked: false,
            api_key: "kw_live_001122_secretvalue",
          }),
          { status: 201, headers: { "Content-Type": "application/json" } },
        ),
      );
      const minted = await mintScopedKey("ci-runner", ["audit:read"], 25);
      expect(minted.plaintextSecret).toBe("kw_live_001122_secretvalue");
      expect(minted.key.id).toBe("key_live_01");
      expect(minted.key.prefix).toBe("kw_live_0011");

      fetchSpy.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            clean: false,
            branch: "feat/unified-dev-app",
            files_count: 1,
            files: [{ path: "core/main.py", status: "M" }],
            proposed_title: "feat(core): update 1 file(s)",
            proposed_message: "feat(core): update 1 file(s)\n\n- [M] core/main.py",
            patch_hash: "deadbeef",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
      const proposal = await fetchGitProposal();
      expect(proposal.filesCount).toBe(1);
      expect(proposal.proposedTitle).toBe("feat(core): update 1 file(s)");

      fetchSpy.mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "committed",
            commit_sha: "abcdef1234567890",
            branch: "feat/unified-dev-app",
            message: "feat(core): update 1 file(s)",
            author: "Dev <dev@keelway.local>",
            clean: true,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
      const commitRes = await createGitCommit("feat(core): update 1 file(s)");
      expect(commitRes.ok).toBe(true);
      expect(commitRes.commitSha).toBe("abcdef1234567890");
    } finally {
      fetchSpy.mockRestore();
    }

    // 6. connectStudioWebSocket preserves flat FastAPI frames and cleans up handlers on close()
    const receivedEvents: StudioWsEvent[] = [];
    let createdSocket: {
      url: string;
      readyState: number;
      onopen: ((ev: Event) => void) | null;
      onmessage: ((ev: MessageEvent) => void) | null;
      onerror: ((ev: Event) => void) | null;
      onclose: ((ev: CloseEvent) => void) | null;
      close: ReturnType<typeof vi.fn>;
    } | null = null;

    class MockStudioWebSocket {
      static OPEN = 1;
      static CONNECTING = 0;
      url: string;
      readyState = 1;
      onopen: ((ev: Event) => void) | null = null;
      onmessage: ((ev: MessageEvent) => void) | null = null;
      onerror: ((ev: Event) => void) | null = null;
      onclose: ((ev: CloseEvent) => void) | null = null;
      close = vi.fn();
      constructor(url: string) {
        this.url = url;
        createdSocket = this;
      }
    }

    const originalWs = globalThis.WebSocket;
    globalThis.WebSocket = MockStudioWebSocket as unknown as typeof WebSocket;
    try {
      const handle = connectStudioWebSocket((ev) => receivedEvents.push(ev));
      expect(createdSocket).not.toBeNull();
      createdSocket!.onmessage?.(
        new MessageEvent("message", {
          data: JSON.stringify({
            type: "air_gap_status_changed",
            air_gapped: true,
            timestamp: "2026-11-14T02:35:00Z",
          }),
        }),
      );
      expect(receivedEvents).toHaveLength(1);
      expect(receivedEvents[0]).toEqual({
        type: "air_gap_status_changed",
        payload: { air_gapped: true },
        timestamp: "2026-11-14T02:35:00Z",
      });

      handle.close();
      expect(createdSocket!.onmessage).toBeNull();
      expect(createdSocket!.close).toHaveBeenCalledTimes(1);
    } finally {
      globalThis.WebSocket = originalWs;
    }
  });

  it("fail-closes decodeAirGapAudit on camelCase overallCompliant=false, unspecified check rows, and omitted mode with egressBytes", () => {
    const camelFalse = decodeAirGapAudit({
      overallCompliant: false,
      checks: [{ id: "SC7-UNSPECIFIED", name: "Loopback check without passed boolean" }],
    });
    expect(camelFalse?.sc7Compliant).toBe(false);
    expect(camelFalse?.sc7Checks?.[0]?.passed).toBe(false);

    const omittedCompliance = decodeAirGapAudit({});
    expect(omittedCompliance).not.toBeNull();
    expect(omittedCompliance?.sc7Compliant).toBeUndefined();
    expect(omittedCompliance?.mode).toBe("unmeasured");
    expect(omittedCompliance?.bytesSent).toBeNull();

    const measuredZero = decodeAirGapAudit({ egressBytes: 0, overallCompliant: true });
    expect(measuredZero?.sc7Compliant).toBe(true);
    expect(measuredZero?.bytesSent).toBe(0);
    expect(measuredZero?.mode).toBe("measured_offline");

    const connectedSnake = decodeAirGapAudit({
      egress_bytes: 4096,
      cloud_calls_count: 1,
      endpoints: [{ host: "api.vendor.example", egress_bytes: 4096, calls: 1 }],
    });
    expect(connectedSnake?.bytesSent).toBe(4096);
    expect(connectedSnake?.mode).toBe("connected_warning");
    expect(connectedSnake?.endpoints[0]?.bytesSent).toBe(4096);

    const airGapLocked = decodeAirGapAudit({ air_gapped: true, egressBytes: 0 });
    expect(airGapLocked?.airGapLocked).toBe(true);
    expect(airGapLocked?.mode).toBe("air_gapped_verified");
  });
});
