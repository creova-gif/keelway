# Keelway Design System & Interface Specification
<!-- Keelway Sovereign Developer Infrastructure Design System -->

## Design Philosophy

Keelway's interface reflects its engineering ethos: **Local-First, Deterministic, Sovereign, and Calm.**

- **Calm Utility over AI Theater:** Avoid decorative gradients, floating purple blobs, pulsing dots, and bouncy cartoon easings. Every pixel serves developer focus and code comprehension.
- **Monaco & Code First:** Developers live in code. Syntax highlighting, terminal output, and AST diffs are the core visual anchors.
- **Radical Transparency:** Hardware telemetry (Unified Memory VRAM, local model parameters, flight tape count, Git commit SHA) is always visible, reassuring the developer that computation remains sovereign.

---

## 1. Color System (CSS Variables) & Brand Lockup

### Official Wordmark & Mark Lockup Rule

Keelway uses one standardized logo geometry across every surface: a geometric **K** (`M7 5h9v38H7z` and `M16 26 28 5h9L25.5 27 44 43H32L16 30z`) drawn in the surface's primary foreground color (`--fg-primary`) with a standalone teal dot (`cx="42.5" cy="9" r="4.5"` in `--teal-accent`) paired beside the **"Keelway"** wordmark. Standalone app icons and `favicon.svg` place the `#FAFAFA` geometric K and `#2DD4BF` dot inside a `#09090B` rounded tile (`rx="11"`). Never stuff a tagline inside the wordmark lockup, and never use a solid teal square background tile in headers or footers.

### Dark Mode (Primary Default — Monochrome Zinc + Single Teal)

```css
:root {
  /* Canvas & Surfaces */
  --bg-canvas: #09090B;          /* Monochrome void background (Zinc 950) */
  --bg-surface: #121215;         /* Primary card and panel surface */
  --bg-surface-elevated: #18181B;/* Hover, active, and modal surfaces (Zinc 900) */
  --border-subtle: #27272A;      /* Dividers and quiet borders (Zinc 800) */
  --border-strong: #3F3F46;      /* Card edges and active inputs (Zinc 700) */

  /* Text & Foreground */
  --fg-primary: #FAFAFA;         /* Headers and primary body (19.2:1 AAA contrast) */
  --fg-muted: #A1A1AA;           /* Secondary metadata and labels (7.9:1 AAA contrast) */
  --fg-dim: #8E8E96;             /* Metadata, timestamps, and placeholders (5.6:1 AA contrast) */

  /* Single Brand & Primary Action Accent (Reserved for K-dot mark, primary CTA, and focus ring) */
  --teal-accent: #2DD4BF;        /* Brand mark dot, primary CTA, focus ring */
  --teal-surface: rgba(45, 212, 191, 0.12);
  --teal-ink: #042F2E;           /* High-contrast ink on solid teal fills (8.6:1 AAA) */

  /* Restrained Monochrome Secondary / Gate Tokens */
  --amber-alert: #E4E4E7;        /* High-contrast monochrome zinc secondary badge */
  --amber-surface: rgba(228, 228, 231, 0.10);
  --amber-ink: #09090B;

  --red-danger: #F87171;         /* AST syntax fault, test failure, cancel */
  --red-surface: rgba(248, 113, 113, 0.14);

  /* Elevation & Radius */
  --radius-sm: 6px;              /* Buttons, badges, and chips */
  --radius-md: 10px;             /* Input fields and inner panels */
  --radius-lg: 14px;             /* Container cards and modals */
}
```

### Light Mode (High-Contrast Clean — Monochrome Zinc + Single Teal)

```css
@media (prefers-color-scheme: light) {
  :root {
    --bg-canvas: #FAFAFA;
    --bg-surface: #FFFFFF;
    --bg-surface-elevated: #F4F4F5;
    --border-subtle: #E4E4E7;
    --border-strong: #D4D4D8;
    --fg-primary: #09090B;
    --fg-muted: #52525B;
    --fg-dim: #71717A;
    --teal-accent: #0F766E;
    --teal-surface: rgba(15, 118, 110, 0.10);
    --teal-ink: #FFFFFF;
    --amber-alert: #27272A;
    --amber-surface: rgba(39, 39, 42, 0.08);
    --amber-ink: #FAFAFA;
    --red-danger: #B91C1C;
  }
}
```

---

## 2. Typography

| Role | Font Family | Weight | Size / Line Height | Tracking | Purpose |
|---|---|---|---|---|---|
| **Display Header** | `Inter`, system-ui | 800 (Bold) | `clamp(2rem, 4vw, 3rem)` / 1.1 | `-0.03em` | Studio Welcome & Hero Titles |
| **Section Header** | `Inter`, system-ui | 700 (Semi-bold) | `1.25rem - 1.5rem` / 1.25 | `-0.02em` | Card titles and lab views |
| **Body Text** | `Inter`, system-ui | 400 (Regular) | `15px` / 1.6 | `normal` | Explanations and descriptions |
| **Code & AST** | `JetBrains Mono` | 500 (Medium) | `13px` / 1.7 | `0.02em` | Terminal, diffs, JSON, paths |
| **Telemetry Badge**| `JetBrains Mono` | 600 (Semi-bold)| `11px` / 1.0 | `0.04em` | Status pills, RAM, commit SHAs |

---

## 3. Spacing & Spatial Rhythm

Strict 4px/8px modular grid:
- `space-1` (4px): Micro-spacing between icon and text.
- `space-2` (8px): Gap between chips, buttons, and inline metadata.
- `space-3` (12px): Inner padding for inputs and compact list items.
- `space-4` (16px): Card gutter and default grid gap.
- `space-6` (24px): Card padding and section margins.
- `space-8` (32px): Layout panel separation.

---

## 4. Interaction States & Transitions

- **Hover States:** Fast 150ms transition with slight brightness increase (`filter: brightness(1.06)`) or subtle border accent (`border-color: var(--teal-accent)`). Never bouncy spring animations.
- **Focus States:** High-visibility `:focus-visible` with `2px solid var(--teal-accent)` and `3px offset`.
- **Active / Pressed:** `transform: scale(0.99)` for immediate tactile click feedback.
- **Empty States:** Always provide context, a reassuring message, and a primary CTA (e.g. *"No tasks yet — give the agent a goal or open a file"*).

---

## 5. Accessibility (a11y) Requirements

- **WCAG 2.1 AA Compliance:** Minimum 4.5:1 contrast for normal text; Keelway exceeds this with 19.2:1 on primary text.
- **Touch Targets:** All clickable buttons, pills, and dropdown triggers maintain at least 44px $\times$ 44px tap targets.
- **Keyboard Navigation:** Full tab order through file tree, editor, action buttons, and terminal console.
- **Reduced Motion:** Fully honors `@media (prefers-reduced-motion: reduce)` by disabling all transitions and animations.
