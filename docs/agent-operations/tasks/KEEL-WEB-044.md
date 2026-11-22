# KEEL-WEB-044 — Interactive cost comparison on /pricing

- **STATUS**: READY_FOR_REVIEW · Devin · 2026-11-22 · `feature/keel-web-045-cost-compare`
- **Scope**: `website/src/components/site/CostCompare.tsx` (new) + FIG 2.1 block in `website/src/app/pricing/page.tsx`.
- **What**: workload slider (1–100M tok/day) → open_weight marginal cost $0 (green) vs frontier ≈ $10/1M tok provider list rate ×30d, labeled illustrative; "BYOM 0% markup" framing matches existing pricing copy.
- **Verified**: `npx tsc --noEmit` clean; `npm run build` — /pricing compiles (1.34 kB).
- **a11y**: role=group + aria-label, real range input with aria-label, no color-only meaning (values printed).
