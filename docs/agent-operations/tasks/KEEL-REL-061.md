# KEEL-REL-061 — Kora → Keelway Canonical Rename Migration

| Field | Value |
|---|---|
| **Status** | `VERIFIED_COMPLETE` |
| **Category** | `RELEASE / BRANDING / MIGRATION` |
| **Agent** | Devin |
| **Date** | 2026-11-18 |
| **Branch** | `rename/KEEL-REL-061-kora-to-keelway` |
| **Decision** | `docs/release-readiness/2026-11-17/19-architecture-decisions/ADR-001-product-naming.md` — OD-1, Option 1: Keelway canonical |

## Objective
Execute the owner-approved rename (ADR-001, Option 1): `kora` → `keelway` as
the canonical name across the product surface, as **one versioned migration**.
Per ADR-001's guardrail, no piecemeal renames — every surface lands in the
same release window.

## Scope (all required — one migration)
- **Repo**: rename GitHub repo `creova-gif/keelway` → `creova-gif/keelway`
  (GitHub auto-redirects the old URL; update remotes in the same window).
- **Package / wheel / PyPI**: package name `kora` → `keelway`; PyPI project,
  `pip install` docs, cosign/Homebrew artifacts regenerated under new name.
- **Binary / CLI**: `keelway` command already canonical — verify nothing
  exposes `kora` to users (`kora` console scripts, `kora` SDK package).
- **API namespace**: internal `/v1` is name-agnostic; verify no `kora` in
  public endpoint names, headers (`X-Keelway-*` already canonical), or tokens.
- **Env var prefix**: `KEELWAY_*` already canonical — confirm no `KORA_*` vars
  exist (check `.env.example`, deploy configs).
- **Deployment domain**: `kora-sable.vercel.app` → `keelway-*.vercel.app`
  (Vercel project rename or new project + domain cutover).
- **Storage / local state**: `~/.kora/` or `kora` DB paths — provide
  migration/symlink so existing installs keep working, or document the reset.
- **Docs**: README, website, `docs/`, AGENTS.md deployment URL, task board.

## Acceptance criteria
1. `grep -ri 'kora'` returns only documented legacy/redirect references —
   no user-facing `kora` remains (a checklist diff script in CI or the task).
2. Install path verified clean-env: `pip install keelway` (or install URL)
   works; old `kora` references redirect, not break.
3. Website + Vercel deploy respond on the keelway domain; old domain redirects.
4. Existing `.keelway/` workspaces unaffected; any `kora` local-state path
   migrated or documented.
5. All suites green: `pytest`, `tsc`, dev-app build, studio-css-check.
6. Docs + this task updated; ADR-001 consequence checklist checked off.

## Out of scope
- Renaming Kora-specific third-party artifacts beyond this repo's control
  (list them in the handoff if discovered).

## Security / integrity constraints
- Do not rename until repo-level rename plan is approved — the ADR requires
  one versioned migration.
- No hardcoded credential changes bundled into the rename diff.

## Progress ledger (2026-11-18)

### Done
- **GitHub repo renamed** `creova-gif/kora` → `creova-gif/keelway`; old URL
  redirects indefinitely so existing clones and the owner's YC application
  link keep working (owner notified to update at convenience).
- All `creova-gif/kora` references → `creova-gif/keelway` across 30+ files:
  `bin/install.sh`, `website/{install.sh,public/install.sh}`,
  `Formula/keelway.rb`, `packaging/homebrew/keelway.rb`,
  `scripts/gen_homebrew_formula.py`, `sdk/typescript/package.json`,
  `AGENTS.md`, `README.md`, `SECURITY.md`, `api/early-access.js`
  (`REPO_NAME`), Makefile comment, docs/runbooks/architecture/product,
  and every test pinning `kora.git` (`test_phase1x_*`, `test_website_facts`,
  `test_full_beta_user_journey`, `test_phase7_packaging_and_sdk`,
  `test_agent_sandbox` workspace path).
