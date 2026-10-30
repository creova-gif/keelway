# Kora AI — Senior UI/UX Design System & Front-End Architecture Specification

**Role:** Senior Principal Product Designer & Lead Front-End Architect  
**Design Standard:** Teenage Engineering Tactility × Linear Precision × NASA Mission Control Rigor  
**Compliance Standard:** WCAG 2.1 AA Certified, 0.00 CLS, <50ms INP  
**Target Platform:** Kora Dev Studio (`kora dev`), Kora Mobile (`mobile/`), Kora Web (`website/`)  

---

## 0. Framing & Foundational Assumptions

1. **Brand Identity:** Kora AI is a **Sovereign Agent Computer**, not a conversational toy or autocomplete plugin. The aesthetic is industrial, tactical, and distraction-free: dark obsidian surfaces, hairline borders, monospace telemetry, and physical audio-haptic feedback.
2. **Primary Audience:** 
   - *Enterprise / Defense Engineers:* High security, zero cloud egress tolerance, strict audit trails.
   - *Emerging Market & Global Developers:* Intermittent connectivity, non-USD regional payment rails (M-Pesa, PIX, UPI), consumer laptops (8GB–16GB RAM).
   - *Autonomous Systems Engineers:* Multi-agent coordination, deterministic replay, closed-loop AST repairs.
3. **Tech Stack & Architecture:**
   - *Desktop/Web Studio:* Semantic HTML5, Tailwind CSS token architecture, native Web Audio API oscillators, zero-build vanilla JS / reactive WebSocket state engine.
   - *Mobile Client:* React Native / Expo, native biometrics (`expo-local-authentication`), haptics (`expo-haptics`).

---

## 0.1 Evil Martians Framework for Developer Tool Interfaces

Implemented directly from Evil Martians' research (*"Devs in mind: how to design interfaces for developer tools"*):

### A. The Three Operational Contexts of Developer Work
1. **Immediate Context (The Panel):**
   - *Self-Contained Controls:* Every panel (Diff, Self-Healing, Settlement, Terminal) holds all tools required to finish a unit of work without leaving the view.
   - *Panel Footers:* Sticky action bars at the bottom of panels contain primary action buttons (`Accept & Commit ⌘⏎`, `Generate Intent`, `Test in Isolated Worktree`) and status summaries, removing the need for hunt-and-peck scrolling.
   - *Minimal Scrolling:* Critical telemetry and control buttons are pinned to viewport boundaries.

2. **Intermediate Context (The Application Scope):**
   - *Context Restoration & State Persistence:* Panel layout (`[`, `]`), active tab, audio mute toggle, air-gap state, and scrub positions are automatically persisted to `localStorage` so a reload or tab switch never destroys developer state.
   - *Collapsible Ergonomics:* Left sidebar and right telemetry inspector are collapsible via keyboard (`[` and `]`) or header icons to grant 100% canvas focus when inspecting large unified AST diffs.
   - *Quick Command Palette (`⌘K`):* Instant modal search to jump between tabs, toggle the air-gap shield, or trigger self-healing without touching the mouse.

3. **Broad Context (The OS & Tool Ecosystem):**
   - *Multi-Tool Harmony:* Designed to sit seamlessly alongside VS Code, Neovim, and terminal split windows (supports 50% screen snapping down to 768px without horizontal clipping).
   - *1-Click CLI Interoperability:* Every state (git branch `#f05b0b9`, CLI commands `kora dev`, `kora notify`) has a 1-click copy button with instant toast feedback.

### B. Directional Flow Rules
- **The Top-Down Rule:** Elements positioned *above* strictly control elements *below* (e.g., Tab bar controls the center workspace; file view mode `Unified | Split` controls the diff canvas; Flight scrubber controls the historical frames below it).
- **The Left-to-Right Rule:** Elements on the *left* strictly dictate elements on the *right* (e.g., Selecting a file in the Left Tree renders its diff in the Center Panel; selecting an AST line in the Center Panel updates the Right Telemetry Inspector).

### C. Form Controls & High Data Density
- **No Hidden Dropdowns:** All core state selectors (payment rails, diff views, preset test suites) use **explicit segmented button controls** visible at a single glance.
- **Dual Range Slider + Direct Numeric Input:** The Flight Recorder scrubber pairs a smooth scrub slider with an exact numerical input (`Frame [ 4 ] of 4`), letting developers scrub roughly or jump to an exact integer.
- **Tabular Monospace Alignment:** Monospace numbers utilize `tabular-nums` (`font-variant-numeric: tabular-nums`) to completely eliminate layout jitter during live counter streaming.

---

## 1. UX Foundation: Target Users & Core User Flows

