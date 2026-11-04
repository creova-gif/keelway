# Keelway Design System & Interface Specification
<!-- Keelway Sovereign Developer Infrastructure Design System -->

## Design Philosophy

Keelway's interface reflects its engineering ethos: **Local-First, Deterministic, Sovereign, and Calm.**

- **Calm Utility over AI Theater:** Avoid decorative gradients, floating purple blobs, pulsing dots, and bouncy cartoon easings. Every pixel serves developer focus and code comprehension.
- **Monaco & Code First:** Developers live in code. Syntax highlighting, terminal output, and AST diffs are the core visual anchors.
- **Radical Transparency:** Hardware telemetry (Unified Memory VRAM, local model parameters, flight tape count, Git commit SHA) is always visible, reassuring the developer that computation remains sovereign.

---

## 1. Color System (CSS Variables)

### Dark Mode (Primary Default)

```css
:root {
  /* Canvas & Surfaces */
  --bg-canvas: #0B0F14;          /* Deep void background */
  --bg-surface: #111821;         /* Primary card and panel surface */
  --bg-surface-elevated: #17202B;/* Hover, active, and modal surfaces */
  --border-subtle: #1C2633;      /* Dividers and quiet borders */
  --border-strong: #243040;      /* Card edges and active inputs */

  /* Text & Foreground */
  --fg-primary: #E6EDF3;         /* Headers and primary body (14.8:1 contrast) */
  --fg-muted: #9AA7B4;           /* Secondary metadata and labels */
  --fg-dim: #64748B;             /* Disabled text and placeholders */

  /* Semantic Sovereignty Accents */
  --teal-accent: #2DD4BF;        /* Verified, local-first, passing tests */
  --teal-surface: rgba(45, 212, 191, 0.12);
  --teal-ink: #06201C;

  --amber-alert: #F5B547;        /* Awaiting Human Quorum, pending review */
  --amber-surface: rgba(245, 181, 71, 0.14);
  --amber-ink: #2A1C02;

  --red-danger: #F87171;         /* AST syntax fault, test failure, cancel */
  --red-surface: rgba(248, 113, 113, 0.14);

  /* Elevation & Radius */
  --radius-sm: 6px;              /* Buttons, badges, and chips */
  --radius-md: 10px;             /* Input fields and inner panels */
  --radius-lg: 14px;             /* Container cards and modals */
}
```

### Light Mode (High-Contrast Clean)

```css
@media (prefers-color-scheme: light) {
  :root {
    --bg-canvas: #F8FAFC;
    --bg-surface: #FFFFFF;
    --bg-surface-elevated: #F1F5F9;
    --border-subtle: #E2E8F0;
    --border-strong: #CBD5E1;
    --fg-primary: #0F172A;
    --fg-muted: #475569;
    --teal-accent: #0F766E;
    --teal-surface: rgba(15, 118, 110, 0.1);
    --amber-alert: #B45309;
    --amber-surface: rgba(180, 83, 9, 0.1);
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

- **WCAG 2.1 AA Compliance:** Minimum 4.5:1 contrast for normal text; Keelway exceeds this with 14.8:1 on primary text.
- **Touch Targets:** All clickable buttons, pills, and dropdown triggers maintain at least 44px $\times$ 44px tap targets.
- **Keyboard Navigation:** Full tab order through file tree, editor, action buttons, and terminal console.
- **Reduced Motion:** Fully honors `@media (prefers-reduced-motion: reduce)` by disabling all transitions and animations.
