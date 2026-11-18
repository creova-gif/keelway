import React from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OnboardingModal } from "@/components/shell/OnboardingModal";
import type { DoctorCheckItem } from "@/lib/types";
import { runAxe } from "@/test/setup";
import "@/styles/tokens.css";

describe("OnboardingModal — 2-Step Sovereign Setup & Lifecycle Polish", () => {
  it("renders Honest Defaults (Step 1), Workspace + System Doctor checks (Step 2), and passes opened branch to onComplete", async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn();
    const openWorkspaceSpy = vi
      .fn()
      .mockRejectedValueOnce(new Error("Directory does not exist"))
      .mockResolvedValueOnce({
        ok: true,
        path: "/Users/dev/keelway-repo",
        branch: "feat/custom-branch",
        filesCount: 64,
      });

    const initialChecks: DoctorCheckItem[] = [
      {
        id: "sandbox-isolation",
        label: "OS Sandbox Isolation (Seatbelt / Bubblewrap)",
        status: "ok",
        detail: "Seatbelt profile active",
      },
      {
        id: "opencore-weights",
        label: "Local OpenCore Runtime (coder-7b v2.5.1)",
        status: "warning",
        detail: "Model cached on disk, warm-up pending",
        remediation: "Run `keelway opencore warmup` to preload weights into memory.",
      },
      {
        id: "audit-sqlite-wal",
        label: "Append-Only Audit Ledger (SQLite WAL)",
        status: "failed",
        detail: "Write lock held by stale PID",
        remediation: "Remove stale `.keelway/audit.db-shm` or restart local daemon.",
      },
    ];

    const rerunChecks: DoctorCheckItem[] = initialChecks.map((c) => ({
      ...c,
      status: "ok",
      detail: "Verified healthy",
      remediation: undefined,
    }));

    const fetchDoctorSpy = vi
      .fn<() => Promise<DoctorCheckItem[]>>()
      .mockResolvedValueOnce(initialChecks)
      .mockResolvedValueOnce(rerunChecks);

    render(
      <OnboardingModal
        open={true}
        onComplete={onComplete}
        defaultWorkspacePath="/Users/dev/keelway"
        openWorkspaceFn={openWorkspaceSpy}
        fetchDoctorFn={fetchDoctorSpy}
      />,
    );

    const dialog = screen.getByRole("dialog");

    // Step 1: 3 transparent sovereign default cards
    expect(within(dialog).getByText(/Local ·/i)).toBeInTheDocument();
    expect(within(dialog).getByText("coder-7b v2.5.1")).toBeInTheDocument();
    expect(within(dialog).getByText(/Runs on this machine via OpenCore/i)).toBeInTheDocument();

    expect(within(dialog).getByText("Ask every time")).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        /Only a person, at this keyboard, can approve edits, commands, or network calls/i,
      ),
    ).toBeInTheDocument();

    expect(within(dialog).getByText("Offline (setting)")).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        "Set to keep your use on this machine. Network use isn't measured yet.",
      ),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("No counter yet")).toBeInTheDocument();

    // Advance to Step 2
    await user.click(within(dialog).getByRole("button", { name: "Continue to workspace check" }));

    expect(fetchDoctorSpy).toHaveBeenCalledTimes(1);
    expect(await within(dialog).findByText("Seatbelt profile active")).toBeInTheDocument();

    // Verify non-color badges (Passed, Warning, Failed) and remediation text
    expect(within(dialog).getByText("Passed")).toBeInTheDocument();
    expect(within(dialog).getByText("Warning")).toBeInTheDocument();
    expect(within(dialog).getByText("Failed")).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Run `keelway opencore warmup` to preload weights/i),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Remove stale `\.keelway\/audit\.db-shm`/i),
    ).toBeInTheDocument();

    // Open workspace (handles rejected promise cleanly, then succeeds on retry)
    const wsInput = within(dialog).getByLabelText(/Workspace/i);
    await user.clear(wsInput);
    await user.type(wsInput, "/Users/dev/missing-repo");
    await user.click(within(dialog).getByRole("button", { name: "Open workspace" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Directory does not exist");

    await user.clear(wsInput);
    await user.type(wsInput, "/Users/dev/keelway-repo");
    await user.click(within(dialog).getByRole("button", { name: "Open workspace" }));
    expect(openWorkspaceSpy).toHaveBeenCalledWith("/Users/dev/keelway-repo");
    expect(await within(dialog).findByText("feat/custom-branch")).toBeInTheDocument();

    // Re-run doctor
    await user.click(within(dialog).getByRole("button", { name: "Re-run doctor" }));
    expect(fetchDoctorSpy).toHaveBeenCalledTimes(2);
    expect(await within(dialog).findAllByText("Passed")).toHaveLength(3);

    // Complete onboarding -> includes branch from openedWorkspaceInfo
    await user.click(within(dialog).getByRole("button", { name: "Start using Keelway" }));
    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledWith(
      expect.objectContaining({
        workspacePath: "/Users/dev/keelway-repo",
        branch: "feat/custom-branch",
      }),
    );
  });

  it("resets step back to 1 when reopened (false -> true) and closes cleanly on 'Change in Settings later'", async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onOpenSettingsLater = vi.fn();
    const fetchDoctorSpy = vi.fn<() => Promise<DoctorCheckItem[]>>().mockResolvedValue([]);

    const { rerender } = render(
      <OnboardingModal
        open={true}
        onOpenChange={onOpenChange}
        onOpenSettingsLater={onOpenSettingsLater}
        onComplete={() => {}}
        fetchDoctorFn={fetchDoctorSpy}
      />,
    );

    // Advance to Step 2, then close (open=false) and reopen (open=true) -> must reset to Step 1
    await user.click(screen.getByRole("button", { name: "Continue to workspace check" }));
    expect(screen.getByRole("dialog", { name: /Workspace & Local System/i })).toBeInTheDocument();

    rerender(
      <OnboardingModal
        open={false}
        onOpenChange={onOpenChange}
        onOpenSettingsLater={onOpenSettingsLater}
        onComplete={() => {}}
        fetchDoctorFn={fetchDoctorSpy}
      />,
    );
    rerender(
      <OnboardingModal
        open={true}
        onOpenChange={onOpenChange}
        onOpenSettingsLater={onOpenSettingsLater}
        onComplete={() => {}}
        fetchDoctorFn={fetchDoctorSpy}
      />,
    );

    const step1Dialog = screen.getByRole("dialog", { name: /Welcome to Keelway/i });
    expect(step1Dialog).toBeInTheDocument();

    // Clicking "Change in Settings later" closes without advancing to Step 2 or running doctor
    fetchDoctorSpy.mockClear();
    await user.click(within(step1Dialog).getByRole("button", { name: "Change in Settings later" }));
    expect(onOpenSettingsLater).toHaveBeenCalledTimes(1);
    expect(onOpenChange).toHaveBeenCalledWith(false);
    expect(fetchDoctorSpy).not.toHaveBeenCalled();
  });

  it("passes WCAG 2.2 AA axe-core checks across Step 1 and Step 2 in Dark, Light, and RTL modes", async () => {
    try {
      for (const theme of ["dark", "light"] as const) {
        for (const dir of ["ltr", "rtl"] as const) {
          document.documentElement.setAttribute("data-theme", theme);
          document.documentElement.setAttribute("dir", dir);

          const step1 = render(<OnboardingModal open={true} initialStep={1} onComplete={() => {}} />);
          expect(await runAxe(document.body)).toHaveNoViolations();
          step1.unmount();

          const step2 = render(<OnboardingModal open={true} initialStep={2} onComplete={() => {}} />);
          await screen.findByText(/OS Sandbox Isolation/i);
          expect(await runAxe(document.body)).toHaveNoViolations();
          step2.unmount();
        }
      }
    } finally {
      document.documentElement.setAttribute("dir", "ltr");
      document.documentElement.setAttribute("data-theme", "dark");
    }
  });
});
