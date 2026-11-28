# Keelway Public Website — UI/UX Audit & Release Assessment

**Task:** KEEL-WEB-052 · **Date:** 2026-11-27 · **Auditor:** Devin
**Surface audited:** `web-next/` (canonical marketing site, Paper V3 "Keel Black & Brass")
**Baseline:** `main` @ `abbbf6c` · local `next dev` + deployed `https://kora-sable.vercel.app/`
**Method:** full-route Playwright capture at 1440px + 390px, source inspection, prod route probes, build-log review. Scorecard per the website-audit weighting.

---

## 1. Executive summary

The web-next site is in materially better shape than a beta candidate typically is: a
distinct V3 brand kit, honest product-led figures, canonical 4-tier pricing, and CI-gated
WCAG 2.2 AA + perf smoke on every PR. It does **not** need a redesign — the Paper V3
direction already satisfies the "premium, technical, editorial" bar.

The gap to the 90/100 release threshold is concentrated in **conversion plumbing and
deploy freshness**, not visual design.

**Estimated score: ~83/100.**

| Dimension | Weight | Score | Verdict |
|---|---|---|---|
| Brand & visual design | 15% | 13 | Distinct "Keel Black & Brass" kit; K′ mark, editorial display type, instrument-panel figures. Not generic. |
| Usability & navigation | 15% | 13 | 7-item nav, hamburger at 390px, no overflow found. Minor: no active-route indicator verified. |
| Product messaging | 15% | 14 | "Agents that answer to you." + control-plane FIG 0.1 is the right opener; honest "Illustrative"/"private preview" labels throughout. |
| Conversion & onboarding | 15% | 8 | **Weakest.** Dead email form (discards input); prod 404s on /signup + /blog. |
| Performance | 10% | 9 | CI perf smoke gate; SSR App Router; no heavy libs observed. |
| Accessibility | 10% | 9 | axe-core WCAG 2.2 AA gate in CI; sr-only labels, role=status present. |
| SEO & discoverability | 10% | 8 | robots.ts, sitemap.ts, manifest, OG image, feed.xml, per-route metadata on 9 pages. |
| Security & technical trust | 5% | 4 | HSTS+preload on prod; no forms posting sensitive data; no fabricated proof observed. |
| Content & documentation | 5% | 4 | /docs is an honest repo-link index; /changelog real; /blog is thin (index-level). |
| **Total** | **100%** | **~82–84** | |

---

## 2. Findings register

