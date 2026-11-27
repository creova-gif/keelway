# 05 — Design System (pointer + verified state)

Canonical sources already in repo — do NOT duplicate them here:

- `DESIGN.md` — fonts, colors, spacing, aesthetic direction
- `dev-app/src/styles/tokens.css` — dev-app design tokens (source of
  truth; `web-next` freshness gate enforces parity in CI)
- `docs/design/` — design specs incl. Paper 13.x (toasts, gated
  states, pinned P-10 rows shipped via KEEL-DSN-005/006)
- `docs/designs/` — per-feature design docs

Verified conventions: `kw-*` classes on `website/`; Lucide
iconography (KEEL-DSN-004); 17px body (`--fs-body`), `--dim #8a9096`
recorded as marketing AA exception; radius tokens `--radius-sm/md/lg`
present in both sites (KEEL-WEB-050); NO_COLOR/ASCII fallback in CLI.

Accessibility posture: axe-core WCAG 2.2 AA suite runs in CI on all
`website` + `web-next` routes; dev-app keyboard nav + command palette
verified. Frontend lane owns any remaining a11y gaps vs DESIGN.md.
