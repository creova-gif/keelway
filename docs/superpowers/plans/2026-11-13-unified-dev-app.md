# Keelway Unified Sovereign Dev App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and ship the unified React 19 + TypeScript + Tailwind CSS + Radix UI Sovereign Dev App (`keelway/dev-app/` → mounted at `/app` on `127.0.0.1:7420` via `cli.py dev` under strict `'self'` CSP), implementing `ADR-UI-001`, `Tokens Rev 4`, all 11 specified screens, inline P-10 human-only gates, and WCAG 2.2 AA accessibility without breaking any existing engineering gate.

**Architecture:** A standalone Vite 6 + React 19 + TypeScript 5 frontend workspace in `keelway/dev-app/` compiles deterministic, zero-CDN static assets into `keelway/core/dev_app_dist/`, reusing the self-hosted `Inter` / `JetBrains Mono` `.woff2` fonts and vendored Monaco bundle already served from `/studio/assets/`. FastAPI (`core/main.py`) mounts `/app/assets` and serves `/app` with `_STUDIO_CSP` (`default-src 'self'`), `cli.py dev` launches `/app` by default (with `--legacy-studio` fallback), and legacy `/studio` + `/web-console` routes remain backward-compatible so all 700+ existing Python & gate assertions continue passing alongside new Vitest + `vitest-axe` + FastAPI `/app` tests.

**Tech Stack:** React 19, TypeScript 5.7, Vite 6, Tailwind CSS 3.4, `@radix-ui/react-dialog`, `@radix-ui/react-popover`, `@radix-ui/react-tooltip`, `@radix-ui/react-tabs`, Vitest, `@testing-library/react`, `@testing-library/user-event`, `vitest-axe`, FastAPI `StaticFiles` (`core/main.py`).

---

## File Structure & Module Boundaries

All paths below are relative to `keelway/` (always `cd keelway` before running commands):

- **Package & Tooling Root (`dev-app/`):**
  - Create: `dev-app/package.json` — React 19, Radix UI, Tailwind, Vite, TypeScript, Vitest, Testing Library, `vitest-axe` scripts (`dev`, `build`, `typecheck`, `test`).
  - Create: `dev-app/tsconfig.json` — Strict TypeScript (`noEmit`, `jsx: "react-jsx"`).
  - Create: `dev-app/vite.config.ts` — Builds deterministic static bundle to `../core/dev_app_dist` with `base: "/app/"` and Vitest `jsdom` environment.
  - Create: `dev-app/postcss.config.cjs` & `dev-app/tailwind.config.ts` — Multi-theme (`[data-theme="dark"|"light"]`) & 3-density (`[data-density="compact"|"default"|"comfortable"]`) config.
  - Create: `dev-app/index.html` — Zero-CDN HTML entry preloading `/studio/assets/fonts/inter-latin-wght.woff2` and `/studio/assets/fonts/jetbrains-mono-latin-wght.woff2`.
- **Design System & Primitives (`dev-app/src/styles/` & `dev-app/src/components/ui/`):**
  - Create: `dev-app/src/styles/tokens.css` — `Tokens Rev 4` CSS variables (`--attn-ochre` strictly `Needs approval`; `--status-warning`, `--status-running`, `--status-ok`, `--red-danger`, `--border-control >= 3:1`, `prefers-reduced-motion`, `.kw-badge-simulated`, `.unicode-bidi-isolate`).
  - Create: `dev-app/src/components/ui/SemanticBadge.tsx` — 18 non-color-redundant status, epistemic (`Live`, `Estimated`, hatched `Simulated`, `Prototype`, `No counter yet`), and provenance (`AI`, `OpenCore`, `Frontier`, `Locked`) badges.
  - Create: `dev-app/src/components/ui/Button.tsx` — Density-aware buttons (`primary`, `warning-cta`, `secondary`, `danger`, `danger-ghost`, `ghost`) with `clickOnly` P-10 trusted-event enforcement and `aria-disabled` preview-lock support.
  - Create: `dev-app/src/components/ui/CalloutBanner.tsx` — Zero-auto-dismiss recovery banners (`prompt-drift`, `chain-verified`, `chain-broken`, `runtime-unreachable`, `spend-warn`, `spend-cap`).
- **Typed `/v1/*` API Client & State (`dev-app/src/lib/`):**
  - Create: `dev-app/src/lib/types.ts` — Shared TypeScript interfaces across all 11 screens (`RailSection`, `DensityMode`, `ThemeMode`, `EgressBarMode`, `SidebarTaskItem`, `StepReceiptItem`, `P10ApprovalProposal`, `P10ApprovalDecisionPayload`, `P10ApprovalReceipt`, `RecordLedgerEntry`, `ChainVerificationState`, `AgentManifestItem`, `RoutingExplainResult`, `TenantGovernancePolicy`, `ScopedApiKeyItem`).
  - Create: `dev-app/src/lib/api.ts` — Loopback `?token=` aware fetch & `/v1/ws/studio` WebSocket client with graceful fallback snapshots when running offline or before a task exists.