### A. User Personas & Core Jobs-to-be-Done (JTBD)
- **Persona 1: Commander Elena (Defense / SCIF Systems Lead)**
  - *Goal:* Run autonomous refactoring and security audits without a single byte leaving the physical facility.
  - *Friction:* Cloud tools (Cursor, Copilot, ChatGPT) violate federal data residency and classified air-gap rules.
  - *Kora Solution:* One-click cryptographic air-gap kill switch (`AirGapEnforcer`), generating verifiable SHA-256 zero-egress receipts.
- **Persona 2: Dev Tariq (Nairobi Full-Stack Engineer)**
  - *Goal:* Build modern apps with high-level AI pair programming without paying $20/month in USD or getting blocked by international card declines.
  - *Friction:* Stripe rejects local debit cards; subsea fiber cable cuts cause frequent 4-hour internet blackouts.
  - *Kora Solution:* $0.00 local edge model inference via Qwen 2.5 Coder, M-Pesa Daraja STK push micro-payments, and 100% offline immunity.
- **Persona 3: Alex (Open-Source Core Maintainer)**
  - *Goal:* Fix 20 failing CI tests overnight without babysitting prompt hallucinations.
  - *Friction:* AI models propose broken syntax and break other test suites.
  - *Kora Solution:* Closed-Loop AST Self-Healing in disposable Git worktrees with zero-regression verification before merging.

---

### B. Core User Flows & Design Rationales

```
[ FLOW 1: ONBOARDING (<30 SECONDS TO FIRST FLIGHT) ]
User runs: curl -fsSL https://get.kora.ai | sh
       │
       ▼
Auto-detects Hardware (RAM, Metal GPU/CUDA)
       │
       ▼
Checks local Ollama / Binds 4-bit GGUF Model Cache
       │
       ▼
Launches Dev Studio (http://localhost:7420)
       │
       ▼
Success: "Air-Gapped Sovereign Engine Online. 0 Tokens Egressed."
Rationale: Zero signup forms, zero credit card prompts, zero API key configuration.
```

```
[ FLOW 2: PRIMARY TASK COMPLETION (AUTONOMOUS AST REPAIR) ]
Developer instructs: "Heal failing payment suite"
       │
       ▼
System captures traceback & isolates AST Node in Ephemeral Git Worktree
       │
       ▼
Dual-Tone Chime (880Hz ➔ 1760Hz): Zero-Regression Patch Verified
       │
       ▼
Ghost Diff View displays surgical hunk (Green additions / Red deletions)
       │
       ▼
Developer taps [Cmd + Enter] or Biometric Signoff ➔ Merged to Main
Rationale: Human-in-the-loop retains ultimate authority; agent handles dirty mechanics.
```

```
[ FLOW 3: ERROR RECOVERY & TIME-TRAVEL SCRUBBING ]
Agent attempts experimental refactor that causes compiler panic
       │
       ▼
Deterministic Flight Recorder records failure frame with full stack trace
       │
       ▼
Developer drags Flight Scrubber back to Frame 3 (pre-breakage)
       │
       ▼
Taps [⑂ Fork Timeline]: Agent spins up a new isolated worktree branch
Rationale: No destructive rollbacks; developers explore parallel counterfactual solutions.
```

---

## 2. Information Architecture (IA) & Screen Hierarchy

```
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
| 1. GLOBAL MISSION HEADER (Height: 52px, Sticky)                                                         |
| [⚡ KORA DEV STUDIO] [Repo: creova-gif/kora] [Engine: Qwen 2.5 7B Edge] [🔒 Air-Gapped] [Egress: 0.0 KB]|
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
| 2. FLIGHT RECORDER TIME-TRAVEL SCRUBBER (Height: 36px, Sticky Subheader)                                |
| Tape: task_7420.flight │ [◂ Step] [ ═════════●══ ] Frame 3 of 4 [Step ▸] │ [⑂ Fork Alternate Timeline]  |
+──────────────────────────┬───────────────────────────────────────────────┬──────────────────────────────+
| 3. PRIMARY SIDEBAR       | 4. CENTRAL INTERACTIVE CANVAS                 | 5. COPILOT INSPECTOR         |
| (Width: 260px, Fixed)    | (Flexible Fluid Workspace)                    | (Width: 380px, Collapsible)  |
|                          |                                               |                              |
| • Workspace Navigation   | [Tabs: Code Diff │ Self-Healing │ Payments]   | • Copilot Status: READY      |
|   - 📂 Code & Diff       |                                               | • Grounded Citations         |
|   - 🔧 Self-Healing Loop | Active View:                                  |   - ADR-006.md #L1-45        |
|   - 💳 Settlement Broker | Surgical Ghost Diff / AST Worktree Terminal / |   - payment_broker.py        |
|   - 💻 Sandboxed Pty     | Multi-Rail Checkout Interface                 |                              |
|                          |                                               | • Chronological Thought Log  |
| • Architecture Modules   |                                               | • Command Input Dock:        |
| • Security Telemetry:    |                                               |   [ Instruct agent...   ➔ ]  |
|   DLP Guard: ACTIVE      |                                               |   AP2 Budget: $10.00 left    |
+──────────────────────────┴───────────────────────────────────────────────┴──────────────────────────────+
| 6. REALTIME TELEMETRY DOCK (Height: 24px, Fixed Bottom)                                                 |
| [●] SQLite: Connected │ WebSocket: LIVE │ Cost: $0.00000 │ Latency: 0.08s │ Audio: ON [🔊] │ Sovereign  |
+─────────────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 3. Visual Design System

### A. Color Palette & WCAG 2.1 AA Contrast Ratios
Every color token has been verified against the deep obsidian base (`#05070D`):

