# KEEL-WEB-049 — web-next security hardening (Next 15.5.29) + a11y coverage

## Objective

Close the production dependency advisories on the deployed `web-next`
surface (kora-sable.vercel.app) and extend the axe e2e suite to cover the
routes shipped under KEEL-WEB-048.

## Audit findings

`npm audit --omit=dev` reported **3 vulnerabilities (1 critical, 2 high)**:

- **`next@15.5.6`** — ~37 open advisories including the critical React
  flight-protocol RCE (GHSA-9qr9-h5gf-34mp / React2Shell), multiple Server
  Actions SSRF/DoS/cache-poisoning and middleware-bypass issues
- **`sharp`** — libvips/libheif/librsvg CVEs (transitive, image pipeline)
- **`postcss@8.4.31`** — nested *exact pin* inside `next`
  (GHSA-r28c-9q8g-f849: sourceMappingURL path traversal); top-level
  `postcss` was already safe at 8.5.33

## Shipped

| Change | Result |
|---|---|
| `next` 15.5.6 → **15.5.29** (stays on 15.5.x — no major bump) | All ~37 next advisories closed |
| `sharp` via `npm audit fix` | libvips CVEs closed |
| `postcss` devDep `^8.4.49` → `^8.5.33` + `"overrides": {"next": {"postcss": "$postcss"}}` | Nested exact-pin dedupes to 8.5.33 — avoids a Next-16 major jump for a single nested dep |
| `e2e/a11y.spec.ts` ROUTES | `+ /blog /legal /signup /offline` — new routes now under axe WCAG 2.2 AA |

**`npm audit --omit=dev`: 0 vulnerabilities.**

## Verification

- `npx tsc --noEmit`: clean
- `npx next build`: 19 routes prerender on Next 15.5.29
- `npx playwright test`: **16/16** — all routes axe-clean incl. new routes,
  mobile 44px thumb-target rule, perf smoke

## Deliberately not done

- **Next 16 major bump** — only remaining path would be for the nested
  postcss, which the `$postcss` override already pins; a 16.x migration is a
  separate scoped task (React 19.2 floor, App Router changes)

## Follow-up — `website` sweep (same finding class)

`website` (the marketing Next app, `next@^15.2.4` → resolves 15.5.29)
carried the same nested `postcss@8.4.31` via `next`'s exact pin — the only
remaining advisory there. Same remedy applied:
`"overrides": {"next": {"postcss": "$postcss"}}` → dedupes to top-level
`postcss@8.5.32`. `npm audit --omit=dev`: 0. `tsc --noEmit` clean.
`dev-app` audited at 0 vulnerabilities (no change needed).
