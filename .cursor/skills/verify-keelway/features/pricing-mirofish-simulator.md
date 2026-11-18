# Calibrated Pricing & MiroFish Market Simulator

Users evaluate seat quotas, BYOM 0% token-markup TCO, and 5-persona buyer elasticity (`Indie Builder`, `AI Startup CTO`, `Design Ops Lead`, `Regulated FinTech VP`, `Sovereign Enterprise CISO`) comparing calibrated pricing (`$15` BYOM / `$29` Pro annual) against legacy `$39`/`$49` schedules.

## Sub-features

- Adjust team seat count (`[aria-label="Simulation team seats"]`) and monthly BYOM API spend (`[aria-label="Simulation monthly API spend"]`) in the **Operations** view
- Run the 5-persona elasticity check (`Run 5-Persona MiroFish Pricing Check`) and inspect `[aria-label="Simulated buyer persona verdicts"]`
- Switch workspace subscription tier (`community`, `byom`, `pro`, `enterprise`) via `[aria-label="Subscription tier"]` in the top workspace bar and observe live quota gauges update
- Run `cli.py pricing-eval --schedule compare --seats <N> --api-spend <USD> --json` for side-by-side schedule comparison

## How to get to it (user POV)

1. **Operations view in `/app`:** Click `Operations` in `[aria-label="Unified platform views"]` and scroll to `[aria-label="Calibrated pricing and MiroFish market simulator"]`.
2. **Sovereign CLI:** Run `python cli.py pricing-eval --schedule compare --seats 12 --api-spend 2500 --json`.
3. **REST API:** `POST /v1/platform/pricing/simulate` with `{"schedule": "compare", "seats": 12, "monthly_api_spend_usd": 2500}`.

## Driving it with control-keelway

Assume `STATE=/tmp/keelway-verify-pricing` is launched and `EVIDENCE=/tmp/keelway-evidence-pricing` is your persistent proof folder:

```bash
CTRL=./.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-pricing
EVIDENCE=/tmp/keelway-evidence-pricing

# 1. Switch to Operations view and configure 12 seats + $2,500/mo BYOM spend
$CTRL browser click  --state-dir "$STATE" --role button --name "Operations"
$CTRL browser fill   --state-dir "$STATE" --label "Simulation team seats" --value "12"
$CTRL browser select --state-dir "$STATE" --label "Simulation monthly API spend" --value "2500"
$CTRL browser click  --state-dir "$STATE" --role button --name "Run 5-Persona MiroFish Pricing Check"
$CTRL browser wait-for --state-dir "$STATE" --text "Pricing Health"

# 2. Capture ARIA + screenshot of persona verdicts
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-operations-mirofish.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-operations-mirofish.png" --full-page

# 3. Cross-check Sovereign CLI pricing-eval JSON output for identical parameters
$CTRL cli --state-dir "$STATE" --out "$EVIDENCE/02-cli-pricing-eval.json" -- \
  pricing-eval --schedule compare --seats 12 --api-spend 2500 --json
```

Observable end state that proves success:

- `01-operations-mirofish.aria.txt` contains `region "Calibrated pricing and MiroFish market simulator"`, `list "Simulated buyer persona verdicts"` with 5 `listitem` entries, `$15` BYOM / `$29` Pro calibrated figures, and `0%` BYOM proxy markup.
- `02-cli-pricing-eval.json` reports `calibrated.byom_annual_usd == 15`, `calibrated.pro_annual_usd == 29`, `calibrated.hidden_fee_distrust_score == 0.0`, and `calibrated.pricing_health_score > legacy.pricing_health_score`.

## Gotchas

- `PricingMiroFishSimulator` is a deterministic mathematical elasticity simulator (`core/eval/pricing_mirofish.py`), not an outbound LLM swarm call; it executes offline with zero external API traffic and does not write rows to `platform_runtime.db`.
- `[aria-label="Simulation monthly API spend"]` is a `<select>` with discrete preset values (`250`, `1200`, `2500`, `10000`); use `browser select` for those presets, or call `cli.py pricing-eval --api-spend <FLOAT>` / `POST /v1/platform/pricing/simulate` for arbitrary dollar amounts.
