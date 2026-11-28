import { test, expect } from "@playwright/test";

// Keep in sync with e2e/a11y.spec.ts ROUTES.
const ROUTES = ["/", "/product", "/pricing", "/docs", "/changelog", "/about", "/blog", "/contact", "/legal", "/sign-in", "/signup", "/offline"] as const;

for (const route of ROUTES) {
  test(`route smoke: ${route} renders`, async ({ page }) => {
    const res = await page.goto(route, { waitUntil: "domcontentloaded" });
    expect(res?.status(), `${route} returned ${res?.status()}`).toBeLessThan(400);
    await expect(page.locator("h1").first()).toBeVisible();
    expect(await page.title(), `${route} missing <title>`).toBeTruthy();
  });
}

test("all nav and footer internal links resolve", async ({ page, request }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const hrefs = await page
    .locator('header a[href^="/"], footer a[href^="/"]')
    .evaluateAll((els) => Array.from(new Set(els.map((el) => el.getAttribute("href")))));
  expect(hrefs.length).toBeGreaterThan(0);
  const broken: string[] = [];
  for (const href of hrefs) {
    const path = (href ?? "").split("#")[0];
    if (!path) continue;
    const res = await request.get(path);
    if (res.status() >= 400) broken.push(`${path} → ${res.status()}`);
  }
  expect(broken, `broken internal links:\n${broken.join("\n")}`).toEqual([]);
});

test("every public route has a meta description", async ({ page }) => {
  const missing: string[] = [];
  for (const route of ROUTES) {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    const desc = await page.locator('meta[name="description"]').getAttribute("content");
    if (!desc) missing.push(route);
  }
  expect(missing, `routes missing meta description: ${missing.join(", ")}`).toEqual([]);
});

test("every public route self-canonicalizes", async ({ page }) => {
  const wrong: string[] = [];
  for (const route of ROUTES) {
    await page.goto(route, { waitUntil: "domcontentloaded" });
    const canonical = await page.locator('link[rel="canonical"]').getAttribute("href");
    const pathname = canonical ? new URL(canonical).pathname : null;
    if (pathname !== route) wrong.push(`${route} → ${canonical ?? "none"}`);
  }
  expect(wrong, `routes with wrong canonical:\n${wrong.join("\n")}`).toEqual([]);
});
