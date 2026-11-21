# KEEL-APP-073 — Plan & Billing settings subsection (Paper `18.2`)

## Status
MERGED — PR #173, all checks green

## Canonical decision
**4 seat tiers + marketplace revenue stream** — `SubscriptionTierId` union and the workspace-bar
combobox cover the 4 seat plans (community/pro/byom/enterprise); the backend spec also publishes a
5th `marketplace` stream (`ecosystem_revenue_share`, 85/15) which renders honestly as a non-seat
card with no Switch affordance. The website's 5-seat-tier copy is marketing drift to reconcile.

## Delta
New `billing` `SettingsSubSection` + `SettingsBillingPanel` (9th rail item, "Plan & Billing"):

- **Plan** — current tier band (name, badge, stream kind, BYOM consumer-compliance notice)
- **Tiers** — 4 cards from live `/v1/subscriptions/tiers` (price, daily token/RPM/agent/workflow
  ceilings, capability counts); `Switch to X` reuses the workspace-bar `onChangeSubscriptionTier`
  path; current card `aria-current`; fallback spec mirrors backend when offline
- **Usage** — real cost-ledger spend (daily + monthly USD vs budgets) via `fetchGovernancePolicy`,
  labeled "measured from the cost ledger", read-only (caps still edited under Governance & Keys)
- **Settlement** — `/v1/marketplace/settlements` totals (gross/creator/fee), "receipt-signed"
  marking, honest empty state
- Decoder + fallback for both new endpoints; URL subsection parser accepts `billing`

## Tests
- 24 files, 124/124 vitest (2 new billing tests: 4-tier render + switch + honest empty)
- `tsc --noEmit` clean; build green; `core/dev_app_dist` regenerated
