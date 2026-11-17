# Keelway Studio — Design System Notes

Scope: the local Studio web IDE served at `/studio` (`core/studio`). The
governance console (`/console`, `web-console/`) and `website/` are separate
surfaces and are not covered here.

## Build

```bash
make studio-css         # rebuild assets/studio.css (committed)
make studio-css-check   # CI/pre-commit freshness check; fails if stale
```

`assets/studio.css` is a generated artifact (Tailwind 3.4.17, minified).
**Always rebuild after changing classes in `index.html` or `assets/studio.js`** —
`tailwind.config.js` scans only those two files. A stale build renders
silently wrong (unstyled/mispositioned elements), it does not fail loudly.

## Color tokens

Defined as `rgb(var(--token) / <alpha-value>)` in `tailwind.config.js`,
values in `tailwind.input.css` under `:root` (dark, default) and
`[data-theme="light"]`.

| Token | Dark | Use |
|---|---|---|
| `--ide-bg` | 11 15 20 | App background |
| `--ide-sidebar` | 17 22 29 | Cards, sidebar, panels |
| `--ide-activity` | 11 15 20 | Header/activity bar |
| `--ide-editor` | 13 18 24 | Editor surface |
| `--ide-panel` | 17 22 29 | Bottom panel |
| `--ide-status` | 11 15 20 | Status bar |
| `--ide-border` | 35 43 54 | Borders |
| `--ide-tab` | 22 28 36 | Tabs |
| `--ide-surface` | 22 28 36 | Raised surface inside cards |
| `--ide-fg` | 230 237 243 | Primary text |
| `--ide-muted` | 139 152 168 | Secondary text (~4.5:1 on all surfaces) |
| `--ide-faint` | 120 133 149 | Tertiary/de-emphasized text — floor for readable text on `ide-sidebar` |
| `--accent` | 45 212 191 | Keel teal — agent working / primary action |
| `--on-accent` | 11 15 20 | Text on accent buttons |
| `--ok` | 74 222 128 | Success / verified |
| `--warn` | 245 181 71 | Signal amber — a human must decide |
| `--danger` | 248 113 113 | Errors / destructive |

Brand semantics: teal = agent working, amber = human decision required.
Status is never conveyed by color alone — pair with text or an icon.

## Components (in `@layer components`)

`.btn` `.btn-primary` `.btn-ghost` `.btn-outline` · `.input` `.label` ·
`.tab` (with `aria-selected`) · `.act` (activity rail, `aria-pressed`) ·
`.rail-btn` (`aria-current="page"`) · `.card` · `.chip` `.step-chip` ·
`.section-title` · `.diff-add` `.diff-del` `.diff-hunk` ·
`.enter` `.pulse` `.aurora` motion utilities.

New UI should reuse these before introducing one-off classes.

## Interaction & accessibility conventions

- Render server data via `textContent`/`h()` DOM building. If `innerHTML`
  is unavoidable (legacy templates), every dynamic value must go through
  `esc()`. Never interpolate `err.message` unescaped.
- Dialogs (`#palette`, `#signin`, `#onboard`, `#labs-drawer`, `#always-form`)
  use `role="dialog"`, `aria-modal`, `aria-labelledby`, `trapFocus`, backdrop
  click and Escape to close, and restore focus to the invoker.
- Proof strips are real tablists: roving `tabindex`, Arrow/Home/End
  navigation, `aria-controls` → drawer `tabpanel`, Escape closes + refocuses.
- Toasts are a single `role="status"` live region (`aria-live="polite"`).
- `prefers-reduced-motion` disables all animation/transition.
- Focus rings: global `:focus-visible` accent outline — do not remove.

## Keyboard map

`Ctrl/Cmd+K` palette · `Ctrl/Cmd+S` save · `Ctrl/Cmd+J` panel ·
`Alt+1..6` sections · `Alt+A` air-gap · `Esc` layered close ·
`Ctrl/Cmd+Enter` submit agent composer.

## Layout

Desktop: activity rail (left) → section content → bottom panel → status
bar. Below `md:` the rail becomes a bottom bar; the task list/detail swap
is driven by `#sec-tasks[data-detail]`; the Labs drawer overlays
(`translate-x-full` closed / `translate-x-0` open, `end-0`).

## Internationalization / RTL

Strings flow through `data-i18n`/`t()`; logical properties (`start`/`end`,
`border-s/e`) are used instead of `left`/`right` so RTL works — keep it
that way in new markup.
