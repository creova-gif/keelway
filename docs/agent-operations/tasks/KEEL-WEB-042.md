# KEEL-WEB-042 — Interactive policy evaluator on /product

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-042
- **TASK TITLE**: Live pre-egress policy demo (FIG 1.3) on the product page
- **CURRENT STATUS**: READY_FOR_REVIEW
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-042-policy-demo

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] Interactive `PolicyDemo` on `/product` — three request-condition toggles (tenant payload / airgap_strict / spend cap), ▸ evaluate computes route + ALLOW/DENY verdict chip with the matched rule in plain language.
- [x] Verdict logic mirrors real policy ordering: airgap → local-only; tenant payload → local (egress denied); spend cap → frontier DENY; unconstrained → frontier BYOM 0% markup.
- [x] a11y: role=group + aria-label, real checkboxes (brass accent), aria-live=polite on the verdict block, kw-land entrance per evaluation.
- [x] Extends the interactive-demo program started in KEEL-WEB-041 (terminal replay) — same kw-figure/kw-fig-btn conventions, zero new deps.

#### WORK COMPLETED & FILES MODIFIED
- `website/src/components/site/PolicyDemo.tsx` (new): toggles + evaluate + verdict rendering.
- `website/src/app/product/page.tsx`: FIG 1.3 section after FigureTabs.

#### TESTS EXECUTED & EVIDENCE
- `npx tsc --noEmit`: clean.
- `npm run build`: `/product` compiles (4.08 kB).

#### NEXT RECOMMENDED ACTION
- Merge after CI; marketing-site interactive set now covers gate (home), terminal (home), figures tabs + policy (product).
