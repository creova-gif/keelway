# KEEL-WEB-006 — web-next /pricing on canonical spec

### TASK HANDOFF RECORD
- **TASK ID**: KEEL-WEB-006
- **TASK TITLE**: First real web-next screen — /pricing on the canonical 4-seat + marketplace model
- **CURRENT STATUS**: MERGED (PR #187)
- **LAST AGENT**: Devin
- **DATE**: 2026-11-22
- **BRANCH**: feature/keel-web-006-web-next-pricing

#### OBJECTIVE & ACCEPTANCE CRITERIA
- [x] /pricing renders the canonical spec — four seat tiers (Community $0 / BYOM $15-19 / Pro $29-35 / Enterprise custom) with real backend quotas (tokens/day, RPM, agents, workflows from SUBSCRIPTION_TIERS)
- [x] Marketplace shown as revenue-share stream, NOT a seat: 0/100 first-party, 85/15 verified, 80/20 enterprise, receipt-signed settlements
- [x] BYOM compliance notice preserved (consumer web subscriptions ≠ API access)
- [x] /pricing added to e2e ROUTES; axe WCAG 2.2 AA caught a real fg-dim contrast defect → fixed to fg-muted
- [x] typecheck + build green, 3/3 e2e pass

#### NEXT RECOMMENDED ACTION
- More pages or app-shell screens on web-next.
