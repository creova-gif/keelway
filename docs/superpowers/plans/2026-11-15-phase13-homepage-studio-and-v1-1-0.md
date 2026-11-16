# Phase 13 — Zero-Install Homepage Golden-Thread Studio Showcase & Official `v1.1.0` Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a zero-install interactive Golden-Thread Studio Showcase (`/#studio-showcase`) directly on `https://kora-sable.vercel.app/` so prospective LangChain / LangGraph switchers experience bidirectional KFlow ↔ Code sync, Flight-Tape scrubbing, Sandbox Blast-Radius radar, and Prompt Regression gating before installing, and cut the synchronized, cryptographically attested **Keelway `v1.1.0` Release**.

**Architecture:** Modular client-side deterministic AST/scrubber studio engine (`website/src/lib/goldenThreadShowcaseEngine.ts`) paired with an accessible, reduced-motion-safe React 19 showcase section (`website/src/components/home/GoldenThreadStudioShowcase.tsx`) mounted on `/`, plus synchronized `1.1.0` release manifests across Python, FastAPI OpenAPI 3.1, TypeScript `@keelway/sdk`, Next.js website, Homebrew formula, CycloneDX 1.5 SBOM workflow, and `CHANGELOG.md`.

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript 5.8 (strict, exhaustive switches, top-level imports only), Tailwind CSS, Framer Motion (`useReducedMotion`), Python 3.11–3.14 / FastAPI, CycloneDX 1.5 SBOM, GitHub Actions Release Automation.

---

### Task 1 (Workstream 13A): Zero-Install Homepage Golden-Thread Studio Engine & Interactive Showcase (`website/`)

**Files:**
- Create: `website/src/lib/goldenThreadShowcaseEngine.ts` *(< 280 lines)*
- Create: `website/src/components/home/GoldenThreadStudioShowcase.tsx` *(< 460 lines)*
- Modify: `website/src/lib/analytics.ts`
- Modify: `website/src/app/page.tsx`
- Modify: `website/src/components/layout/CommandPalette.tsx`
- Modify: `website/src/app/api/search-index/route.ts`

- [ ] **Step 1: Add typed funnel analytics events in `website/src/lib/analytics.ts`**
  Add `"golden_thread_stage_switched"`, `"golden_thread_code_synced"`, `"golden_thread_tape_scrubbed"`, and `"golden_thread_prompt_gated"` to `KeelwayAnalyticsEvent`.

- [ ] **Step 2: Implement pure deterministic Studio Showcase Engine in `website/src/lib/goldenThreadShowcaseEngine.ts`**
  - Top-level imports only; exhaustive `switch` checks (`const _exhaustive: never = ...`) on union discriminants.
  - Export 3 presets:
    1. `langgraph-refund-cycle` (LangGraph `StateGraph` with cyclic loop + `interrupt()` auto-upgraded to `p10_human_gate`)
    2. `pr-security-sentinel` (Multi-agent AST diff & Seatbelt test runner)
    3. `clinical-hipaa-intake` (Local `keelway-core:7b` private zero-egress intake)
  - Export `syncShowcaseCodeToGraph(code: string, presetId: ShowcasePresetId)` and `syncShowcaseGraphToCode(nodes: ShowcaseNode[], edges: ShowcaseEdge[], language: "python" | "typescript")` producing exact 1-based `lineStart` / `lineEnd` AST spans, topological wave coordinates (`x`, `y`), `cycleBackEdges` (`maxIterations: 4`), and deterministic hex `blueprintDigest`.
  - Export `evaluateShowcasePromptGate(candidatePrompt: string)` returning `{ verdict: "PASS" | "BLOCK", score: number, gateRunId: string, gateSha256: string, costDeltaUsd: number, findings: string[] }` (blocking `sk-`, `AKIA`, `ignore previous instructions`, `bypass p-10`, `shell=True`).
  - Export deterministic Flight-Tape waterfall spans + counterfactual fork comparison (`cachedUpstreamSavedUsd`, `$0.00` upstream replay cost) and Seatbelt/Bubblewrap Blast-Radius probes (`ALLOWED` workspace paths vs `BLOCKED` `169.254.169.254` & `~/.ssh/id_ed25519`).

- [ ] **Step 3: Implement `<GoldenThreadStudioShowcase />` in `website/src/components/home/GoldenThreadStudioShowcase.tsx`**
  - Section `id="studio-showcase"` (`aria-labelledby="golden-thread-studio-heading"`).
  - 4-Stage Golden-Thread Pill Stepper (`01 Plan & Import`, `02 Build & Sync Studio`, `03 Scrub & Blast-Radius`, `04 Govern & Ship`) + `Advance Golden-Thread Stage` button.
  - Preset switcher (`LangGraph Refund Cycle`, `Multi-Agent PR Sentinel`, `HIPAA Zero-Egress Triage`).
  - **Stages 01 & 02:** Split-screen Responsive SVG KFlow Canvas (forward topological curves, amber dashed `cycle_back_edges`, clickable nodes, 1-click `Toggle P-10 Human Gate`) ↔ Editable Code & AST Line Inspector (`Python` | `TypeScript @keelway/sdk`, highlighted `Lstart–Lend`, `Sync Code → Graph`, `Copy SDK Code`).
  - **Stages 03 & 04:** Interactive Flame Waterfall Scrubber + `Fork Counterfactual ($0.00 Upstream Cache)` toggle + Seatbelt/Bubblewrap Blast-Radius Radar (`ALLOWED` vs `BLOCKED` probes with `blast-*` receipt) + Inline Prompt Regression Gate (`Evaluate Candidate Prompt` + `Test Adversarial Prompt` quick-fill showing `PASS` -> `BLOCK`) + `pip install keelway==1.1.0 && keelway dev --port 7420` launch bar.
  - Zero occurrences of `"/playground`, third-party CDNs, or forbidden private tokens (`creova-gif`, `kora.git`, `KEEL-`, `Antigravity`, `gstack`, `verify_engineering_gates.sh`).

