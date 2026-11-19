<!-- gstack: design-md-format=legacy-keep -->
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
| **Display Header** | `Inter`, system-ui | 800 (Bold) | `clamp(2.25rem, 4.5vw, 3.75rem)` / 1.05 | `-0.032em` | Studio Welcome & Hero Titles |
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


---

## 6. Website v1.1 — "Precision Instrument" Layer (2026-11-19)

Marketing-site additions on top of the base system. North star: **calm engineering** — the site reads like a well-made instrument.

### Type scale (utilities in `globals.css`)
- `.kw-display` — fluid hero display: `clamp(2.25rem, 4.5vw, 3.75rem)`, wght 800, tracking `-0.032em`.
- `.kw-h2` — section headings: `clamp(1.5rem, 2.6vw, 2.25rem)`, wght 700, `-0.02em`.
- `.kw-kicker` — mono eyebrow label: JetBrains Mono 11px / 600, `0.14em` tracking, uppercase. The "instrument label" signature; use on section badges.

### Section rhythm
- Uniform `py-16 sm:py-24` with `border-t border-border-subtle` hairline separation.
- `.kw-section-index` — mono `NN / LABEL` index top-right on major sections only ("engineering drawing" marker; never more than one per section).

### Emphasis rule
- `.frame-teal-rule` — 1px teal top rule, **only** on interactive/emphasis cards (e.g., the product-proof figure). Teal stays rare; neutral cards never get it.

### Motion — intentional, CSS-gated
- `.kw-reveal` + `Reveal` component (`components/motion/Reveal.tsx`): fade-rise 200ms ease-out, ≤3-item stagger via `kw-reveal-delay-{1,2}`. Hidden state applied post-mount only to offscreen elements — content is fully visible without JS and under `prefers-reduced-motion`.
- Tab/segmented indicators transition at 150ms. No bounce, no glow, no loops.

---

## 7. Website v2 — "Editorial Precision" Direction (2026-11-19)

Supersedes §6 defaults where they conflict. Benchmarked against Linear,
Cognition, Conductor, and Factory marketing surfaces: the shared trait is
**restraint** — ~3 elements per viewport, typography doing the work, one
large real product visual, near-invisible accent.

### Theme model — hybrid light editorial / dark product
- **Default = light editorial.** `data-theme="light"` on `<html>`; warm
  paper canvas `#f6f5f2`, white surfaces, near-black ink `#141416`.
- **Dark product bands.** `data-theme="dark"` scoped sections for the
  homepage hero, studio/terminal/product showcases, and the app-adjacent
  pages (`/docs`, `/api-reference`, `/governance`, `/models`,
  `/marketplace`). Near-black canvas `#09090b` retained.
- User theme toggle still works; scoped bands stay dark either way.

### Near-monochrome accent
- Teal is no longer the CTA color. `.kw-btn-primary` is inverted
  monochrome (ink on paper / white on black).
- Teal survives only inside authentic product screenshots and at most
  ~2 functional data points per surface (e.g., a receipt seal, a live
  gate state). Decorative teal bullets/icons are removed.

### Chrome budget
- No pill badges, no blueprint grid, no glows on marketing surfaces.
- Hairline `border` is the default separator; `frame-crosshair` reserved
  for genuinely framed product captures.
- JetBrains Mono only for `kw-fig-label` figure captions (`FIG 0.1 —`),
  code, and tabular data — never for nav, badges-as-decoration, or body.

### Type
- `.kw-display` bumped to `clamp(2.625rem, 5.25vw, 4.5rem)`, `-0.045em`
  tracking — Linear-scale statement headlines.
- Section numbering stays mono micro-label style (`FIG` / `01 /`) but
  quieter (10px, dim).

### Hero contract
- One statement headline, one supporting sentence, one primary CTA +
  one text link, then ONE full-width authentic product screenshot in a
  `kw-figure` hairline frame. No stat grids, no synthetic demo panels.

## 8. Website v3 — "Maritime Instrument" (2026-11-19)

