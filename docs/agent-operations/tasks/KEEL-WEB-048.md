# KEEL-WEB-048 — web-next utility routes (Paper 13.1/13.2)

## Objective

Ship the four routes Paper page 13's Website Interface Specs require and
`web-next` lacked: `/legal`, `/blog`, `/signup`, `/offline`. Also bring the
header nav to the spec's target order (`Product · Pricing · Docs · Changelog ·
About`) and fix a leftover 15.2 iconography violation in the same file.

## Shipped

| Route / change | Implementation |
|---|---|
| `/legal` | Terms of service (T-01..T-05) + privacy (P-01..P-04) clause rows in the about-page border-row grammar. Plain-language clauses only — Apache-2.0 open core, private-preview cloud, 0% token markup, magic-link-only auth, contact data never routed to public trackers (repo invariant), "signed agreement governs" scope note. |
| `/blog` | "Field notes" index — five cards linking to *real* existing pages (`/changelog`, `/product`, `/pricing`, `/about`). No fabricated posts or dates; the page explicitly notes the engineering log lives in the changelog, and links `feed.xml`. |
| `/signup` | Two-path page in the sign-in layout: Community self-hosted (`InstallCommand` — free, Apache-2.0, runs offline) vs Cloud private preview (`MagicLinkForm` — honest "request access" copy, no fake account creation). |
| `/offline` | Static fallback in the `not-found` grammar — "OFFLINE — read only" eyebrow, retry link, honest claim that the self-hosted core runs fully offline. |
| `SiteHeader` | `About` added to NAV (spec target nav); hand-authored hamburger/close SVG → Lucide `Menu`/`X` (`lucide-react` was already a dependency, unused — same 15.2 fix as `website/` under DSN-004). |
| `SiteFooter` | `Blog`, `About`, `Legal` added to the footer nav. |
| `sitemap.ts` | `/blog`, `/legal`, `/signup` added; `/offline` deliberately excluded (fallback surface, not an indexable destination). |

## Honesty notes

- **No fake content**: blog entries are real field-note excerpts pointing at real
  destinations, not invented dated posts. Legal copy is plainly labeled — signed
  agreements supersede.
- **`/signup` claims nothing** — `MagicLinkForm` already routes to the honest
  "private preview, request access on GitHub" state.
- **Spec drift flagged, not shipped**: Paper 13.1 still says "5-tier" pricing —
  canonical is 4 (KEEL-APP-081); Paper side needs the correction.

## Verification

- `npx tsc --noEmit`: clean
- `npx next build`: all 19 routes prerender; new `/blog` `/legal` `/offline`
  `/signup` static (141B–1.1kB)
- Pre-existing warnings only (dual-lockfile notice, ambiguous
  `duration-[var(--dur-base)]` classes in unrelated components)

## Remaining page-13 open items (Paper-side / deferred)

- 13.4 embedded terminal — Paper self-flags "spec — not shipped"
- "5-tier" → 4-tier correction on Paper 13.1
