# KEEL-WEB-053 — Website audit follow-ups: route-smoke e2e, early-access intake, legacy deprecation

## Status: COMPLETED

## Scope
Land the three implementable findings from `docs/audits/WEBSITE_UI_UX_AUDIT.md`
(WEB-052): F-04 route-smoke e2e coverage, F-02 real early-access intake, F-05
legacy `website/` deprecation marking.

## Files modified
- `web-next/e2e/routes.spec.ts` (new): 14 route-smoke tests — all 12 public
  routes return 200, header/footer internal-link integrity crawl, per-page
  meta-description assertions. A stale prod deploy now fails this gate instead
  of shipping silently (closes F-04).
- `web-next/src/app/api/early-access/route.ts` (new): faithful TypeScript port
  of the canonical `api/early-access.js` semantics — origin allowlist
  (`keelway.dev`, `kora-sable.vercel.app`, `kora-eight-nu.vercel.app` +
  `EARLY_ACCESS_ALLOWED_ORIGINS`), 5 req/10 min per-IP rate limit, 4KB body
  cap, work-email/interest/role/region validation, fail-closed `503` without
  `EARLY_ACCESS_WEBHOOK_URL`, optional HMAC `X-Keelway-Signature-256` via
  `EARLY_ACCESS_WEBHOOK_SECRET`, `KW-XXXXXXXX` reference IDs. Added a
  non-object JSON guard the CJS original lacked (closes F-02).
- `web-next/src/components/site/magic-link-form.tsx`: now POSTs `{email}` to
  `/api/early-access` with loading/error/success states; the 503 surfaces as
  "temporarily unavailable" instead of silently discarding input.
- `website/README.md`: deprecation banner — names `web-next/` canonical,
  labels the route table historical, notes CI's `website-devapp-and-sdks` job
  still compiles the shared toolchain against `website/node_modules` so full
  removal is a follow-up (mitigates F-05).
- `docs/audits/WEBSITE_UI_UX_AUDIT.md`: F-02/F-04/F-05 statuses updated;
  backlog table re-sorted (F-01 + webhook provisioning remain user-side).

## Tests executed & evidence
- `npm run typecheck` (web-next): clean
- `npm run build` (web-next): clean, `/api/early-access` listed ƒ (Dynamic)
- `npm run test:e2e` (web-next): **30/30 passed** — 16 a11y/perf + 14 new
  route-smoke
- Live route probe (`next start`): GET→405, no/disallowed Origin→403,
  `null`/non-object JSON→400, valid work email w/o webhook env→503 fail-closed,
  OPTIONS preflight→204

## Known risks & blockers
- Route returns 503 until `EARLY_ACCESS_WEBHOOK_URL` is provisioned in the
  Vercel project — intentional fail-closed; the form reports it honestly.
- `website/` full removal still blocked on repointing the CI toolchain job.

## Next recommended action
Owner: promote the latest web-next deployment to prod (F-01) and provision
`EARLY_ACCESS_WEBHOOK_URL` + optional `EARLY_ACCESS_WEBHOOK_SECRET`. Follow-up
task: repoint `website-devapp-and-sdks` CI away from `website/`, then delete it.
