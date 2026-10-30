# Kora Dev Studio — 10-Dimension Designer's Eye Plan Review

**Target:** `core/studio/index.html` & `docs/architecture/KORA_DEV_STUDIO_PRD.md`  
**Reviewer:** Principal Product Designer & HIG Specialist  
**Design Standard:** Linear-grade fluidity + Teenage Engineering tactile hardware aesthetic  

---

## Scorecard & Executive Rating

| # | Dimension | Current Rating | Target | Key Gaps Identified |
| :-: | :--- | :-: | :-: | :--- |
| **1** | **Typography & Hierarchy** | **7 / 10** | **10 / 10** | Monospace numbers lack tabular alignment (`tnum`); secondary metadata lacks contrast distinction. |
| **2** | **Spacing, Rhythm & Density** | **8 / 10** | **10 / 10** | High-density is good, but sidebar lacks clear visual padding between functional blocks. |
| **3** | **Color & Contrast** | **8 / 10** | **10 / 10** | Obsidian `#070A12` base is strong; accent cobalt needs distinct hover/active glow states. |
| **4** | **Component States** | **6 / 10** | **10 / 10** | Buttons lack distinct `:focus-visible` rings and tactile `:active` micro-scale depressions (`scale(0.98)`). |
| **5** | **Interaction & Motion** | **6 / 10** | **10 / 10** | Tab switches are instant cuts without fluid slide or spring physics; ghost diffs pop abruptly. |
| **6** | **Information Architecture** | **8 / 10** | **10 / 10** | Navigation trunk test passes, but time-travel scrubber needs visual placement in the main header. |
| **7** | **Cognitive Load & Density** | **8 / 10** | **10 / 10** | High telemetry density; needs progressive disclosure for raw JSON payment payloads. |
| **8** | **Responsive & Adaptive** | **7 / 10** | **10 / 10** | Excellent on 1440px desktop; mobile viewport needs collapsible copilot drawer and thumb-dock. |
| **9** | **Accessibility (a11y)** | **6 / 10** | **10 / 10** | Missing explicit `role="tablist"` and `aria-selected` attributes on navigation tabs. |
| **10** | **Craftsmanship & Delight** | **7 / 10** | **10 / 10** | Needs Teenage Engineering tactile audio clicks (synthetic Web Audio oscillators) and air-gap seal pulse. |
| **TOTAL** | **Overall Experience** | **7.1 / 10** | **10 / 10** | **Solid foundation; elevated to 10/10 via tactical design tokens below.** |

---

## Detailed Dimension Audits & Elevation Plan

### 1. Typography & Hierarchy (Target: 10/10)
- **Problem**: Monospace metric values (e.g. `$0.00 / token`, `0.08s latency`, token counts) jitter when rapidly streaming numbers because tabular figures (`font-variant-numeric: tabular-nums`) are not enforced.
- **Specification to reach a 10**:
  - Enforce `font-mono tabular-nums tracking-tight` on all telemetry counters, hashes, and diff line numbers.
  - Scale typography strictly: Header Display `14px/600`, Body `12px/400`, Subtext/Metadata `11px/500`, Nano-telemetry `10px/600 uppercase`.

### 2. Spacing, Rhythm & Layout (Target: 10/10)
- **Problem**: File tree explorer and navigation buttons touch edges without an intentional 8px grid rhythm.
- **Specification to reach a 10**:
  - Adopt a strict 4px/8px layout grid: `gap-2` (8px) for buttons, `p-3` (12px) for card headers, `p-4` (16px) for canvas workspaces.
  - Add vertical divider guides (`border-r border-white/5`) with hairline 1px visual weight.

### 3. Color & Contrast (Target: 10/10)
- **Palette Tokens**:
  - Background Base: `#05070D` (Pure Obsidian)
  - Surface Card: `#0C101D` (Deep Navy Tint)
  - Surface Elevated: `#141B2D` (Card Hover)
  - Emerald Shield (Air-Gap): `#10B981` (Glow: `box-shadow: 0 0 12px rgba(16, 185, 129, 0.25)`)
  - Accent Cobalt: `#3B82F6` (Active: `#2563EB`)
  - Crimson Block: `#EF4444` (Delete / Failure)
  - Amber Gate: `#F59E0B` (Pending Human Approval)

### 4. Component Architecture & Micro-Interactions (Target: 10/10)
- **Tactile Physics**:
  - Buttons depress by `transform: scale(0.98)` with a 50ms transition on `:active`.
  - Focused interactive controls reveal a subtle 2px ring: `focus-visible:ring-1 focus-visible:ring-accentCobalt/80`.

### 5. Interaction & Motion (Target: 10/10)
- **Spring Transitions**:
  - When switching between Diff, Self-Healing, and Payments tabs, apply an entry fade-and-slide: `opacity: 1; transform: translateY(0); transition: all 150ms cubic-bezier(0.16, 1, 0.3, 1)`.

### 6. Tactile Audio Feedback (Teenage Engineering Inspired)
- **Zero-Dependency Web Audio Oscillator**:
  - Instead of shipping heavy MP3/WAV files, generate micro-frequency audio beeps directly using browser Web Audio API:
    - *Air-Gap Toggle*: 120Hz sine sweep down (mechanical latch).
    - *Self-Healing Success*: 880Hz to 1760Hz crisp dual chime.
    - *Approval Gate*: 440Hz warm notification tone.
  - Global mute toggle in bottom status bar (`🔊 Sound: ON/OFF`).
