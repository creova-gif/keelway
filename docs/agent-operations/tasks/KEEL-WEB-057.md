# KEEL-WEB-057 — F-02 production verification + secret hygiene

## Status: COMPLETED

Live probes against `kora-sable.vercel.app` post-WEB-055:
- `/`, `/signup`, `/blog`, `/product` → 200 (canonical web-next serving).
- `POST /api/early-access` foreign origin → `forbidden origin` (allowlist enforced).
- `POST /api/early-access` allowed origin → fail-closed 503 "temporarily
  unavailable" — verified live while `EARLY_ACCESS_WEBHOOK_URL` is absent.
- `EARLY_ACCESS_WEBHOOK_SECRET` migrated `encrypted` → `sensitive` via
  Vercel API type-only patch (readable-secret flag cleared; value untouched).

Residual: `EARLY_ACCESS_WEBHOOK_URL` still needs the webhook URL value
from the user, then provision on production+preview.