| Token Name | Hex Code | Contrast vs `#05070D` | Compliance | Semantic Purpose |
| :--- | :---: | :---: | :---: | :--- |
| **Obsidian Base** | `#05070D` | 1.0 : 1 | — | Canvas background, absolute depth |
| **Surface Card** | `#0B101D` | 1.2 : 1 | — | Card containers, sidebar panels |
| **Surface Elevated** | `#121829` | 1.5 : 1 | — | Card headers, input surfaces, active tabs |
| **Text Primary** | `#F8FAFC` | **18.2 : 1** | **AAA** | Core headings, code text, diff additions |
| **Text Secondary** | `#94A3B8` | **7.4 : 1** | **AAA** | Labels, breadcrumbs, parameters |
| **Text Muted** | `#64748B` | **4.6 : 1** | **AA** | Timestamps, line numbers, non-critical telemetry |
| **Accent Cobalt** | `#3B82F6` | **4.8 : 1** | **AA** | Primary interactive focus, active tab borders |
| **Emerald Shield** | `#10B981` | **6.9 : 1** | **AAA** | Air-gap verified, tests passing, $0.00 cost |
| **Amber Gate** | `#F59E0B` | **8.2 : 1** | **AAA** | Human approval required, fork points |
| **Crimson Kill** | `#EF4444` | **4.7 : 1** | **AA** | Failing tests, discarded hunks, network drop |

---

### B. Typography Scale
Strict typographic hierarchy using **Inter** for human UI and **Fira Code** with tabular numbers (`tabular-nums`) for all telemetry:

```css
/* Typography Scale */
--font-display:  600 16px/1.2 'Inter', -apple-system, sans-serif;
--font-body:     400 12px/1.5 'Inter', -apple-system, sans-serif;
--font-label:    600 11px/1.4 'Inter', -apple-system, sans-serif;
--font-code:     400 12px/1.6 'Fira Code', monospace;
--font-tnum:     500 11px/1.0 'Fira Code', monospace; font-variant-numeric: tabular-nums;
--font-nano:     600 10px/1.0 'Fira Code', monospace; text-transform: uppercase; letter-spacing: 0.05em;
```

---

### C. Spacing & Rhythm Grid
Built on a strict 4px/8px modular scale:
- `space-1` = 4px (micro padding inside badges)
- `space-2` = 8px (button gap, label margins)
- `space-3` = 12px (card padding, sidebar items)
- `space-4` = 16px (canvas workspace gutter)
- `space-6` = 24px (major section spacing)

---

### D. Component Library Specifications

1. **Tactile Buttons**:
   - *Default*: 1px border (`border-white/10`), rounded corners (`rounded-lg`), font `11px font-medium`.
   - *Hover*: Brightens background by 8% with 100ms transition.
   - *Active*: Physical mechanical depress: `transform: scale(0.98)` with 50ms transition.
   - *Focus-Visible*: 2px solid ring: `focus-visible:ring-2 focus-visible:ring-accentCobalt focus-visible:ring-offset-2 focus-visible:ring-offset-obsidian`.
2. **Ghost Diff Viewer**:
   - Line-by-line syntax with strict visual semantic blocks:
     - Addition line: `background: rgba(16, 185, 129, 0.12); color: #34D399; border-left: 2px solid #10B981;`
     - Deletion line: `background: rgba(239, 68, 68, 0.12); color: #F87171; border-left: 2px solid #EF4444;`
     - Context line: `color: #94A3B8;`
3. **Hardware Air-Gap Badge**:
   - Active: Emerald glow (`box-shadow: 0 0 16px rgba(16, 185, 129, 0.25)`), pulsing dot.
   - Inactive: Amber warning ring with text `HYBRID CLOUD ALLOWED`.

---

## 4. Interaction Design & Tactile Audio System

