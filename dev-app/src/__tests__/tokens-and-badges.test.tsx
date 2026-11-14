import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SemanticBadge, type SemanticBadgeKind } from "@/components/ui/SemanticBadge";
import { Button } from "@/components/ui/Button";
import { CalloutBanner } from "@/components/ui/CalloutBanner";
import { explainRouting, fetchAirGapAudit, fetchSystemDoctor } from "@/lib/api";
import { isTrustedUserEvent } from "@/lib/types";
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
});