- **Shell, Palette & Onboarding (`dev-app/src/components/shell/`):**
  - Create: `dev-app/src/components/shell/DevAppShell.tsx` — `48px` 4-icon Rail (`Tasks`, `Files`, `Record`, `Settings`), conditional `240px` Context Sidebar (`Needs approval` pinned top), `F6` / `⌘1–3` / `⌘J` / `⌘⇧A` / desktop-only `⌘⇧R` landmark cycling, and `24px` Honest Status Bar + Radix Egress `Details` Popover + `<768px` Mobile Companion mode.
  - Create: `dev-app/src/components/shell/CommandPalette.tsx` — `⌘K` Radix Dialog (`>`, `#`, `@`, `/` prefix modes) enforcing `"Approvals are never run from here"`.
  - Create: `dev-app/src/components/shell/OnboardingModal.tsx` — Screen 01 2-Step First-Run Onboarding (Step 1 Orla honest defaults; Step 2 `/v1/workspace/open` + `/v1/system/doctor` Seatbelt/Bubblewrap & OpenCore readiness check).
- **Screens (`dev-app/src/components/screens/`):**
  - Create: `dev-app/src/components/screens/P10ApprovalCard.tsx` — Screen 03 inline P-10 gate (`02a` file edit, `02b` command, `02c` click-only network/deploy, preview-loading lock, `Edit request` inline override with automatic B→C network flag escalation, AT-safe 2-step keyboard deploy confirmation, Radix `Allow always (scoped)` rule picker, `Deny` reason subform, and `28px` collapsed `Record #seq` receipt).
  - Create: `dev-app/src/components/screens/TasksWorkspace.tsx` — Screen 02 & Screen 04 (`Plan` auto-collapsing card, collapsible `[Ready]` vs `[Passed]`/`[Failed]` step receipts, `⌘↵`-isolated `AgentComposer`, `520px` `Review changes` right `aside` with `Keep changes` / `Revert` / `Ask for changes`, and `300px` `Logs | Terminal | Network` bottom drawer).
  - Create: `dev-app/src/components/screens/FilesWorkspace.tsx` — Screen 05 (`Tree | Changes | Symbols` `240px` sidebar, self-hosted `/studio/assets/monaco/vs/loader.js` bridge with CSP-safe `<textarea>` fallback & `Escape` Tab-trap exit, `Not saved · disk full` recovery bar, `AI #seq` provenance gutter, Unified/Split diff toggle, and `Open in VS Code`).
  - Create: `dev-app/src/components/screens/RecordAuditLedger.tsx` — Screen 06 (`0px` left sidebar, `Verify chain` intact/broken banner, `Export…` bundle trigger, 6-dimension filter + search bar, 7-column SHA-256 table, and `360px` `Entry #seq` 4D Provenance & Merkle/Hash Inspector).
  - Create: `dev-app/src/components/screens/SettingsWorkspace.tsx` — Screens 08–11 (`240px` Settings sub-nav + `Permissions & keelway.agent/v1 Manifests`, `Models & 4D Routing /v1/routing/explain`, `Governance, SQLite WAL & kw_live_* Spend Caps`, `Network & Egress Alt+A`, `Appearance & 3-Up Live Density Preview`, and `Labs` hatched `[Simulated]` / `[Estimated]` / `[Prototype]` / `[Live]` bento workbench).
  - Create: `dev-app/src/App.tsx` & `dev-app/src/main.tsx` — Root state orchestrator wiring URL query (`?token=`, `?section=`, `?companion=1`), theme/density/locale (`dir="ltr"|"rtl"`), WebSocket events, and all screens.
