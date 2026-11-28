import { test, expect } from "@playwright/test";

// Local-server CWV smoke — a regression tripwire, not field CWV.
// Thresholds are deliberately loose vs the 2.5s/0.1 product targets because
// `npm run start` on a dev box/CI runner is slower than the Vercel edge;
// the goal is catching layout explosions and ballooning payloads, not
// asserting lab-perfect vitals.
const LCP_BUDGET_MS = 6_000;
const CLS_BUDGET = 0.25;
const JS_TRANSFER_BUDGET_BYTES = 1_500_000;

// LCP and layout-shift entries are only observable through a
// PerformanceObserver — install one before the page's own scripts run.
function installVitalsObserver() {
  (window as unknown as { __vitals: { lcp: number; cls: number } }).__vitals = { lcp: 0, cls: 0 };
  new PerformanceObserver((list) => {
    const w = window as unknown as { __vitals: { lcp: number; cls: number } };
    for (const e of list.getEntries()) w.__vitals.lcp = e.startTime;
  }).observe({ type: "largest-contentful-paint", buffered: true });
  new PerformanceObserver((list) => {
    const w = window as unknown as { __vitals: { lcp: number; cls: number } };
    for (const e of list.getEntries()) {
      const ls = e as PerformanceEntry & { value: number; hadRecentInput: boolean };
      if (!ls.hadRecentInput) w.__vitals.cls += ls.value;
    }
  }).observe({ type: "layout-shift", buffered: true });
}

test("home page LCP, CLS and JS payload stay within smoke budgets", async ({ page }) => {
  await page.addInitScript(installVitalsObserver);
  await page.goto("/", { waitUntil: "load" });
  // Let LCP candidates settle (font/image arrivals) before reading.
  await page.waitForTimeout(2000);

  const vitals = await page.evaluate(() => {
    const w = window as unknown as { __vitals: { lcp: number; cls: number } };
    const js = (performance.getEntriesByType("resource") as PerformanceResourceTiming[])
      .filter((r) => r.name.endsWith(".js"))
      .reduce((sum, r) => sum + (r.transferSize || r.encodedBodySize || 0), 0);
    return { ...w.__vitals, js };
  });

  expect(vitals.lcp, "no largest-contentful-paint entry recorded").toBeGreaterThan(0);
  expect(vitals.lcp, `LCP ${vitals.lcp.toFixed(0)}ms over ${LCP_BUDGET_MS}ms budget`).toBeLessThan(LCP_BUDGET_MS);
  expect(vitals.cls, `CLS ${vitals.cls.toFixed(3)} over ${CLS_BUDGET} budget`).toBeLessThan(CLS_BUDGET);
  expect(vitals.js, `JS transfer ${(vitals.js / 1024).toFixed(0)}KB over ${(JS_TRANSFER_BUDGET_BYTES / 1024).toFixed(0)}KB budget`).toBeLessThan(JS_TRANSFER_BUDGET_BYTES);
});

test("key routes produce a first-contentful-paint", async ({ page }) => {
  for (const route of ["/", "/pricing", "/product"]) {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(500);
    const fcp = await page.evaluate(() => {
      const p = performance.getEntriesByType("paint").find((e) => e.name === "first-contentful-paint");
      return p ? p.startTime : -1;
    });
    expect(fcp, `${route} produced no first-contentful-paint`).toBeGreaterThan(0);
  }
});
