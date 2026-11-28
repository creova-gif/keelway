import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/dom";
import axeCore, { type AxeResults, type RunOptions } from "axe-core";
import { afterEach, expect } from "vitest";
import { resetApiFallbackState } from "@/lib/apiFallbacks";

// View chunks are React.lazy code-splits; the import + hydration legitimately
// exceeds the 1s asyncUtilTimeout default under parallel test load.
configure({ asyncUtilTimeout: 4000 });

afterEach(() => {
  resetApiFallbackState();
  if (typeof window !== "undefined" && window.history?.replaceState) {
    try {
      window.history.replaceState({}, "", "/");
    } catch {
      // Ignore history errors in constrained environments
    }
  }
  if (typeof document !== "undefined") {
    document.documentElement.setAttribute("data-theme", "dark");
    document.documentElement.setAttribute("data-density", "default");
    document.documentElement.removeAttribute("data-reduce-motion");
    document.documentElement.setAttribute("dir", "ltr");
    document.documentElement.setAttribute("lang", "en");
  }
});

class ResizeObserverMock {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
}

if (typeof window !== "undefined") {
  if (typeof HTMLCanvasElement !== "undefined") {
    HTMLCanvasElement.prototype.getContext = (() =>
      null) as unknown as typeof HTMLCanvasElement.prototype.getContext;
  }

  if (!window.matchMedia) {
    Object.defineProperty(window, "matchMedia", {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
    });
  }

  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = function scrollIntoViewMock(): void {};
  }
}

export async function runAxe(
  container: Element | Document = document.body,
  options?: RunOptions,
): Promise<AxeResults> {
  return axeCore.run(container, {
    ...options,
    rules: {
      "color-contrast": { enabled: false },
      ...(options?.rules ?? {}),
    },
  });
}

export const axe = runAxe;

function formatViolations(results: AxeResults): string {
  if (!results.violations.length) {
    return "No accessibility violations detected.";
  }
  return results.violations
    .map((v) => {
      const targets = v.nodes.map((n) => n.target.join(", ")).join(" | ");
      return `[${v.impact ?? "unknown"}] ${v.id}: ${v.help} (${targets})`;
    })
    .join("\n");
}

expect.extend({
  toHaveNoViolations(received: AxeResults) {
    const pass = Array.isArray(received?.violations) && received.violations.length === 0;
    return {
      pass,
      message: () =>
        pass
          ? "Expected accessibility violations, but found none."
          : `Expected zero axe accessibility violations, found ${received?.violations?.length ?? 0}:\n${formatViolations(received)}`,
    };
  },
});

declare module "vitest" {
  interface Assertion<T> {
    toHaveNoViolations(): T;
  }
  interface AsymmetricMatchersContaining {
    toHaveNoViolations(): void;
  }
}