- **Frontend & Backend Tests + Engineering Gates:**
  - Create: `dev-app/src/test/setup.ts` — Vitest DOM + `ResizeObserver`/`matchMedia` shims + `vitest-axe` matchers.
  - Create: `dev-app/src/__tests__/tokens-and-badges.test.tsx` — Verifies `Ready` != `Passed`, hatched `Simulated` badge, `Not saved` non-dot label, and `Tokens Rev 4` theme/density toggles.
  - Create: `dev-app/src/__tests__/shell-and-palette.test.tsx` — Verifies `F6` landmark order, `⌘⇧R` unbound on web (`isDesktopApp={false}`), Honest Status Bar states (`sent: unmeasured`), and `⌘K` `"Approvals are never run from here"`.
  - Create: `dev-app/src/__tests__/p10-approval-safety.test.tsx` — Verifies zero focus-steal on async P-10 mount, `⌘↵` composer isolation, `⌘⇧A` heading-first focus, preview-loading lock, `02c` network/deploy no-`Allow always` + no-chord + AT-safe 2-step keyboard confirm, `Edit request` `curl`/`git push` escalation to Variant C, and `axe` zero violations across Dark, Light, and `dir="rtl"`.
  - Create: `dev-app/src/__tests__/files-record-settings.test.tsx` — Verifies `Files` `Not saved` recovery & `Escape` tab-trap exit, `Record` 7-column hash chain & broken `#1279` alert, `Permissions` `p-13 → p-14` drift banner + Manifest JSON validator, `4D Routing` `privacy="private"` fail-closed proof, `kw_live_*` one-time reveal gate, and `Labs` `[Simulated]` → `[Live]` upgrade.
  - Create: `docs/decisions/ADR-UI-001-unified-dev-app.md` — Canonical Architecture Decision Record in repository docs.
  - Modify: `core/main.py` — Mount `/app/assets` and serve `/app` with `_STUDIO_CSP` while keeping `/`, `/studio`, and `/web-console` 100% compatible with existing tests.
  - Modify: `cli.py` — Add `--legacy-studio` flag to `dev` parser and default `cmd_dev` launch URL to `/app` when `core/dev_app_dist/index.html` exists.
  - Create: `tests/test_dev_app.py` — FastAPI ASGI tests verifying `/app` `200 OK`, `_STUDIO_CSP` (`default-src 'self'`), zero external CDN links, self-hosted `/app/assets/*` bundle serving, and honest `unmeasured` baseline.
  - Modify: `scripts/verify_engineering_gates.sh` — Add `dev-app` typecheck + Vitest safety/a11y suite + `tests/test_dev_app.py` to the canonical engineering verifier.

---

### Task 1: Scaffold `keelway/dev-app` Workspace, `Tokens Rev 4` Styles, UI Primitives & Typed `/v1/*` Client

**Files:**
- Create: `keelway/dev-app/package.json`
- Create: `keelway/dev-app/tsconfig.json`
- Create: `keelway/dev-app/vite.config.ts`
- Create: `keelway/dev-app/postcss.config.cjs`
- Create: `keelway/dev-app/tailwind.config.ts`
- Create: `keelway/dev-app/index.html`
- Create: `keelway/dev-app/src/styles/tokens.css`
- Create: `keelway/dev-app/src/lib/types.ts`
- Create: `keelway/dev-app/src/lib/api.ts`
- Create: `keelway/dev-app/src/components/ui/SemanticBadge.tsx`
- Create: `keelway/dev-app/src/components/ui/Button.tsx`
- Create: `keelway/dev-app/src/components/ui/CalloutBanner.tsx`
- Create: `keelway/dev-app/src/test/setup.ts`
- Test: `keelway/dev-app/src/__tests__/tokens-and-badges.test.tsx`

- [ ] **Step 1: Create `dev-app` package, TypeScript, Vite, PostCSS, Tailwind & HTML entry files**

Create `keelway/dev-app/package.json`:
```json
{
  "name": "@keelway/dev-app",
  "version": "1.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --port 5174",
    "build": "tsc --noEmit && vite build",
    "typecheck": "tsc --noEmit",
    "test": "vitest run"
  },
  "dependencies": {
    "@radix-ui/react-dialog": "^1.1.6",
    "@radix-ui/react-popover": "^1.1.6",
    "@radix-ui/react-tabs": "^1.1.3",
    "@radix-ui/react-tooltip": "^1.1.8",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.2.0",
    "@testing-library/user-event": "^14.6.1",
    "@types/node": "^22.13.0",
    "@types/react": "^19.0.8",
    "@types/react-dom": "^19.0.3",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "axe-core": "^4.10.2",
    "jsdom": "^26.0.0",
    "postcss": "^8.5.2",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.7.3",
    "vite": "^6.1.0",
    "vitest": "^3.0.5",
    "vitest-axe": "^0.1.0"
  }
}
```

