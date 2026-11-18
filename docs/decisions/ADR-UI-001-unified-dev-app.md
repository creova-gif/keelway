# ADR-UI-001: Consolidate Studio & Web Console into the 4-Rail Sovereign Dev App with Inline P-10 Gates & Tokens Rev 4

- **Status:** Accepted
- **Date:** 2026-11-14
- **Subsystem:** Developer UI, Studio Runtime Mount (`core/main.py`, `cli.py`, `dev-app/`)

## Context

Keelway previously maintained three separate UI surfaces and design explorations:
1. **`core/studio/index.html`:** Vanilla JavaScript 6-tab prototype served at `/` and `/studio`.
2. **`web-console/`:** Standalone 5-page enterprise React prototype served at `/console` and `/web-console`.
3. **`keelway-ui` Wireframes:** 73 locked Figma wireframes defining a 4-rail Sovereign Agent IDE (`Tasks`, `Files`, `Record`, `Settings`), alongside an exploratory `01c` variant testing a persistent right-hand Gate Rail.

Maintaining parallel frontends introduced UI drift against FastAPI `/v1/*` routes, inconsistent token semantics compared to `website/src/app/globals.css`, and risk of separating human-in-the-loop P-10 authorization from the exact diff or command under review.

## Decisions

1. **Single React 19 Sovereign Frontend (`dev-app/` → `core/dev_app_dist/`):**
   - Consolidate the developer IDE and v1.1 enterprise control plane into one React 19 + TypeScript + Tailwind CSS + Radix UI application in `dev-app/`, compiled via Vite (`base: "/app/"`) into static `'self'` assets under `core/dev_app_dist/`.
   - Serve the compiled bundle from FastAPI (`core/main.py`) at `/app` and `/app/assets/*` under strict `_STUDIO_CSP` (`default-src 'self'; script-src 'self'`), `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer`, with zero third-party script, stylesheet, or font CDNs (`NIST SP 800-53 SC-7`).
   - Default `keelway dev` and `keelway desktop` in `cli.py` to `/app` whenever `core/dev_app_dist/index.html` is present.

2. **Permanent Rejection of `01c` Right Gate Rail in Favor of Inline P-10 Cards:**
   - Reject the `01c` persistent right-hand Gate Rail exploration permanently.
   - Standardize 100% on inline `P-10` human-only approval cards (`02a` File Edit, `02b` Shell Command, `02c` Click-Only Network/Deploy & Regulated `CRE-231`/`CRE-42`) embedded directly inside the `Tasks` thread so human judgment never separates from the unified diff or command preview.
   - Support inline `Edit request` overrides with automatic safety escalation from Variant B to click-only Variant C whenever an edited command introduces outbound network or publish flags (`curl`, `wget`, `ssh`, `scp`, `--publish`, `npm publish`, `docker push`), minting one-off execution only (`Allow always` suppressed).

3. **Harmonized Website Palette + `Tokens Rev 4` 5-Way Semantic Disambiguation:**
   - Preserve marketing website obsidian/alabaster surfaces, self-hosted `Inter` + `JetBrains Mono` (`tabular-nums`), and Brand Teal `#2DD4BF` / `#0B655D`, while enforcing **5-way status disambiguation** so P-10 human gates never share a hue with general warnings:
     1. `--status-ok` (`#4ADE80` / `#276B3D`): Verified test/build exit `0` and cryptographic `Chain verified` only.
     2. `--attn-ochre` (`#F9AE78` / `#924B02`): Reserved **exclusively** for P-10 `Needs approval`.
     3. `--status-warning` (`#E3BC56` / `#785C00`): Prompt/model drift, `Not saved`, `Cloud used (n)`, and spend `>80%`.
     4. `--status-running` (`#6FB1F2` / `#1D5FA6`): Active background execution.
     5. `--red-danger` (`#F87171` / `#B91C1C`): Hard faults, broken audit chains, and policy denials.
   - **Flagged Deviations from `keelway/website`:**
     - Add `--bg-chrome` (`#0D1218` / `#ECEFF2`) for the `48px` 4-rail + `24px` status bar and `--bg-code` (`#090D12` / `#F3F6F9`) for code/diff wells.
     - Narrow Brand Teal strictly to brand identity, primary CTAs, active rail indicators, focus rings, and `AI`/`OpenCore` provenance.
     - Lift `--fg-dim` (`#8291A0` dark `5.14:1` / `#5A6775` light `5.41:1`) and `--border-control` (`#586574` dark `3.05:1` / `#7C8897` light `3.60:1`) to satisfy WCAG 2.2 AA (`1.4.3` & `1.4.11`).
     - Shift typography scale from `16px` marketing prose to `13px/18px` UI body and `12.5px/20px` code across Compact (`24px`), Default (`28px`), and Comfortable (`32px`) density modes.
     - Tighten radii to `4px` / `6px` / `10px` and strip `.blueprint-surface` and `.frame-crosshair` from workspace canvases to prevent diff/editor moiré.
     - Add `2px dashed var(--border-focus)` programmatic focus styling (`WCAG 2.4.11`) for `⌘⇧A` P-10 heading navigation.

4. **Epistemic Honesty & Non-Negotiable Safety Invariants:**
   - Render truthful unmeasured egress copy (`Offline (setting) · sent: unmeasured`) until kernel byte counters are active.
   - Enforce `"Only you can approve"` across P-10 cards and `"Approvals are never run from here"` in the `⌘K` Command Palette (`⌘K` navigates to pending gates and never executes approvals).
   - Enforce `[data-reduce-motion="true"]` static overrides and the 4-badge Labs epistemic grammar (`[Simulated]`, `[Estimated]`, `[Prototype]`, `[Live]`).

5. **Zero-Regression Backward Compatibility:**
   - Preserve `/`, `/studio`, `/console`, and `/web-console` in `core/main.py` untouched for existing Studio and proof-strip contracts.
   - Provide `--legacy-studio` on `keelway dev` and `keelway desktop` to launch `/` on demand.

## Consequences & Verification Gates

- **Positive:** Eliminates split frontend architectures, binds all 11 screens (`Tasks`, inline `P-10`, `Review Changes` + `Logs/Terminal/Network`, `Files`, `Record` 7-column ledger + `360px` inspector, `⌘K`, and `Settings` for Permissions/Manifests, Models/4D Routing, Governance/Keys/Spend, Network/Appearance/Labs) to live FastAPI routes, and enforces zero-CDN sovereignty.
- **Automated Gate Enforcement (`scripts/verify_engineering_gates.sh` Step `[8/8]`):**
  - `pytest tests/test_dev_app.py`: Verifies `/app` HTTP 200, `_STUDIO_CSP` (`default-src 'self'`, `script-src 'self'`), `nosniff`, `no-referrer`, zero forbidden CDN domains, JS/CSS bundle epistemic strings and tokens, SPA subpath routing (`/app/settings`), strict `404` on missing `/app/assets/*` chunks, untouched `/studio`, and `cli.py dev --legacy-studio`.
  - `cd dev-app && npm run typecheck && npm test`: Enforces strict TypeScript compilation plus Vitest + `axe-core` WCAG 2.2 AA accessibility and P-10 interaction invariants.
