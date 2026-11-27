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

### F-02 · Sign-up/sign-in form collects then discards email (HIGH)
`magic-link-form.tsx` accepts an email, prevents submit, and renders "request access on
GitHub" — the address is never transmitted or stored. The copy is honest about private
preview, but a form that implies delivery and silently drops the input is a conversion
dead-end and a subtle trust cost. Old `website/` advertised `/api/early-access` in its
README but the route file no longer exists — there is **no working intake endpoint in
either app**.
**Fix options:** (a) port a fail-closed `/api/early-access` route (private webhook, no
public-Issue routing per AGENTS.md PII rule); (b) replace the form with a direct GitHub
link and no fake input. Recommend (a) when a private webhook destination exists;
(b) until then.

### F-03 · Tailwind ambiguous-class warnings — real styling risk (MED — fixed this task)
Dev build warned `duration-[var(--dur-base)]` and `ease-[var(--ease-settle)]` are
ambiguous in `motion/reveal.tsx` — under Tailwind 3.4 arbitrary `var()` values on
non-numeric utilities can be dropped or mis-emitted, silently killing the reveal
transition. **Fixed:** switched to `transition-[opacity,transform]` +
`[transition-duration:var(--dur-base)] [transition-timing-function:var(--ease-settle)]`
arbitrary properties; fresh compile emits zero warnings.

### F-04 · e2e coverage is accessibility-only (MED)
`e2e/` contains a single `a11y.spec.ts`. The master audit calls for nav, mobile menu,
all internal links, signup/contact flows, redirects, metadata, and error-page coverage.
No test asserts `/blog` or `/signup` render — which is exactly why F-01 can regress
invisibly. **Backlog item:** route-smoke spec iterating the route table.

### F-05 · Legacy `website/` app is a divergent second surface (MED)
`website/` (v3 Maritime build) still compiles in CI alongside web-next, and its README
documents routes (`/models`, `/governance`, `/api-reference`, `/api/early-access`) that
return 404 or no longer exist in source. Two public-site codebases invite drift and
confuse deploy mapping. **Backlog item:** mark `website/` deprecated in its README or
remove once web-next is confirmed as the prod project root.

### F-06 · Homepage has no explicit page metadata (LOW)
9 routes export `metadata`; the homepage relies on `layout.tsx` defaults. Verify OG
title/description for `/` specifically — risk of generic social previews on the most
shared URL.

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
| 2 | F-02: real early-access intake or honest link (product call) | HIGH | S–M |
| 3 | F-04: route-smoke e2e spec (all routes render + no 404 nav targets) | MED | S |
| 4 | F-05: deprecate or remove legacy `website/` app | MED | S |
| 5 | F-06: explicit `/` OG metadata | LOW | XS |
| 6 | F-07: Docs 2.0 — searchable docs surface, API reference | LOW | Post-beta |
| 7 | F-03: ambiguous Tailwind classes | — | **DONE this task** |

## 5. Honest limitations of this audit

- Production behavior assessed via route probes, not Vercel dashboard access.
- Lighthouse/Web-Vitals numbers not captured locally; CI perf smoke is the standing gate.
- `/signup` and `/blog` rendered fine locally — F-01 is a deploy-currency defect, not a code defect.
