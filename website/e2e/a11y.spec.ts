import { test, expect } from "@playwright/test";
import { AxeBuilder } from "@axe-core/playwright";

// KEEL-WEB-038 v3 public route surface. Retired routes (/models, /api-reference,
// /marketplace, /governance, /brand, /playground, /search) 301 via next.config.ts.
const ROUTES = [
  "/",
  "/about",
  "/product",
  "/pricing",
  "/changelog",
  "/contact",
  "/docs",
  "/sign-in",
] as const;

for (const route of ROUTES) {
  test(`a11y: ${route} has no WCAG 2.2 AA violations`, async ({ page }) => {
    await page.goto(route, { waitUntil: "networkidle" });
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    const summary = results.violations.map(
      (v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s) — ${v.help}`,
    );
    expect(summary, `axe violations on ${route}:\n${summary.join("\n")}`).toEqual([]);
  });
}

test("perf smoke: homepage loads within budget", async ({ page }) => {
  await page.goto("/", { waitUntil: "load" });
  const metrics = await page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0] as
      | PerformanceNavigationTiming
      | undefined;
    const resources = performance.getEntriesByType("resource") as PerformanceResourceTiming[];
    const transferBytes = resources.reduce((sum, r) => sum + (r.transferSize || 0), 0);
    return {
      domContentLoadedMs: nav?.domContentLoadedEventEnd ?? Number.POSITIVE_INFINITY,
      loadMs: nav?.loadEventEnd ?? Number.POSITIVE_INFINITY,
      transferBytes,
    };
  });
  // Generous budgets for localhost CI: catch gross regressions, not micro-tuning.
  expect(metrics.domContentLoadedMs).toBeLessThan(5_000);
  expect(metrics.loadMs).toBeLessThan(8_000);
  expect(metrics.transferBytes).toBeLessThan(4 * 1024 * 1024);
});