Create `keelway/dev-app/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  base: "/app/",
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  build: {
    outDir: path.resolve(__dirname, "../core/dev_app_dist"),
    emptyOutDir: true,
    sourcemap: false,
    assetsDir: "assets",
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

Create `keelway/dev-app/index.html` using strictly local `/studio/assets/fonts/*` preloads (zero external CDNs).

- [ ] **Step 2: Write the failing Vitest test for `Tokens Rev 4` badges, buttons & callout banners**

Create `keelway/dev-app/src/__tests__/tokens-and-badges.test.tsx` asserting:
1. `<SemanticBadge kind="ready" />` renders `"Ready"` with neutral `text-fg-muted` styling (never green `text-ok`), whereas `<SemanticBadge kind="passed" />` renders `"Passed"` with `text-ok` and `"✓"`.
2. `<SemanticBadge kind="simulated" />` applies `.kw-badge-simulated` diagonal hatch styling and `"Simulated"` text.
3. `<SemanticBadge kind="needs-approval" />` uses `text-ochre`, while `<SemanticBadge kind="reconfirm" />` and `<SemanticBadge kind="not-saved" detail="disk full" />` use `text-warning` (`Not saved · disk full`).
4. `<Button clickOnly shortcutHint="⌘⇧Y">` omits the `<kbd>` shortcut hint and ignores untrusted synthetic events while firing on trusted activation.

- [ ] **Step 3: Install dependencies and verify test fails initially**

Run: `cd keelway/dev-app && npm install && npm test`
Expected: FAIL (`Cannot find module '../components/ui/SemanticBadge'`).

- [ ] **Step 4: Implement `tokens.css`, `tailwind.config.ts`, `types.ts`, `api.ts`, `SemanticBadge.tsx`, `Button.tsx`, and `CalloutBanner.tsx`**

Implement the exact `Tokens Rev 4` CSS variables (`@font-face` pointing to `/studio/assets/fonts/inter-latin-wght.woff2` and `/studio/assets/fonts/jetbrains-mono-latin-wght.woff2`), `tailwind.config.ts`, typed `/v1/*` client (`api.ts`), and all three UI primitives.

- [ ] **Step 5: Run Vitest & `tsc` to verify Task 1 passes**

Run: `cd keelway/dev-app && npm run typecheck && npm test`
Expected: PASS (`tokens-and-badges.test.tsx` green, `0` TS errors).

- [ ] **Step 6: Commit Task 1**

```bash
cd keelway && git add dev-app/
git commit -m "feat(dev-app): scaffold React 19 workspace, Tokens Rev 4 system, and UI primitives"
```

---

### Task 2: Implement 4-Rail `DevAppShell`, Honest `24px` Status Bar, `⌘K` Command Palette & 2-Step First-Run Onboarding

**Files:**
- Create: `keelway/dev-app/src/components/shell/DevAppShell.tsx`
- Create: `keelway/dev-app/src/components/shell/CommandPalette.tsx`
- Create: `keelway/dev-app/src/components/shell/OnboardingModal.tsx`
- Test: `keelway/dev-app/src/__tests__/shell-and-palette.test.tsx`

- [ ] **Step 1: Write the failing tests for Shell Landmarks, Honest Status Bar, `⌘K` Non-Approval Guardrail & Onboarding**

Create `keelway/dev-app/src/__tests__/shell-and-palette.test.tsx` testing:
1. **4-Rail + `Needs approval` Queue Pinning:** Tasks with `status === "needs_approval"` automatically sort above `running`/`queued` tasks in `<aside aria-label="Tasks">`.
2. **`F6` & `⌘1–3` Landmark Cycling + Browser Chord Safety:** Pressing `F6` cycles `Primary/Sidebar` → `Main` → `[Review when open]` → `[Logs when open]` → `Status bar`. Pressing `Meta+Shift+R` with `isDesktopApp={false}` does **not** call `preventDefault()`, whereas `isDesktopApp={true}` navigates to `"record"`.
3. **Honest Status Bar (`07`):** `unmeasured` renders `"Offline (setting)"`, `"sent: unmeasured"`, and `"No counter yet"` (never `"0 B sent"`). `connected_warning` renders neutral `"Connected"` + warning `"Cloud used (2)"` and opens the Radix `"Data sent this session"` popover on clicking `"Details"`.
4. **`⌘K` Command Palette (`05`):** Supports `>`, `#`, `@`, `/` prefix filtering, renders `"Approvals are never run from here"`, and exposes zero `Allow once` / `Allow always` / `Deny` actions. Selecting a `Needs approval` task navigates to that task without approving it.
5. **2-Step First-Run Onboarding (`12` + Step 2):** Step 1 displays Orla's exact 3 honest default cards (`Local · coder-7b v2.5.1`, `Ask every time`, `Offline (setting) — Network use isn't measured yet`); Step 2 validates workspace folder + 3-row `/v1/system/doctor` sandbox check.

- [ ] **Step 2: Run Vitest to confirm failure**

Run: `cd keelway/dev-app && npx vitest run src/__tests__/shell-and-palette.test.tsx`
Expected: FAIL (`Failed to resolve import '../components/shell/DevAppShell'`).

- [ ] **Step 3: Implement `DevAppShell.tsx` (including `<768px` Companion Tab Bar), `CommandPalette.tsx`, and `OnboardingModal.tsx`**

Implement all three components using `@radix-ui/react-dialog`, `@radix-ui/react-popover`, and `@radix-ui/react-tooltip`, logical RTL CSS classes (`border-s-2`, `ps-*`, `pe-*`), and `<code dir="ltr" className="unicode-bidi-isolate">`.

- [ ] **Step 4: Run Vitest & `tsc` to verify Task 2 passes**

Run: `cd keelway/dev-app && npm run typecheck && npm test`
Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
cd keelway && git add dev-app/src/components/shell dev-app/src/__tests__/shell-and-palette.test.tsx
git commit -m "feat(dev-app): add 4-rail DevAppShell, honest status bar, Cmd+K palette, and 2-step onboarding"
```

---

### Task 3: Implement Inline `P10ApprovalCard` & `TasksWorkspace` (`Plan`, Step Receipts, `Review Changes` `520px`, `Logs / Terminal / Network` `300px`)

**Files:**
- Create: `keelway/dev-app/src/components/screens/P10ApprovalCard.tsx`
- Create: `keelway/dev-app/src/components/screens/TasksWorkspace.tsx`
- Test: `keelway/dev-app/src/__tests__/p10-approval-safety.test.tsx`

- [ ] **Step 1: Write the failing safety & WCAG 2.2 AA `axe` test suite (`p10-approval-safety.test.tsx`)**

Cover all 5 mandatory CI safety gates from Section 6.4 of the approved spec:
1. **Zero Focus-Steal + `⌘↵` Isolation:** Focus composer `<textarea>`, mount incoming `<P10ApprovalCard>` dynamically → `document.activeElement` remains composer `<textarea>`, polite live announcer updates, and pressing `Meta+Enter` submits the composer message without calling `onSubmitDecision`.
2. **`⌘⇧A` Heading-First Focus:** Trigger jump → `document.activeElement` is `<h3 tabIndex={-1} data-programmatic-focus="true">`, never `Allow once`.
3. **Preview-Loading Lock (`10b`):** When `previewStatus="loading"`, `Allow once` has `aria-disabled="true"` and rejects clicks/`⌘⇧Y`, while `Deny` and `Edit request` work.
4. **`02c` Network/Deploy + `Edit Request` B→C Escalation + AT-Safe 2-Step Confirm:**
   - On `kind="network_deploy"`, `Allow always (scoped)` is absent from the DOM, `⌘⇧Y` / `⌘⇧N` do nothing, and keyboard activation (`detail === 0`) on focused `Allow once` opens the untimed `"Confirm external send"` inline bar before dispatching.
   - On `kind="command"`, clicking `Edit request` and changing `npm test` to `npm test && curl https://evil.example` escalates the card to `"Network + command (escalated by edit)"`, hides `Allow always (scoped)`, disables `⌘⇧Y`, and marks the resulting receipt `"modified by you"`.
5. **Dual-Theme + RTL `axe-core` Audit:** Zero WCAG 2.2 AA violations across `dark`, `light`, and `dir="rtl"`.

- [ ] **Step 2: Run Vitest to confirm failure**

Run: `cd keelway/dev-app && npx vitest run src/__tests__/p10-approval-safety.test.tsx`
Expected: FAIL (`Cannot find module '../components/screens/P10ApprovalCard'`).

- [ ] **Step 3: Implement `P10ApprovalCard.tsx` and `TasksWorkspace.tsx`**

Implement:
- `P10ApprovalCard.tsx` (all 3 variants, preview lock, `Edit request` with `NETWORK_ESCALATION_PATTERN` B→C escalation, Radix `Allow always (scoped)` rule picker bound to `modelId + promptVersion`, `Deny` optional reason tray, AT-safe 2-step keyboard deploy confirmation, and collapsed `28px` `Record #seq` receipt).
- `TasksWorkspace.tsx` (Task header with `Review changes`, `Logs ⌘J`, `Stop ⌘.`; `PlanCard` that auto-collapses to 1 line while a P-10 card is pending; collapsible `StepReceipt` rows enforcing `[Ready]` on `Read`/`Searched`/`Edited` and `[Passed]`/`[Failed]` only on test/verifier runs; `AgentComposer` with `/` slash menu and `⌘↵` isolation; `520px` `Review changes` right pane with `[✓ Keep changes]`, `[Revert all]`, and `Ask for changes` line-citation pre-fill; and `300px` `Logs | Terminal | Network` bottom drawer wired to `/v1/terminal/exec` and `/v1/studio/airgap`).

- [ ] **Step 4: Run Vitest & `tsc` to verify Task 3 passes**

Run: `cd keelway/dev-app && npm run typecheck && npm test`
Expected: PASS (all P-10 safety gates + `vitest-axe` Dark/Light/RTL green).

- [ ] **Step 5: Commit Task 3**

```bash
cd keelway && git add dev-app/src/components/screens/P10ApprovalCard.tsx dev-app/src/components/screens/TasksWorkspace.tsx dev-app/src/__tests__/p10-approval-safety.test.tsx
git commit -m "feat(dev-app): implement inline P-10 approval gates, Tasks workspace, Review pane, and Logs/Terminal drawer"
```

---

### Task 4: Implement `FilesWorkspace` (Tree/Changes/Symbols, Zero-CDN Monaco + `<textarea>` Fallback, `Not saved` Recovery & Unified/Split Diff)

**Files:**
- Create: `keelway/dev-app/src/components/screens/FilesWorkspace.tsx`
- Test: `keelway/dev-app/src/__tests__/files-record-settings.test.tsx` (Part 1: Files suite)

- [ ] **Step 1: Write failing tests for `FilesWorkspace`**

Add `describe("FilesWorkspace (Screen 05)")` in `keelway/dev-app/src/__tests__/files-record-settings.test.tsx` asserting:
1. `Tree | Changes | Symbols` switcher renders workspace files with Git badges (`M`, `A`), dirty file counts, and AST symbols.
2. When a save fails (`saveError="disk full"`), the active file tab displays the explicit `[Not saved]` + `"disk full"` badge (never an unlabelled dot) and mounts `[Retry save ⌘S]` + `[Save as...]`.
3. In `<textarea>` fallback mode (used in jsdom / strict CSP without workers), pressing `Tab` indents by 2 spaces, while pressing `Escape` exits `Tab`-capture mode so the next `Tab` moves focus to the next control (WCAG 2.1.2 No Keyboard Trap).
4. Switching `[Code] | [Unified diff] | [Split diff]` renders dual-cue `+`/`-` diff lines and `AI #1283` provenance gutter markers.

- [ ] **Step 2: Run Vitest to confirm failure**

Run: `cd keelway/dev-app && npx vitest run src/__tests__/files-record-settings.test.tsx`
Expected: FAIL (`Cannot find module '../components/screens/FilesWorkspace'`).

- [ ] **Step 3: Implement `FilesWorkspace.tsx`**

Wire `GET /v1/files/tree`, `GET /v1/files/content`, `POST /v1/files/save`, `GET /v1/studio/diff`, `GET /v1/codebase/symbols`, and `POST /v1/editor-sync/open-in-editor`, plus lazy self-hosted `/studio/assets/monaco/vs/loader.js` attachment (`keelway-dark` / `keelway-light` token themes) with seamless `<textarea>` fallback (`Escape` exits Tab-indentation trap) and `[Commit N files...]` modal (`/v1/git/proposal` → `/v1/git/commit`).

- [ ] **Step 4: Run Vitest & `tsc` to verify Task 4 passes**

Run: `cd keelway/dev-app && npm run typecheck && npm test`
Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
cd keelway && git add dev-app/src/components/screens/FilesWorkspace.tsx dev-app/src/__tests__/files-record-settings.test.tsx
git commit -m "feat(dev-app): implement Files explorer, zero-CDN Monaco/fallback editor, and Not-saved recovery"
```

---

### Task 5: Implement `RecordAuditLedger` (7-Column SHA-256 Chain, 6-Filter Bar, Intact/Broken Verification & `360px` 4D Provenance Inspector)

**Files:**
- Create: `keelway/dev-app/src/components/screens/RecordAuditLedger.tsx`
- Modify: `keelway/dev-app/src/__tests__/files-record-settings.test.tsx` (Part 2: Record suite)

- [ ] **Step 1: Add failing tests for `RecordAuditLedger`**

Extend `keelway/dev-app/src/__tests__/files-record-settings.test.tsx` with `describe("RecordAuditLedger (Screen 06)")` asserting:
1. Renders all 7 canonical columns (`When (ET)`, `Who`, `What`, `Model`, `Approval`, `Outcome`, `Integrity`), displaying `model_id + version + prompt_version` (`coder-7b 2.5.1 · p-14`) and human-only `Approval` (`Allow once · you`).
2. Intact state shows green `"Chain verified · ... entries · no gaps"`, whereas broken chain state (`status: "broken", brokenAtSeq: 1279`) renders `role="alert"` `"Chain broken at entry #1279"` with `"Open entry #1279"` selecting `#1279` in the `360px` Inspector.
3. Selecting an entry opens the `360px` Inspector showing `Prompt` (`system prompt hash`), `4D Route` receipt, `hash` + `prev` link (`(#1282)` clickable jump), and `[Open diff in Review]`; pressing `Escape` closes the inspector.

- [ ] **Step 2: Run Vitest to confirm failure**

Run: `cd keelway/dev-app && npx vitest run src/__tests__/files-record-settings.test.tsx`
Expected: FAIL (`Cannot find module '../components/screens/RecordAuditLedger'`).

- [ ] **Step 3: Implement `RecordAuditLedger.tsx`**

Implement `RecordAuditLedger.tsx` wired to `GET /v1/audit`, `GET /v1/audit/verify`, `GET /v1/audit/merkle/proof/{seq}`, and `GET /v1/audit/export` (downloading JSONL + CSV + standalone verifier bundle).

- [ ] **Step 4: Run Vitest & `tsc` to verify Task 5 passes**

Run: `cd keelway/dev-app && npm run typecheck && npm test`
Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
cd keelway && git add dev-app/src/components/screens/RecordAuditLedger.tsx dev-app/src/__tests__/files-record-settings.test.tsx
git commit -m "feat(dev-app): implement Record SHA-256 hash-chained ledger and 360px 4D provenance inspector"
```

---

### Task 6: Implement Unified `SettingsWorkspace` (Screens 08–11) & Root `App.tsx` Orchestrator

**Files:**
- Create: `keelway/dev-app/src/components/screens/SettingsWorkspace.tsx`
- Create: `keelway/dev-app/src/App.tsx`
- Create: `keelway/dev-app/src/main.tsx`
- Modify: `keelway/dev-app/src/__tests__/files-record-settings.test.tsx` (Part 3: Settings & App integration suite)

- [ ] **Step 1: Add failing tests for `SettingsWorkspace` (Screens 08–11) & `App.tsx`**

Extend `keelway/dev-app/src/__tests__/files-record-settings.test.tsx` with `describe("SettingsWorkspace & App Integration (Screens 08-11)")` asserting:
1. **Screen 08 (`Permissions & Agent Manifests`):** Renders `Prompt version changed: p-13 → p-14` drift banner with `[Re-confirm]` action, immutable `[Always ask]` rows (`Network and deploy`, `Domain-regulated actions CRE-231 / CRE-42`) + `[Locked]` `"Only a person, at this keyboard"`, and `keelway.agent/v1` Manifest Registry table + Live JSON Inspector (`/v1/studio/manifests/inspect`).
2. **Screen 09 (`Models & 4D Hybrid Routing`):** Renders OpenCore weights (`/v1/opencore/weights`) and the Zero-Token 4D Dry-Run Simulator (`POST /v1/routing/explain`), proving `privacy="private"` against an external open-weight cloud endpoint renders a fail-closed `Blocked` receipt (`data_boundary=external_vendor_api`).
3. **Screen 10 (`Governance, Tenant Keys & Spend Caps`):** Renders `SQLite WAL` persistence strip, `DataResidencyZone` (`local_only`, `africa_sovereign`, `eu_sovereign`, `global`), USD spend meters + `fallback_to_opencore_on_budget_exceeded` (`keelway-core:7b`), and one-time `kw_live_*` key reveal modal whose `[Done]` button stays locked until `"I have saved this key"` is checked.
4. **Screen 11 (`Network & Egress`, `Appearance & Density`, `Labs`):** Renders Orla's exact copy (`"Set to keep your use on this machine. Network use isn't measured yet."`) + `Alt+A` Air-Gap toggle, switches `data-theme` (`dark`/`light`) and `data-density` (`compact`/`default`/`comfortable`) live on `document.documentElement`, and upgrades a `Labs` experiment card from hatched `[Simulated]` to `[Live]` after running a live benchmark (`/v1/eval/benchmark` / `/v1/eval/swarm`).

- [ ] **Step 2: Run Vitest to confirm failure**

Run: `cd keelway/dev-app && npx vitest run src/__tests__/files-record-settings.test.tsx`
Expected: FAIL (`Cannot find module '../components/screens/SettingsWorkspace'`).

- [ ] **Step 3: Implement `SettingsWorkspace.tsx`, `App.tsx`, and `main.tsx`**

Implement all 6 Settings sub-surfaces (`permissions`, `models`, `governance`, `network`, `appearance`, `labs` + `general` & `keyboard` reference cards) inside `SettingsWorkspace.tsx`, and wire `App.tsx` + `main.tsx` to connect all 11 screens, 8-locale/RTL attribute sync, `/v1/ws/studio` live updates, and `<768px` Mobile Companion mode (`?companion=1` or narrow viewport).

- [ ] **Step 4: Run Vitest, `tsc`, and `vite build` to verify Task 6 passes and compiles static assets cleanly**

Run: `cd keelway/dev-app && npm run typecheck && npm test && npm run build`
Expected: PASS (`0` TS errors, all Vitest suites green, `../core/dev_app_dist/index.html` and `/app/assets/*` emitted).

- [ ] **Step 5: Commit Task 6**

```bash
cd keelway && git add dev-app/ core/dev_app_dist/
git commit -m "feat(dev-app): complete Settings control plane (4D routing, manifests, governance, Labs) and static build"
```

---

### Task 7: Mount `/app` in FastAPI (`core/main.py`) & `cli.py dev`, Record `ADR-UI-001`, and Enforce in `scripts/verify_engineering_gates.sh`

**Files:**
- Create: `keelway/docs/decisions/ADR-UI-001-unified-dev-app.md`
- Modify: `keelway/core/main.py`
- Modify: `keelway/cli.py`
- Create: `keelway/tests/test_dev_app.py`
- Modify: `keelway/scripts/verify_engineering_gates.sh`

- [ ] **Step 1: Write the failing FastAPI ASGI test (`tests/test_dev_app.py`)**

Create `keelway/tests/test_dev_app.py`:
```python
import re
import pytest
from httpx import AsyncClient, ASGITransport
from core.main import app


@pytest.mark.asyncio
async def test_unified_dev_app_served_under_strict_self_csp():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/app")
        assert resp.status_code == 200
        assert "Content-Security-Policy" in resp.headers
        csp = resp.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

        html = resp.text
        assert "Keelway" in html
        assert "/app/assets/" in html
        for forbidden_cdn in (
            "cdn.tailwindcss.com",
            "cdnjs.cloudflare.com",
            "fonts.googleapis.com",
            "fonts.gstatic.com",
            "unpkg.com",
            "jsdelivr.net",
        ):
            assert forbidden_cdn not in html

        js_match = re.search(r'src="(/app/assets/[^"]+\.js)"', html)
        assert js_match is not None, "Compiled /app/assets/*.js bundle link missing"
        bundle_resp = await client.get(js_match.group(1))
        assert bundle_resp.status_code == 200
        assert "sent: unmeasured" in bundle_resp.text
        assert "Approvals are never run from here" in bundle_resp.text
        assert "Only you can approve" in bundle_resp.text
```

- [ ] **Step 2: Run pytest on `tests/test_dev_app.py` to verify it fails (`404 Not Found`)**

Run: `cd keelway && pytest tests/test_dev_app.py -v`
Expected: FAIL (`assert 404 == 200`).

- [ ] **Step 3: Mount `/app` & `/app/assets` in `core/main.py`, add `--legacy-studio` + `/app` default to `cli.py dev`, write `ADR-UI-001`, and wire Step `[8/8]` in `scripts/verify_engineering_gates.sh`**

1. In `core/main.py`:
   - Resolve `dev_app_dir = Path(__file__).resolve().parent / "dev_app_dist"`.
   - If `(dev_app_dir / "assets").exists()`, mount `/app/assets` via `StaticFiles`.
   - Add `@app.get("/app", response_class=HTMLResponse)` and `@app.get("/app/{subpath:path}", response_class=HTMLResponse)` serving `dev_app_dir / "index.html"` with `_STUDIO_CSP`, `X-Content-Type-Options: nosniff`, and `Referrer-Policy: no-referrer` (preserving `/`, `/studio`, `/console`, and `/web-console` untouched so `tests/test_studio.py`, `tests/test_proof_strip_ux.py`, and `tests/test_studio_manifest_panel.py` remain 100% green).
2. In `cli.py`:
   - Add `--legacy-studio` boolean flag to the `dev` subparser and `cmd_dev(..., legacy_studio: bool = False)`.
   - Default `cmd_dev` launch path to `/app` whenever `core/dev_app_dist/index.html` exists and `not legacy_studio`.
3. Create `docs/decisions/ADR-UI-001-unified-dev-app.md` recording `ADR-UI-001`.
4. Update `scripts/verify_engineering_gates.sh` (`[1/8]`..`[8/8]`) to run `tests/test_dev_app.py` plus `(cd dev-app && npm run typecheck && npm test)` when `dev-app/node_modules` is present.

- [ ] **Step 4: Run `tests/test_dev_app.py`, legacy studio tests, and the full `scripts/verify_engineering_gates.sh` suite**

Run: `cd keelway && ./scripts/verify_engineering_gates.sh`
Expected: PASS (`ALL KEELWAY ENGINEERING GATES PASSED [100% VERIFIED]`).

- [ ] **Step 5: Commit Task 7**

```bash
cd keelway && git add core/main.py cli.py docs/decisions/ADR-UI-001-unified-dev-app.md tests/test_dev_app.py scripts/verify_engineering_gates.sh
git commit -m "feat(studio): mount unified React 19 Sovereign Dev App at /app under strict CSP and wire CI gates"
```

---

## Spec Coverage & Self-Review Checklist

1. **UX Summary, IA & `ADR-UI-001`:** Covered in Tasks 2, 6, and 7 (`48px` 4-Rail + `240px` Sidebar + `0px` Record sidebar + `docs/decisions/ADR-UI-001-unified-dev-app.md`; `01c` Gate Rail omitted).
2. **All 11 Screens & 6 Canonical States:**
   - Screen 01 (2-Step Onboarding): Task 2 (`OnboardingModal.tsx`).
   - Screen 02 (`Tasks`), Screen 03 (`P-10` + `Edit request` B→C escalation), Screen 04 (`Review changes` `520px` + `Logs/Terminal/Network` `300px`): Task 3.
   - Screen 05 (`Files` + Monaco/`<textarea>` fallback + `Not saved` recovery): Task 4.
   - Screen 06 (`Record` 7-column SHA-256 ledger + `360px` 4D Inspector): Task 5.
   - Screen 07 (`⌘K` Palette w/ non-approval guardrail): Task 2.
   - Screens 08–11 (`Permissions & Manifests`, `Models & 4D Routing`, `Governance & kw_live_*`, `Network & Egress`, `Appearance & 3-Mode Density`, `Labs` hatched `[Simulated]`): Task 6.
3. **Tokens Rev 4 & Flagged Website Deviations:** Covered in Task 1 (`tokens.css` + `tailwind.config.ts`).
4. **WCAG 2.2 AA, AT-Safe `02c` Confirm, 8-Locale/RTL & `<768px` Companion:** Covered across Tasks 2–6 and verified via `vitest-axe` + behavioral safety tests in Tasks 2, 3, 4, 5, and 6.
5. **Gate Integrity:** Existing `/studio` & `/web-console` tests stay 100% intact while `/app` + `dev-app` typecheck/unit/a11y/CSP gates join `scripts/verify_engineering_gates.sh` in Task 7.
