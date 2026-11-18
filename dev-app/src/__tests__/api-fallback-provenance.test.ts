import { describe, expect, it, vi } from "vitest";
import { fetchGovernancePolicy, subscribeDataFallbacks } from "@/lib/api";

describe("data fallback provenance", () => {
  it("notifies subscribers when a response falls back to bundled data", async () => {
    const listener = vi.fn();
    const unsubscribe = subscribeDataFallbacks(listener);
    try {
      listener.mockClear();
      await fetchGovernancePolicy();
      expect(listener).toHaveBeenCalled();
      const lastCount = listener.mock.calls.at(-1)?.[0] as number;
      expect(lastCount).toBeGreaterThan(0);
    } finally {
      unsubscribe();
    }
  });

  it("stops notifying after unsubscribe", async () => {
    const listener = vi.fn();
    const unsubscribe = subscribeDataFallbacks(listener);
    unsubscribe();
    listener.mockClear();
    await fetchGovernancePolicy();
    expect(listener).not.toHaveBeenCalled();
  });
});