### F-01 · Production deploy lags main (HIGH — conversion blocker)
`kora-sable.vercel.app` serves an older web-next build: `/blog` and `/signup` return
**404** in production though both merged in WEB-048 (PR #230). `/signup` is the primary
conversion CTA target. The `deploy.yml` workflow only covers infra paths — website prod
deploys depend on the Vercel GitHub integration, which has not shipped `main` recently.
**Owner action needed:** verify the Vercel project's production branch/deploy hooks.

### F-02 · Sign-up/sign-in form collects then discards email (HIGH — fixed KEEL-WEB-053)
`magic-link-form.tsx` accepted an email, prevented submit, and rendered "request access
on GitHub" — the address was never transmitted or stored. **Fixed:** the form now POSTs
to a real fail-closed `/api/early-access` route handler ported from the canonical
`api/early-access.js` semantics (origin allowlist, per-IP rate limit, 4KB body cap,
work-email validation, `503` without `EARLY_ACCESS_WEBHOOK_URL`, optional HMAC
`X-Keelway-Signature-256`, `KW-XXXXXXXX` reference IDs). The form gains honest
loading/error/success states and surfaces the 503 as "temporarily unavailable" rather
than silently dropping input. **Remaining owner action:** provision
`EARLY_ACCESS_WEBHOOK_URL` (+ optional `EARLY_ACCESS_WEBHOOK_SECRET`) in the Vercel
project so intake actually delivers; until then the endpoint fails closed by design.

### F-03 · Tailwind ambiguous-class warnings — real styling risk (MED — fixed this task)
Dev build warned `duration-[var(--dur-base)]` and `ease-[var(--ease-settle)]` are
ambiguous in `motion/reveal.tsx` — under Tailwind 3.4 arbitrary `var()` values on
non-numeric utilities can be dropped or mis-emitted, silently killing the reveal
transition. **Fixed:** switched to `transition-[opacity,transform]` +
`[transition-duration:var(--dur-base)] [transition-timing-function:var(--ease-settle)]`
arbitrary properties; fresh compile emits zero warnings.

### F-04 · e2e coverage is accessibility-only (MED — fixed KEEL-WEB-053)
`e2e/` contained a single `a11y.spec.ts`; nothing asserted `/blog` or `/signup` render —
exactly why F-01 regressed invisibly. **Fixed:** new `e2e/routes.spec.ts` asserts all 12
public routes return 200, crawls header/footer internal links for dead targets, and
checks per-page meta descriptions (14 tests alongside the 16 a11y/perf tests). A stale
prod deploy now fails the route-smoke gate rather than shipping silently.

### F-05 · Legacy `website/` app is a divergent second surface (MED — resolved KEEL-WEB-055)
`website/` (v3 Maritime build) used to compile and e2e-test in CI alongside web-next,
and its README documented routes that return 404 or no longer exist in source.
**Resolved:** deprecation banner landed (WEB-053); CI no longer builds or e2e-tests
the app (WEB-054); directory removed entirely (WEB-055). The drift gates it hosted
were migrated, not retired: `product-facts.json` + `openapi.json` + `public/` mirrors
moved to `web-next/`; `test_website_facts.py` → `test_webnext_facts.py` repointed to
the live surface (self-canonicalizing routes, sitemap/robots/manifest/feed, self-hosted
fonts, zero-CDN scan, real pricing tokens); phases 12–17 + api_export + full_beta now
read `web-next/`; agent write scopes `website/**` → `web-next/**`; legacy `.html`
bookmarks get 308 redirects in `next.config.ts`.

### F-06 · Homepage has no explicit page metadata (LOW — fixed KEEL-WEB-054, scope expanded)
9 routes exported `metadata`; the homepage relied on `layout.tsx` defaults. Inspection
found the real defect was broader: the layout set `alternates.canonical: "/"`, so
**every route served `<link rel="canonical" href="/">`** — subpages could be
de-indexed in favor of the homepage — and `/product` exported no metadata at all.
**Fixed:** layout canonical removed; all 12 routes now self-canonicalize; `/product`
and `/offline` gained title/description; `routes.spec.ts` asserts per-page canonical
+ meta description so a layout-level regression fails e2e.

### F-07 · Content depth (LOW — post-beta appropriate)
/docs is an external-link index (honest, not fake depth); /blog has an index but thin
entries; no searchable docs, no API reference page (old site had one). Acceptable for
beta per "publish only what's real"; schedule Docs 2.0 post-beta.

---

## 3. Verified-conformant checklist (no action needed)

- Canonical 4-tier pricing (Community/BYOM/Pro/Enterprise), "most common" tag, honest
  BYOM API-key caveat footnote, marketplace revenue-share strip, marginal-token-cost chart
- Product-led figures throughout (control-plane panels, policy demo, terminal replay,
  cost compare) — no stock imagery, no fake benchmark claims
- "Illustrative" labels on simulated charts; "private preview, magic link only" on auth
- Mobile: hamburger nav, no horizontal overflow at 390px, hero scales correctly
- Security headers on prod: `strict-transport-security ... preload` verified
- SEO primitives: robots.ts → sitemap.xml, manifest.ts, og-image.jpg, feed.xml route
- Motion: Reveal honors `prefers-reduced-motion`; SSR content visible without JS

---

## 4. Prioritized backlog

| # | Item | Sev | Effort |
|---|---|---|---|
| 1 | F-01: restore prod deploy currency (Vercel project config) | HIGH | User-side |
| 2 | F-02: provision `EARLY_ACCESS_WEBHOOK_URL` (+ `..._SECRET`) in Vercel | HIGH | User-side |
| 3 | F-05: drift gates migrated to `web-next/` + `website/` removed | — | **DONE (WEB-055)** |
| 4 | F-07: Docs 2.0 — searchable docs surface, API reference | LOW | Post-beta |
| 5 | F-03: ambiguous Tailwind classes | — | **DONE (WEB-052)** |
| 6 | F-04: route-smoke e2e spec | — | **DONE (WEB-053)** |
| 7 | F-02: real `/api/early-access` + wired form | — | **DONE (WEB-053)** |
| 8 | F-05: `website/` deprecation banner + CI decoupling | — | **DONE (WEB-053/054)** |
| 9 | F-06: per-page canonical + `/product`/`/offline` metadata | — | **DONE (WEB-054)** |

## 5. Honest limitations of this audit

- Production behavior assessed via route probes, not Vercel dashboard access.
- Lighthouse/Web-Vitals numbers not captured locally; CI perf smoke is the standing gate.
- `/signup` and `/blog` rendered fine locally — F-01 is a deploy-currency defect, not a code defect.
