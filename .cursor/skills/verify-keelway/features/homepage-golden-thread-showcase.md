# Zero-Install Homepage Golden-Thread Studio Showcase (`/#studio-showcase`)

Public visitors experience the complete **4-Stage Golden-Thread Sovereign AI Studio** directly on the Next.js 15 homepage (`/#studio-showcase`) with zero signup or CLI install required: converting LangGraph `StateGraph` loops into bounded SVG KFlow topologies, toggling **P-10 Human Gates** with instant Python & `@keelway/sdk` TypeScript AST line sync, scrubbing **Flight-Tape Waterfall** timelines with `$0.00` cached counterfactual forks, inspecting **Seatbelt/Bubblewrap Blast-Radius** boundaries, and tripping live **Prompt Regression Gates** (`PASS` → `BLOCK`).

## Sub-features

- Switch across 3 curated domain presets (`langgraph-refund-cycle`, `pr-security-sentinel`, `clinical-hipaa-intake`) and step through Stages `01`–`04` (*Plan & Import → Build & Sync Studio → Scrub & Blast-Radius → Govern & Ship*)
- Toggle `P-10` human-approval locks directly on SVG KFlow nodes (`syncShowcaseGraphToCode`) or sync source edits back to the visual topology (`syncShowcaseCodeToGraph`) across both Python and `@keelway/sdk` TypeScript tabs with exact AST line-span highlighting
- Scrub the Flame Waterfall Flight-Tape playhead and toggle counterfactual OpenCore replay (`$0.00` cached upstream spans vs. forked downstream execution) alongside Seatbelt/Bubblewrap filesystem and zero-egress Blast-Radius probe receipts
- Inject adversarial prompt/schema drift in Stage `04` (`evaluateShowcasePromptGate`) to observe deterministic `PASS` → `BLOCK` enforcement and copy the verified `pip install keelway==1.1.0` handoff snippet

## How to get to it (user POV)

1. **Homepage Anchor (`/#studio-showcase`):** Load `/` on the production Next.js server (`npm run build && npm run start` in `website/`) and scroll to `#studio-showcase` (above the `#quickstart` CLI card).
2. **Command Palette (`⌘K` / `Ctrl+K`):** Open the global Command Palette or `/api/search-index` and select the **Golden-Thread Studio Showcase** action jumping to `/#studio-showcase`.

## Cold Headless Chromium Verification Procedure

Start from a clean production build of `website/` and drive headless Chromium against `http://127.0.0.1:3100/#studio-showcase`:

```bash
cd website
npm run build
PORT=3100 npm run start &
WEB_PID=$!
trap "kill $WEB_PID 2>/dev/null || true" EXIT

CTRL=../.cursor/skills/verify-keelway/scripts/control-keelway
STATE=/tmp/keelway-verify-phase13-web
EVIDENCE=/tmp/keelway-evidence-phase13-web
mkdir -p "$STATE" "$EVIDENCE"

# 1. Stage 01 (Plan & Import): Load /#studio-showcase cleanly with zero console/page errors
$CTRL browser goto       --state-dir "$STATE" --url "http://127.0.0.1:3100/#studio-showcase"
$CTRL browser wait-for   --state-dir "$STATE" --text "Plan & Import"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/01-stage1-plan-import.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/01-stage1-plan-import.png"

# 2. Stage 02 (Build & Sync Studio): Toggle P-10 lock on SVG node -> verify @keelway/sdk code & AST line update
$CTRL browser click      --state-dir "$STATE" --role tab --name "Build & Sync Studio"
$CTRL browser click      --state-dir "$STATE" --role button --name "TypeScript (@keelway/sdk)"
$CTRL browser click      --state-dir "$STATE" --role button --name "Toggle P-10"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/02-stage2-p10-sdk-sync.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/02-stage2-p10-sdk-sync.png"

# 3. Stage 03 (Scrub & Blast-Radius): Toggle Flight-Tape counterfactual fork ($0.00 cached upstream) & inspect radar
$CTRL browser click      --state-dir "$STATE" --role tab --name "Scrub & Blast-Radius"
$CTRL browser click      --state-dir "$STATE" --role button --name "Counterfactual"
$CTRL browser wait-for   --state-dir "$STATE" --text "$0.00"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/03-stage3-flight-tape-fork.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/03-stage3-flight-tape-fork.png"

# 4. Stage 04 (Govern & Ship): Trip Adversarial Prompt Gate from PASS -> BLOCK & verify keelway==1.1.0 handoff
$CTRL browser click      --state-dir "$STATE" --role tab --name "Govern & Ship"
$CTRL browser wait-for   --state-dir "$STATE" --text "PASS"
$CTRL browser click      --state-dir "$STATE" --role button --name "Adversarial"
$CTRL browser wait-for   --state-dir "$STATE" --text "BLOCK"
$CTRL browser wait-for   --state-dir "$STATE" --text "keelway==1.1.0"
$CTRL browser snapshot   --state-dir "$STATE" --aria --out "$EVIDENCE/04-stage4-prompt-gate-block.aria.txt"
$CTRL browser screenshot --state-dir "$STATE" --out "$EVIDENCE/04-stage4-prompt-gate-block.png"
```

## Gotchas

- Always verify against a cold `next build && next start` production server rather than `next dev` so static prerendering, CSP headers, and self-hosted `.woff2` variable fonts match production.
- Disable smooth scroll (`document.documentElement.style.scrollBehavior = "auto"`) before dispatching CDP physical mouse clicks (`runBrowserSubcommand` / `withCdpPage` in `.cursor/skills/verify-keelway/scripts/lib/cdp-browser.mjs`) so `scrollIntoView` settles synchronously.
- All animations must respect `useReducedMotion()` (`prefers-reduced-motion: reduce`), and zero third-party CDNs or `/playground` links may appear in network requests or DOM snapshots.