Supersedes §1 mark lockup, §1 color systems, and §7 theme model where they
conflict. A ship's bridge at night: flat ink on dark chart paper. Depth
comes from hairline rules and fog-lift surfaces — **no gradients, no glows,
no decorative shadows, no textures**. Approved on the Paper board
`Keelway — v3 Brand Kit & Homepage` (four pages: Concept, Brand System,
Website, Product & Components).

### Canvas & ink — dark native (no light mode on marketing surfaces)
- `--canvas #08090a` instrument black. Surfaces are translucency steps
  (`--fog-4`, `--fog-8`), never solid grays.
- `--rule rgba(255,255,255,.06)` hairlines are the only borders.
- `--ink #f4f5f5` (17.4:1 AAA), `--muted #9ba1a6` (7.0:1 AA),
  `--dim #5d6268` (3.5:1 — decorative captions only, never body/nav).

### Accent — binnacle brass
- `--brass #c9a45c` (7.6:1 AA) replaces teal entirely. Brass is a material,
  not decoration: the mark's prime, primary CTAs, recommended/selected
  states, and sealed/awaiting instrument states. ~4 uses per view, max.
- `--brass-deep #a8854a` hover/active. Warning shares brass.
- Semantic: starboard green `#6fae8e` success, port red `#b0564e` error,
  flag blue `#6f87a3` info. Color never carries meaning alone — always
  paired with a text label or icon.

### Mark — K′
- Primary mark is `K′`: a K plus brass prime (`components/site/Mark.tsx`,
  `favicon.svg`). Wordmark "Keelway" in Inter 700, sentence case — never
  all-caps or letter-spaced. Min sizes: lockup 96px, mark alone 20px.

### Type — Inter + JetBrains Mono
- `.kw-display` `clamp(2.75rem,5.5vw,4.75rem)` weight 640 `-0.045em` —
  hero H1 only. `.kw-h1/.kw-h2/.kw-h3` 640/640/620.
- Mono is instrument labeling: `.kw-label` (11px, +0.14em, uppercase) for
  eyebrows/`FIG`/section indices, `.kw-data` for IDs/hashes/code. Never
  for prose or headlines.

### Components
- `.kw-btn`: primary brass/ink (hover `--brass-deep`), secondary hairline
  (`--fog-8` hover), tertiary `.kw-link`. Disabled 40%. Focus-visible =
  3px `--brass-ring` — never removed.
- `.kw-input` hairline; focus = brass border + 15% ring; error = port.
- `.kw-chip` mono pills per semantic (brass/green/red/blue).
- `.kw-card` fog-4 + hairline, radius 10; `.kw-figure` hairline-strong +
  `kw-figcap` mono caption. Brass border reserved for recommended cards.
- Motion: `.kw-rise` fade-rise, CSS-only, gated on
  `prefers-reduced-motion: no-preference` (also gates smooth scroll).

### Route set (v3)
`/`, `/about`, `/product`, `/pricing`, `/changelog`, `/contact`,
`/sign-in`, 404 — plus `/feed.xml`, `/sitemap.xml`, `/robots.txt`,
`/manifest.webmanifest`. Legacy paths 301 to live equivalents
(`next.config.ts`); removed pages stay recoverable in git history.

### Page contracts
- Home: eyebrow → "Agents that answer to you." → subline → 2 CTAs →
  `FIG 0.1` real app capture → 3 hairline columns (YOUR HARDWARE /
  YOUR POLICY / YOUR RECORDS) → install line → footer.
- Product: "One platform. Three instruments." → Gateway / Policy /
  Flight recorder cards → `FIG 1.x` captures.
- Pricing: "Priced like a ledger." → canonical 5-tier (Community $0,
  BYOM $15, Pro $29 brass-recommended, Team $49, Enterprise VPC row),
  0% token markup noted.
- Changelog: "The logbook, public." releases on hairline rows.
- Contact: "Talk to a human." form → drafted GitHub issue (no invented
  mailbox). Sign-in: `K′` + magic-link stub + SSO/GitHub (preview-gated).
- 404: port-red `ERR 404 — off the chart` → "isn't on the tape."
