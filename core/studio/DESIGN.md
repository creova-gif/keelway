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
values in `tailwind.input.css` under `:root` (dark, default),
`[data-theme="light"]`, and `[data-theme="hc"]` (high-contrast dark:
pure-black surfaces, slate-400 borders, ≥7:1 text). A
`prefers-contrast: more` media rule applies the same hc tokens when the
OS asks for more contrast, unless the user explicitly chose light.
The theme button + palette command cycle dark → light → hc; Monaco maps
them to `vs` / `hc-black` / `keelwayDark`.

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

JS-level render helpers (top of `studio.js`) — reuse before hand-rolling:

| Helper | Purpose |
|---|---|
| `h(tag, attrs, ...kids)` | DOM builder; every child via `textContent` — the only sanctioned way to render server data |
| `esc(v)` | Escapes for the few legacy `innerHTML` templates left |
| `statusChip(status)` | `.chip` with ok/warn/danger tone mapped from backend status; text always visible |
| `metricChip(label, value)` | Label/value summary tile (eval, drift) |
| `loadErrorNode(err, retry)` | `role="alert"` error block + Retry button |
| `renderLoadError(el, err, retry)` | Swap a container's contents for the standard error block |
| `goFeature(sec, id)` | Palette deep-jump: switch section, scroll to a card |

Card convention: API results render as `h()`-built cards/lists —
scannable fields + status chips. The `<pre>` stays only as a one-line
status/diagnostic log beneath; long monospace dumps are not a primary
information surface.

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

## Async state conventions

Every async loader/action must have distinct states:

- **loading**: textContent placeholder in the status `<pre>` or a muted line.
- **empty**: explicit sentence (e.g. "No active plugins found…"), never
  blank space and never a fake zero/pass total.
- **success**: structured cards + one-line `[✓]` status.
- **error**: `renderLoadError` block (message + Retry) for list loaders,
  or `[-]` status line for action logs; `tone('err')` + toast when the
  user initiated it.
- **not run**: honest "Panel not run" / "NOT RUN" marks — never imply a
  result that hasn't been produced.

List regions that change asynchronously get `aria-live="polite"`.

## Density

`data-density` on `<html>` scales the root `font-size` (compact 14px /
default 16px / comfortable 17px). All rem-based Tailwind utilities scale
with it; fixed px values (icons, brackets like `h-7`) stay anchored.
Persisted to `localStorage keelway.density`, cycled by `#density-btn`.

## Keyboard map

`Ctrl/Cmd+K` palette · `Ctrl/Cmd+S` save · `Ctrl/Cmd+J` panel ·
`Alt+1..6` sections · `Alt+A` air-gap · `Esc` layered close ·
`Ctrl/Cmd+Enter` submit agent composer.

## Layout

Desktop: activity rail (left) → section content → bottom panel → status
bar. Below `md:` the rail becomes a bottom bar; the task list/detail swap
is driven by `#sec-tasks[data-detail]`; the Labs drawer overlays
(`translate-x-full` closed / `translate-x-0` open, `end-0`).

## Information architecture

Sections and where each feature card lives. The palette (`Ctrl/Cmd+K`)
deep-links to every card below via `goFeature`.

| Section | Surface (master-prompt #) | Cards / capabilities |
|---|---|---|
| `sec-home` | 01 Home & Workspace · 07 Runtime | Quick actions, model/hardware/tasks/tapes tiles, `lab-doctor` (system diagnostics), `lab-code-intel`, `lab-conflict-resolver`, `lab-app-builder` |
| `sec-workspace` | 02 Projects · 04 Code & Terminal | Explorer, git changes, memory, Monaco editor, diff view, console |
| `sec-tasks` | 03 Agent Workspace | Run list/detail, `lab-kflow` (DAG orchestration), `lab-agent-bundle` |
| `sec-runs` | 01 Evidence / observability | Flight tapes, `lab-evidence` (metric cards), `lab-merkle-audit` |
| `sec-skills` | — | `lab-kstack` (role skills), `lab-plugins` (MCP), `lab-kbrain` (fact memory), `lab-eval-drift` |
| `sec-settings` | 10 Settings · 05/08/09 partial | Appearance/language/air-gap, `lab-quorum` (approvals), `lab-mesh` (P2P compute), `lab-sync`, `lab-runner-spool`, cost ledger, agent registry |
| Labs drawer | — | `lab-healing` (self-repair bench — experimental) |

Honest gaps (exist as backend capability, no dedicated surface yet):
unified **06 AI Models** view (today: ledger + econ inside Settings,
model badge in status bar), unified **08 Security & Policies** view
(today: spread across Runs audit, Settings quorum, Tier-2 badges),
**09 Enterprise Admin** console (`/console` is a separate surface,
not Studio).

## Internationalization / RTL

Strings flow through `data-i18n`/`t()`; logical properties (`start`/`end`,
`border-s/e`) are used instead of `left`/`right` so RTL works — keep it
that way in new markup.