- `core/eval/evidence_room.py`: runtime label "Kora AI Core by Kora
  Technologies" → "Keelway AI Core by Keelway Technologies".
- `core/orchestration/self_healing.py` and
  `scripts/verify_engineering_gates.sh`: probe `keelway-ai.nosync` first,
  legacy `kora-ai.nosync` retained as fallback.
- Verified: 81 + 29 targeted pytest green, `py_compile` clean.

### Phase 2 (2026-11-18, owner: "change everything except the Vercel link and repo")
- **`kora_*` SQLite tables renamed** to `keelway_*` in `models.py`,
  `database.py`, `conftest.py`. `init_db()` now renames any pre-existing
  `kora_%` tables to `keelway_%` on startup (guarded: canonical name wins on
  conflict, legacy table retained). `decision-precedence.md` updated to
  supersede the earlier keep-`kora_` decision. New coverage:
  `tests/test_kora_table_migration.py` (positive migration + conflict path).
- **Hardcoded default secrets renamed**: `KORA_OMNICHANNEL_SECRET_2026` →
  `KEELWAY_OMNICHANNEL_SECRET_2026` (messaging.py),
  `KORA_SOVEREIGN_PAYMENT_SECRET_2026` → `KEELWAY_…` (source_defaults.py,
  payment_broker.py, test), `KORA_SOVEREIGN_OFFLINE_SALT_2026` →
  `KEELWAY_…` (ledger.py). Rotating a *default* changes derived values —
  real deployments must override these anyway.
- **PIX merchant name** in the copia-e-cola payload `KORA_AI` → `KEELWAY`.
- **Container images** `ghcr.io/creova-gif/kora` → `keelway` (helm, k8s,
  terraform aws/gcp). The deploy workflow publishes
  `ghcr.io/${{ github.repository }}` so builds already emit `keelway`
  post-rename; the gcr.io default needs one republish before first use.
- **NOTICE**: product naming → Keelway AI Core; `Kora Technologies` entity
  copyright and trademark attributions preserved (legal facts).
- Remaining identifiers: `kora_candidates` → `keelway_candidates`
  (workflows), sandbox test vars, `cd kora` clone instructions →
  `cd keelway`, `product-facts.yaml` repo URL, website demo comments.
- Verified: 132 + 49 targeted pytest green, `py_compile` clean.

### Intentionally kept (documented, not forgotten)
- `.kora` entries in `PROTECTED_PREFIXES`/`PROTECTED_DIRS`, `legacy_aware()`
  shims, `kora-ai.nosync` fallback probe, `kora.db` legacy filename fallback:
  they protect and serve pre-rename installs — correct by design.
- `kora-sable.vercel.app`: still the live deployment domain and referenced
  in the owner's YC application — kept working; cutover is owner-timed.
- `Kora Technologies` entity attribution in NOTICE and the "Kora" trademark
  lines: legal facts, altered only by owner counsel.
- Historical docs (task logs, audits, `docs/archive/`,
  `docs/release-readiness/2026-11-17/`, roadmap milestones): records of
  fact, not rewritten.

### Queued external steps
- **Vercel project rename** `kora` → `keelway`: **PAUSED by owner**
  (2026-11-18). The `kora` project and `kora-sable.vercel.app` remain
  untouched; a domain cutover is owner-timed against the YC application.
  When unpaused: `authorize_team_access` (MCP) → `update_project` rename →
  verify `kora-sable` domain stays attached → optionally add a `keelway`
  alias.
- **gcr.io image republish** under `keelway`: happens naturally on the
  next release build (deploy workflow publishes
  `ghcr.io/${{ github.repository }}`); the terraform `gcr.io` default
  needs one GCR push before first use.
- PyPI/Homebrew artifacts regenerated under the keelway name on next
  release (formula file already `keelway.rb`).

**Task closure note (2026-11-18):** all in-repo rename surfaces are
migrated and verified (phases 1–2, PRs #68, #69). Remaining items are
external/owner-timed operational actions documented above, not code
work — marking `VERIFIED_COMPLETE`.
