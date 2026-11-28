# Desktop Completeness Audit — Competitor-Informed (KEEL-DSN-003)

Reference set audited: **Devin/Cognition** (agent chat, secrets, billing seats), **Antigravity** (agent manager, inbox), **Conductor** (multi-workspace switcher), **OpenCode** (session list, model picker, permission prompts), **Factory** (droid sessions, review), **Linear** (inbox/triage grammar), **Higgsfield/Paper** (kit tooling).

## What the kit already covered

- Brand system (logo, color, type, iconography, voice) — page 04
- Tokens synced code↔design (hash `f8e761be`, updated 2026-11-23 — see `docs/design/TOKENS.md`) — `docs/design/tokens.json`
- Product screens (app shell, Record), interfaces (IDE, Ops, Agents run detail, Marketplace, Builder) — pages 10–12
- All 8 Settings panels — page 17 (`17.1`–`17.6`)
- P-10 card + Tasks lane, billing, onboarding, command palette, remaining views + state matrix, drawers — page 18 (`18.1`–`18.5`)
- Accessibility contracts — page 14

## Gaps closed on page `19 — Desktop Completeness` (`p-J-0`)

| Artboard | Surface | Borrowed from |
|---|---|---|
| `19.1` `322-0` | Component primitives vocabulary — buttons/inputs/menus/tooltips/toasts/dots+kbd/dialogs/disclosures + "never ships" rules | Linear restraint, all |
| `19.2` `35J-0` | Agent composer deep-dive — attachments, model/route selector, pre-flight simulation strip, inline P-10 request in thread | Devin, Antigravity, OpenCode |
| `19.3` `35K-0` | Workspace switcher (⌘⇧W, worktree-scoped, per-workspace P-10 badges) + Inbox (3 item kinds only: P-10 requests, run receipts, security events) | Conductor, Antigravity inbox |
| `19.4` `35L-0` | First-run auth (local-no-account vs team scoped token, no oracle on failure) + About & updates (version/channel, ed25519 signature state, SBOM link, no "trust anyway") | desktop-app norm + Keelway verification differentiator |

## Still open

1. ~~**Light-theme token set** — app ships light mode; Paper tokens are dark-only. Next kit task.~~ **RESOLVED 2026-11-23**: added artboard `02.5 — Light-theme reference` on page 04 (Brand System), documenting the real values already shipped in `dev-app/tokens.css`'s `[data-theme="light"]` block (canvas, surface, ink, muted text, rule, accent). This is a reference board, not a new design decision — Paper itself stays dark-native per DESIGN.md §8 ("no light mode on marketing surfaces"); the board exists so anyone implementing light-mode product screens has the real values in the same place as the rest of the brand system.
2. ~~**Chat thread as a first-class view** — `AgentComposer.tsx` exists in code; 19.2 defines its grammar. If it becomes a full view (not just composer+lane), needs its own rail entry — product decision.~~ **DECIDED 2026-11-23**: own rail entry, chosen over staying nested in Agents. Artboarded as `12.11 — Chat · first-class view` (page 12): a dedicated "Chat" rail item beside Agents, with a full-height thread, a session switcher, and the pre-flight/P-10 grammar carried over unchanged from `19.2`. **Real implementation implication, not just a design add**: this makes Chat the 11th rail view, which contradicts the product's own "Unified 10-View Sovereign Dev Tool" naming — shipped in `README.md` (3 places) and baked into the `PlatformViewId` type (`dev-app/src/lib/types.ts`, currently exactly 10 values). Whoever implements this needs to update that naming/type alongside the code, not just add a new screen.
3. ~~**Billing tier count** — app 4 tiers vs website 5; still awaiting canonical decision.~~ **RESOLVED 2026-11-23**: this was backwards. Direct verification of the pricing page (then `website/src/data/pricing.ts` + `website/src/app/pricing/page.tsx`; the site has since moved to `web-next/src/app/pricing/page.tsx` post-WEB-055, same 4 tiers inline) confirms the website has exactly **4 tiers** (Community/BYOM/Pro/Enterprise), matching the app. The false "5-tier" figure came from `README.md`, which wrongly listed a 5th "$49/seat Team" tier that exists nowhere in code. Fixed in PR #218 (two README corrections: tier count, and a false "TUI" capability claim). The pre-existing Paper billing board (`18.2`) was also stale in a third direction — it showed only 3 tiers ("Solo/Pro/Enterprise") with no BYOM — and has been corrected to the real 4-tier model (see `TOKENS.md` 2026-11-23 update).
4. **Diff-review full view** — 18.5 covers the drawer; a standalone review view (Devin-style side-by-side) is a candidate if usage justifies it.
5. ~~**Wappalyzer exports** (`Downloads/build-fw/*.csv`) — reviewed; tech-stack fingerprints only, no design signal beyond the competitor set itself.~~ **EXPANDED 2026-11-23**: re-reviewed all 7 CSV exports individually (not just the aggregate), then cross-validated against live computed CSS on two sites via browser DevTools. Real findings:
   - The full competitor set (capy.ai and others) converges on Next.js/React/Tailwind/Radix-UI/shadcn/Base-UI/Vercel — this is the category-standard stack, not an outlier pattern.
   - **Linear.app is a styling outlier, not an implementation one**: it runs styled-components + MobX on Google Cloud (not the Tailwind/Radix norm), but its *live computed* CSS values (spacing, radii, type weights) closely validate our existing maritime-v3 tokens — e.g. its variable-weight type sits in the same ~510–640 range our `--font-sans` cap documents, which is what motivated the font-weight-700→640 correction made this session (see `TOKENS.md`).
   - **Conductor.build, not Linear, is the closest real stack analog** to Keelway (Tailwind + Radix + shadcn + Base-UI).
   - **Motion-library recommendation**: Framer Motion for Keelway's own app/product UI (state-heavy); reserve GSAP for marketing-site scroll choreography only, consistent with how the competitor set itself splits by site type.
   - **Ad-tech posture correlates with audience type**: consumer/paid-acquisition sites in the set run heavy tracking stacks; dev-tool/organic sites run lean. Recommend keeping Keelway's marketing site in the lean group — consistent with the Sorvex Labs Posture page's "no standing egress by default" claim (page 05.5).