### A. States Matrix
| Component | Default | Hover | Focus-Visible | Active (Pressed) | Disabled |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Button** | `#2563EB` solid | `#1D4ED8` | 2px Cobalt Ring | `scale(0.98)` | `opacity: 0.4; cursor: not-allowed` |
| **Tactile Toggle** | `#10B981` border | `#10B981/20` bg | 2px Emerald Ring | `scale(0.96)` | `opacity: 0.3` |
| **Input Field** | `#05070D` base | `border-white/20` | `border-accentCobalt` | — | `bg-white/5` |
| **Timeline Scrubber** | `#3B82F6` thumb | `#60A5FA` | Ring on thumb | Dragging | `opacity: 0.2` |

---

### B. Teenage Engineering Synthetic Audio Architecture
Instead of loading external MP3 files (which fail in offline SCIFs), Kora synthesizes sound live using the **Web Audio API**:

```javascript
// Zero-dependency pure mathematical sound generation
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();

function playTone(freq, type = 'sine', duration = 0.08, gainVal = 0.04) {
  if (!audioEnabled || !audioCtx) return;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
  gain.gain.setValueAtTime(gainVal, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + duration);
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start();
  osc.stop(audioCtx.currentTime + duration);
}

// 1. Mechanical Air-Gap Latch: 140Hz sawtooth sweep
// 2. Self-Healing Pass Chime: 880Hz sine ➔ 1760Hz harmonic
// 3. Timeline Scrubber Frame Tick: 600Hz triangle wave
```

---

## 5. Responsive Breakpoints & Accessibility (WCAG 2.1 AA)

### A. Breakpoints
- **Desktop (≥ 1280px)**: Complete 3-column mission control (Sidebar + Center Canvas + Copilot Drawer).
- **Compact Laptop (1024px – 1279px)**: Collapses secondary citations into expandable slide-over drawer.
- **Tablet / Mobile (< 1024px)**: Sidebar converts to bottom thumb-dock navigation bar; central canvas prioritizes mobile diff review with 44px touch targets.

### B. Keyboard Accessibility Navigation Map
- `Cmd / Ctrl + Enter`: Instantly trigger agent instruction dispatch.
- `[` and `]`: Scrub flight execution tape backward/forward one step.
- `Alt + A`: Toggle Air-Gapped Zero-Egress mode.
- `Alt + H`: Trigger Autonomous Self-Healing repair loop.
- `Space`: Toggle audio synthesizer on/off.
- `Tab / Shift + Tab`: Full focus ring traversal across all controls with explicit `tabindex`.

### C. Screen Reader & Reduced Motion
- All interactive tab buttons enforce ARIA: `role="tab"`, `aria-selected="true/false"`, `role="tabpanel"`.
- Thought streaming updates are announced via an off-screen `aria-live="polite"` region.
- Respects `@media (prefers-reduced-motion: reduce)` by disabling spring translations and transitions.

---

## 6. Quality Checklist: Nielsen's 10 Usability Heuristics & Core Web Vitals

| Heuristic | Implementation in Kora Dev Studio |
| :--- | :--- |
| **1. Visibility of System Status** | Real-time WebSocket connection badge (`LIVE`), live cost counter (`$0.00000`), active model indicator, and frame-by-frame flight tape counter. |
| **2. Match between System & Real World** | Git worktrees labeled as "disposable sandboxes", mechanical click audio cues for state toggles, recognizable regional payment logos (M-Pesa, PIX, UPI). |
| **3. User Control & Freedom** | The **Deterministic Flight Scrubber** allows rewinding any agent mistake and branching alternative timelines with zero repository contamination. |
| **4. Consistency & Standards** | Standard unified diff syntax (`@@ -x,y +x,y @@`), conventional terminal prompt styling, consistent keyboard shortcuts. |
| **5. Error Prevention** | Biometric and confirmation gates on destructive commands; all agent code changes run in ephemeral worktrees before touching `main`. |
| **6. Recognition Rather Than Recall** | Active context citations displayed in side-drawer; suggested 1-click self-healing commands when a build fails. |
| **7. Flexibility & Efficiency of Use** | Keyboard accelerators for power users; 1-click visual buttons for beginners; open MCP bridge for custom IDEs. |
| **8. Aesthetic & Minimalist Design** | Pure obsidian background; zero marketing fluff inside the engineering canvas; every pixel serves code comprehension. |
| **9. Help Users Recognize & Recover** | Error frame locator highlights the exact offending AST line, file name, and exception type with an automated repair proposal. |
| **10. Help & Documentation** | Built-in `kora doctor` diagnostics and embedded ADR references for architectural decisions. |

### Core Web Vitals Targets
- **Largest Contentful Paint (LCP)**: `< 0.4s` (zero external framework bundles, inline Tailwind utilities).
- **Interaction to Next Paint (INP)**: `< 30ms` (native JS event handlers, zero virtual DOM reconciliation overhead).
- **Cumulative Layout Shift (CLS)**: `0.00` (fixed grid dimensions, tabular numerals preventing text jitter).
