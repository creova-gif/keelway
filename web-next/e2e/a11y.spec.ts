import { test, expect } from "@playwright/test";
import { AxeBuilder } from "@axe-core/playwright";

const ROUTES = ["/", "/product", "/pricing", "/docs", "/changelog", "/about", "/blog", "/contact", "/legal", "/sign-in", "/signup", "/offline"] as const;

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


test("a11y: 404 page has no WCAG 2.2 AA violations", async ({ page }) => {
  await page.goto("/__not-found-test__", { waitUntil: "networkidle" });
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summary = results.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s) — ${v.help}`,
  );
  expect(summary, `axe violations on 404:\n${summary.join("\n")}`).toEqual([]);
});

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
  expect(metrics.domContentLoadedMs).toBeLessThan(5_000);
  expect(metrics.loadMs).toBeLessThan(8_000);
  expect(metrics.transferBytes).toBeLessThan(4 * 1024 * 1024);
});

test.describe("mobile viewport (390px)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("a11y: / has no WCAG 2.2 AA violations on mobile", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    const summary = results.violations.map(
      (v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s) — ${v.help}`,
    );
    expect(summary, `axe violations on mobile /:\n${summary.join("\n")}`).toEqual([]);
  });

  test("mobile nav opens and meets the 44px thumb-target rule", async ({ page }) => {
    await page.goto("/", { waitUntil: "networkidle" });
    const toggle = page.getByRole("button", { name: "Toggle navigation" });
    const box = await toggle.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(box!.width).toBeGreaterThanOrEqual(44);
    await toggle.click();
    const links = page.getByRole("navigation", { name: "Mobile" }).getByRole("link");
    for (const link of await links.all()) {
      expect((await link.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    }
  });
});
