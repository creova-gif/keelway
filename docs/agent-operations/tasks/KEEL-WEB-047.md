# KEEL-WEB-047 — Paper pages 05–09 parity audit + two spec deltas

**Status**: READY_FOR_REVIEW
**Branch**: feature/keel-web-047-pages05-09-parity
**Paper source**: `Keelway — Brand Kit & Homepage`, pages 05–07, 09

## Audit result — four previously unswept pages

| Page | Verdict |
|---|---|
| 05 Sorvex Labs (brand architecture + identity) | delta fixed — footer endorsement must be the canonical `A Sorvex Labs product` (09 footer anatomy; /about already used it via KEEL-WEB-046). Steel register noted: no Sorvex surface exists yet, nothing to apply |
| 06 CLI & Terminal | compliant — noun→verb grammar (`mobile pair`, `token create`, `memory search`), zero ANSI (the spec's own mono fallback), `--json` on read verbs (doctor, tape, cost, vault list), argparse gives exit 2 on usage |
| 07 Motion & Interaction | compliant — `kw-land`/`kw-fade`/`kw-seal-ring`/`kw-draw` are exactly the causal set; `kw-skeleton` carries the "never shimmer" comment; `prefers-reduced-motion` collapses durations in tokens.css on both surfaces + JS checks in `reveal.tsx`/`terminal-demo.tsx`; no looping pulses/breathing dots found |
| 09 Website | delta fixed — recommended tier needed the `most common` mono tag (wash tint + brass border were already compliant); header ink/muted grammar already correct |

## Changes

- `web-next/src/app/pricing/page.tsx` — `most common` mono micro tag on the Pro (recommended) tier, per 09.3/13.1
- `web-next/src/components/site/footer.tsx` — `A Sorvex Labs company.` → `A Sorvex Labs product.` (canonical endorsement line)

## Honest deferral

- CLI exit code 3 (denied-by-policy): spec'd in 06.1 + the 09.3 doc card. The CLI's only network call sites are localhost Ollama probes with no auth — no live caller can produce a 403 today, so a `main()` mapping would be dead code. Implement when the CLI grows its first authenticated endpoint call.
- Sorvex steel register: no Sorvex-branded surface exists; the endorsement line is the only required presence, per 09 ("the only place Sorvex appears on product surfaces").

## Verification

- `npx tsc --noEmit` — clean
- `npm run build` — all routes prerendered
- `npx playwright test` — 12/12 green (axe + mobile target gate)