- [ ] **Step 4: Wire Homepage, CommandPalette & Search Index**
  - Mount `<GoldenThreadStudioShowcase />` in `website/src/app/page.tsx` right after `<CustomerJourneyGrid />`.
  - Add `"Try Golden-Thread Studio Showcase"` (`href: "/#studio-showcase"`) to `BUILTIN_ACTIONS` in `website/src/components/layout/CommandPalette.tsx` while keeping all existing action titles intact.
  - Add `"Golden-Thread Bidirectional Studio Showcase"` (`href: "/#studio-showcase"`) in `website/src/app/api/search-index/route.ts` and update line 101 from `"$39 Pro"` to `"$15 BYOM, $29 Pro"`.

- [ ] **Step 5: Verify Next.js Typecheck & Production Build**
  Run: `cd website && npm run typecheck && npm run build`
  Expected: Exit code `0`, all routes static/dynamic pre-rendered cleanly.

---

### Task 2 (Workstream 13B): Synchronized `v1.1.0` Release Metadata, OpenAPI Export, Changelog & Parity Suite

**Files:**
- Modify: `pyproject.toml`, `core/main.py`, `cli.py`, `core/platform/enterprise_identity_siem.py`, `sdk/typescript/package.json`, `website/package.json`, `Formula/keelway.rb`, `.github/workflows/release-artifacts.yml`, `CHANGELOG.md`
- Modify: `website/product-facts.json` & `website/public/product-facts.json`
- Modify: `website/openapi.json` & `website/public/openapi.json`
- Modify: `tests/test_cli_init_and_banner.py`, `tests/test_phase7_packaging_and_sdk.py`, `tests/test_phase9_enterprise_identity_siem_metrics.py`, `tests/test_website_facts.py`, `scripts/verify_engineering_gates.sh`
- Create: `tests/test_phase13_homepage_studio_and_release.py` *(< 320 lines)*
- Create: `.cursor/skills/verify-keelway/features/homepage-golden-thread-showcase.md`

- [ ] **Step 1: Bump all canonical `1.0.0` version fields to `1.1.0`**
  Update `pyproject.toml`, `core/main.py`, `cli.py` (`keelway init` config), `core/platform/enterprise_identity_siem.py` (`product.version`, `service.version`, `scope.version`), `sdk/typescript/package.json`, `website/package.json`, `Formula/keelway.rb` (`tag: "v1.1.0"`), and `.github/workflows/release-artifacts.yml` (`default: "v1.1.0"`).

- [ ] **Step 2: Prepend `## [1.1.0] — 2026-11-15` in `CHANGELOG.md` & sync `product-facts.json` + `openapi.json`**
  - Document Phases 9–13 in `CHANGELOG.md` (Enterprise OIDC/SCIM 2.0 + 2-of-2 P-10 Quorum + SIEM/OTLP, KBrain + KHub Air-Gapped Mirror, Flight-Tape Debugger + OTel GenAI Wedge + `keelway migrate` LangGraph AST Importer, Golden-Thread Bidirectional KFlow ↔ Code Studio + Blast-Radius Radar + Prompt Gate, and Zero-Install Homepage Studio Showcase).
  - Add `zero_install_homepage_golden_thread_studio_showcase` (`AVAILABLE`, `code_path`: `website/src/components/home/GoldenThreadStudioShowcase.tsx, website/src/lib/goldenThreadShowcaseEngine.ts`, `evidence_test`: `tests/test_phase13_homepage_studio_and_release.py`) and set `"version": "1.1.0"` in both `website/product-facts.json` and `website/public/product-facts.json` (`21` features).
  - Re-export `website/openapi.json` and `website/public/openapi.json` from `core.main:app` (`info.version == "1.1.0"`, `273` paths).

- [ ] **Step 3: Update existing version assertions & write `tests/test_phase13_homepage_studio_and_release.py`**
  - Update `"1.0.0"` -> `"1.1.0"` assertions in `tests/test_cli_init_and_banner.py`, `tests/test_phase7_packaging_and_sdk.py`, `tests/test_phase9_enterprise_identity_siem_metrics.py`, and `tests/test_website_facts.py`.
  - Write `tests/test_phase13_homepage_studio_and_release.py` asserting cross-manifest `1.1.0` parity, `CHANGELOG.md` `[1.1.0]` coverage, `GoldenThreadStudioShowcase.tsx` + `goldenThreadShowcaseEngine.ts` structure/line budgets/privacy hygiene, and wire it into `scripts/verify_engineering_gates.sh`.

- [ ] **Step 4: Run Full Engineering Gates, Cold Browser Verification, Push `main` & Cut Tagged GitHub Release `v1.1.0`**
  - Run `./scripts/verify_engineering_gates.sh` && `(cd website && npm run build)` && cold `control-keelway.mjs` browser verification of `http://127.0.0.1:3199/#studio-showcase`.
  - Commit & push `main`, verify `5/5` green jobs in `ci.yml` + live Vercel `v1.1.0`, tag `v1.1.0`, push `origin v1.1.0`, and verify `.github/workflows/release-artifacts.yml` attaches `keelway-1.1.0-py3-none-any.whl`, `keelway-1.1.0.tar.gz`, `keelway-sbom.cdx.json`, and `SHA256SUMS.txt` to GitHub Release `v1.1.0`.
