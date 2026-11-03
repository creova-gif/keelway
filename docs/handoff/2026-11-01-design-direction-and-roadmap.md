# Keelway handoff: design direction, product stage, competitors, next work

Written 2026-11-01 for Devin to pick up on 2026-11-02. Base: `origin/main` @ `78e062b`.
Everything marked **verified** was checked against that commit. Everything marked **external** comes from web
search results (secondary blogs, mostly) and must be checked against vendor pages before it is quoted anywhere.

## 0. Read this first

- **Name:** the product is now **Keelway, by Sorvex Labs** (merged in `c624682`). The design preview in
  `assets/` still says "Kora" because it was built before the rename. Treat it as a mock, not code.
- **`DESIGN.md` has NOT been written.** The owner approved the design direction below but asked to hold the
  write until the rename and Devin's in-flight Studio work settle. Do not create `DESIGN.md` from this doc
  without asking. Section 2 says what to reconcile first.
- **The Figma is the source of truth for Studio visuals** (`c57560d` built the task-first home "from the
  Figma"). Nothing here overrides it. Section 2 lists only additions and two conflicts to raise with the owner.
- Open branches when this was written: `devin/1793544785-vercel-static-site` (static site only) and
  `devin/1793543707-approval-rule-fixes`. Check their state before touching approvals or `vercel.json`.

## 0.1 Owner decisions and direction since this doc was first written (2026-11-01, later)

- **Figma is no longer the source of truth.** The brand kit `keelway-brand-kit.html` was rejected: it "looks like a
  small business brand". Replacement direction: `assets/brand-direction-v0.2.html` (screenshot:
  `assets/brand-direction-v0.2.png`). Core ideas: a plain heavy **K mark with one accent dot** (the point where an
  agent stops and a person decides), Archivo for headlines, Instrument Sans for interface, Martian Mono for
  evidence, ink and paper with **one** chromatic brand color (Keel teal), amber only for "a human must decide",
  and the product's own **Record** panel as the hero. Headline: "The control layer for AI agents."
  Status: draft, not approved. It needs the owner's yes before anything is built or `DESIGN.md` is written.
- **Studio keeps Inter and JetBrains Mono** (already shipped). The new faces are for the website and brand.
- **Keep teal as the brand color**; the earlier "no brand accent" idea is withdrawn. Drop the `.aurora` glow.
  Use the shipped palette (all text pairs measure 4.5:1 or better); my earlier day-panel palette failed contrast
  (amber 2.25:1) and is withdrawn. Every state needs shape + word + color, never color alone.
- **Positioning:** governed control layer first, own agent as the reference implementation. See
  `business-model-and-platform.md`.
- **Business model:** open core, with a change: "policy flows down, hashes flow up, code stays local".
  Agents-on-the-platform plan: manifest, private registry, builder, public verified registry last.
- **Buyers:** the owner wants all of them (developers, teams, regulated enterprise, cost-sensitive developers,
  agent vendors). Sequence in section 7 of the business doc.

### Decisions confirmed by the owner (2026-11-01, evening)

- **Brand v0.2 (K mark, Archivo / Instrument Sans / Martian Mono, ink + paper + one teal) is accepted for now.**
  It will be revisited later. Still no `DESIGN.md` until the owner says so.
- **Licence: agreed.** Permissive (Apache-2.0) for the runtime, CLI and Record specification; proprietary for
  Keelway Cloud and Enterprise. (The repo still has no LICENSE file and the README badge says proprietary; changing
  that is a separate, owner-approved step.)
- **Agent platform plan: agreed.** Order: Agent Manifest, private team registry, Studio builder, public verified
  registry last. First slice is on branch `feature/agent-manifest-and-record`.
- **Push and PR for this handoff: approved.**
- **Company name "Sorvex Labs":** open. Findings and recommendation are in `business-model-and-platform.md` section 8.

## 1. Where the product is (verified)

**Health:** 169 tests pass on `origin/main` (Python 3.14 venv, `pytest -q`, 2.4 s). CI runs `ruff` and `pytest`
on 3.11 and 3.12. About 9.7k lines of Python.

**Real and working**

| Area | Evidence |
|---|---|
| Agent loop with 6 tools (`read_file`, `write_file`, `edit_file`, `run_command`, `list_dir`, `search_codebase`) | `core/orchestration/agent_loop.py` |
| Autonomy policies: `autonomous`, `confirm_mutation`, `confirm_all` | same file, `AutonomyPolicy` |
| Scoped standing approvals ("Allow always" per tool + path glob or exact command, audited, revocable) | `core/security/approval_rules.py`, `78e062b` |
| API tokens, RBAC on every `/v1` route and the Studio WebSocket | `core/security/auth.py`, `rbac.py`, `tests/test_auth.py` |
| Hash-chained audit log with a verify endpoint, wired to a Studio Audit tab | `auth.py` `_chain_hash`, `verify_audit_chain`; `GET /v1/audit/verify` |
| DLP and prompt-injection firewall | `core/security/firewall.py` |
| Multi-provider gateway: Anthropic, OpenAI, Gemini, local (Ollama); failover; local-first cost router with privacy filter | `core/models/gateway.py`, `348b0cb` |
| Real workspace file IO, AST symbol index, git diff, Monaco editor on real data | `core/storage/workspace_fs.py`, `ast_index.py`, Studio |
| Studio: task-first home, runs, approval card with full `write_file` preview, i18n (8 languages, RTL), self-hosted assets | `studio.js` (~790 lines) |
| `keelway demo`, `keelway pull`, `keelway doctor`, `keelway token`, `keelway bench` | `cli.py` |

**Simulated or thin (the README already lists most of these)**

- **Embeddings are not semantic.** `core/storage/embedding.py` is a 128-dimension hashed n-gram projection
  ("deterministic pure-Python dense feature hasher"). It works as a lexical-plus-hash index. Calling it
  "semantic search" or "dense vector RAG" in the README or marketing overstates it.
- **There is no 4-tier safety gate in code.** The README and the older design spec say "4-tier". The code has
  three autonomy policies plus a single RBAC permission named `approve_tier3`. Any UI that draws four tiers
  must either match a real model or the model must be built first (see P0-1).
- Multi-agent mesh, P2P mesh, speculative decoding, payments, messaging and telephony are payload builders or
  in-memory simulations. MCP is an in-process dispatcher with no stdio or SSE transport. The mobile app is an
  Expo scaffold (`mobile/App.tsx` is 40 lines). OpenTelemetry is in-memory only.
- **Distribution:** only `install.sh` and `pip install -e .`. No PyPI release, Homebrew formula or desktop app.
- **Evals:** `evals/eval_runner.py` has 4 hand-written tasks (EVAL-01 to 04) plus `keelway bench` (10 tasks).
  Not run in CI, and no published numbers against a public benchmark.

**Status against the older shipping-gap doc** (`KEELWAY_SHIPPING_GAP_ANALYSIS_AND_ROADMAP.md`):

| Gap | Status |
|---|---|
| 1 Model cold start | Partial: `keelway pull` (Ollama) and `demo` exist; no bundled runtime, no in-Studio key onboarding |
| 2 Real file IO | Done |
| 3 Agent tool loop | Done |
| 4 Semantic indexing | Partial: AST index done; embeddings are hashed, not a model |
| 5 Two-way editor | Done (Monaco) |
| 6 Distribution | Not done |
| 7 Evals | Partial: runner exists, not in CI, no public benchmark |

## 2. Design direction (approved in principle, not applied)

**One-sentence feeling the owner picked:** "It's under control." Calm, legible, trustworthy command, like an
instrument panel. The audit log and the approval gate are the heroes.

**Idea ("interlocking"):** a railway signal box. Stopping is easy, proceeding is deliberate, and a quiet
screen means safe. Color is a claim: saturated pixels appear only for a real state.

**What already matches what Devin shipped (keep it):** the brand tokens in `core/studio/tailwind.input.css` say
"Keel teal = the agent is working, Signal amber = a human must decide". That is the same rule. Keep the Figma
palette, Inter, and JetBrains Mono for Studio. Do not swap the shipped fonts.

**Additions worth proposing (none are built):**

1. **A "stopped" state.** Add red as an explicit state (held or denied), distinct from the diff-red. Give each
   state a shape as well as a color (stop = square, needs-human = diamond, ok = circle) so it survives color
   blindness and grayscale. Keep diff colors muted so red and green keep meaning "blocked" and "verified".
2. **Gate rail (Studio):** a persistent right-side strip showing the current run's risk level, the one pending
   approval, and "chain intact". The approval card exists; this makes it persistent.
3. **Audit tape (Studio):** a continuous list of sealed entries (number, time, action, short hash) with a
   visible "Verify chain" control. The verify endpoint and a Studio verify action already exist.
4. **Website hero that shows the "no":** an action being held (for example `git push --force origin main`),
   Deny and Approve beside it, a sealed audit entry below, and a runnable
   `curl localhost:7420/v1/audit/verify` block with its real response instead of a logo strip. Draft headline:
   "The agent asked. Keelway held it." The market gap is real: every competitor in section 3 sells what agents
   can do; none shows an agent being stopped, approved, or verified.
5. **Mobile:** deny is one tap; approve is hold-and-slide plus biometrics, with the exact command shown first.
6. **Website only:** an optional display face (Archivo, variable width) for headlines. All three proposed
   families exist on Google Fonts (CSS API returned HTTP 200 with the variable axes). Licensing was not read
   from a license page; confirm OFL before shipping.

**Conflicts to raise with the owner before building**

- The shipped `.aurora` rule is a radial accent glow behind content. The direction above removes glow and
  gradients. Keep or drop?
- The proposal said "no brand accent". The shipped tokens already use teal as the brand accent (for
  "working"). Reconcile: either teal stays as a state color only, or it stays the brand color. Also decide
  whether teal ("working") and green ("ok") are distinct enough side by side.
- The "tier" lamps in the preview assume four risk levels ordered by blast radius. See section 1: that model
  does not exist yet.

**Assets:** `assets/design-preview-interlocking.html` is a self-contained mock of Studio, the website hero,
mobile and the tokens, with a dark/light toggle. It uses the old name and the proposed palette
(light: `#D9DCD3`/`#ECEEE8`/`#15191A`; dark: `#1E2624`/`#283230`/`#E6E9E3`; states: proceed `#1FBF98`,
caution `#F2A020`, stop `#F25C54`). It was never viewed in a rendered browser in the session that made it.
Open it and check it by eye before relying on it.

## 3. Competitors (external, unverified against vendor pages)

| Product | What it is | Why it matters here |
|---|---|---|
| **Devin Desktop** (Cognition; Windsurf was rebranded 2 June 2026) | Opens to an "Agent Command Center": a Kanban of local and cloud agents. Devin Local (Rust) plus Devin Cloud (VM, returns PRs). Supports ACP so Codex and Claude run side by side. "Spaces" share context and worktrees. | The closest product shape to the new Studio home. It treats agents as a fleet. |
| **Claude Code** | Terminal agent in a Claude subscription. Permission modes, hooks (PreToolUse can allow, deny or modify), OS sandboxing, and an "auto mode" where a classifier approves actions (reported March 2026). | Sets the bar for approvals and hooks. A governance layer has to beat built-in permissions or sit underneath them. |
| **Cursor** | Credit-based IDE agent. Reported price points: $20, $60, $200 per month. One source claims an August 2026 acquisition; I found no corroboration, so ignore it. | The default IDE. Its pricing complaints are Keelway's local-first opening. |
| **OpenAI Codex** | In ChatGPT plans, with a Windows-native sandbox and an enterprise plugin and MCP packaging system. | Same buyer as Keelway's enterprise story. |
| **Warp (Oz)** | Terminal client open-sourced April 2026; Oz runs many agents in the cloud, self-hostable; runs Claude Code and Codex inside it. | Shows the "host everyone's agents" direction. |
| **OpenCode, Kilo Code** | Open-source terminal and IDE agents. Star counts reported from about 95k to above 116k. | Free, popular, and the real baseline for "open source". |
| **Cline, Aider, OpenHands, Continue** | Open-source agents. Cline has the best step-by-step approval reputation; OpenHands needs Docker and a strong model; Aider is single-threaded. | Keelway's approvals have to be clearly better than Cline's to matter. |
| **Governance startups and open-source layers** | Approval proxies, audit and policy tools for Claude Code and MCP (lists such as `awesome-ai-agent-governance`). | A crowded niche already forming around exactly Keelway's pitch. |

**Trust numbers to use with care:** secondary sources report that most developers use AI tools but distrust the
output (one Sonar write-up says 96% do not fully trust it and 48% always verify before commit; Stack Overflow's
2025 survey had 46% distrusting accuracy versus 33% trusting). I could not confirm these against the primary
reports. Do not put them on the website until checked.

**Governance guidance that matches the audit design:** enterprise buyers ask for SSO, SIEM-connected audit logs,
RBAC, sandbox isolation and PR policy gates. One source argues an audit log is only credible if enforcement
is separate from reporting and approvals cover a specific declared action rather than a broad scope.
Keelway's scoped "Allow always" rules (tool + path glob or exact command) already follow that.

**Positioning (a recommendation, not a decision):** the products above compete as the agent or the IDE, and
they are well funded. Keelway's defensible ground is the control layer under any agent: local-first, scoped
approvals, a hash-chained audit log anyone can verify, DLP, and air-gap. Whether to be "a governed runtime
that also hosts other agents (via MCP and ACP)" or "our own agent" is the biggest open product question.

## 4. Recommended next work, in order

Each item is sized for one Devin session. "Verify first" means read the code before trusting section 1.

**P0: make the trust claims true and visible**

1. **One risk model, used everywhere.** Define explicit risk classes for tool calls (for example: read,
   edit inside workspace, run command, irreversible or outside-workspace such as force push, network or
   deleting). Map each autonomy policy and approval rule onto them. Expose it from the API so Studio, CLI and
   mobile read the same thing. Replace the "4-tier" wording in docs with whatever ships. Acceptance: one
   function classifies a tool call; tests cover force-push, `rm -rf`, writes outside the workspace.
2. **`run_command` isolation.** Verify first what `run_command` actually restricts. Competitors ship OS-level
   sandboxing. At minimum: cwd pinned to the workspace, env scrubbed of provider keys, timeouts enforced, and
   a deny list that the risk model in item 1 consults. Acceptance: a test that an agent cannot read
   `~/.ssh` or inherit `ANTHROPIC_API_KEY` through a command.
3. **Audit export and anchoring.** Add `GET /v1/audit/export` (JSONL, includes `prev_hash` and `entry_hash`)
   and a documented standalone verifier script that needs no server. Optionally write the head hash to a file
   or git note on each run so rollback of the database is detectable. Acceptance: verifier fails when a row is
   edited or deleted.
4. **Fix the "semantic" claim.** Either integrate a real local embedding model behind the existing
   `EmbeddingProvider` interface (optional dependency, ONNX or Ollama embeddings, hashed fallback), or
   reword the README, Studio and website. Add a retrieval test that a hashed index fails and a real one passes.

**P1: first-run and credibility**

5. **Zero-config first run.** In Studio, detect "no model available" and offer: connect a provider key,
   `keelway pull`, or run the demo. Today a clean machine fails at connection.
6. **Evals in CI with published numbers.** Run `keelway bench` on every PR, store results as an artifact, and
   add a public-benchmark subset (SWE-bench-lite style or Terminal-Bench). Include the prompt-injection and
   secret-exfiltration cases the gap doc promised. Publish one honest table in the README.
7. **Packaging:** PyPI release and a Homebrew tap. A signed desktop wrapper is later.

**P2: product depth**

8. **Run board (command-center view).** Several concurrent runs, each in its own git worktree (the self-heal
   engine already uses disposable worktrees), with states: working, needs you, held, done. Studio's task-first
   home is the foundation.
9. **MCP over stdio/SSE, and ACP.** So Claude Code, Codex, and Cursor can call Keelway's tools, and so
   Keelway can host other agents under its approvals and audit. This is what turns "another agent" into "the
   control layer".
10. **Mobile approvals for real:** push notification to a real device, biometric confirm, deny in one tap.
    Today it is a scaffold and the messaging module sends nothing.
11. **Trim the README.** It still leads with claims the code does not back (see the simulated list).

## 5. Questions for the owner (Justin)

Answered since writing: 1 (positioning: control layer first), 3 (Figma is not the source of truth), 4 (all buyers, sequenced). Still open: 2 (teal vs green and the glow: recommended answer in 0.1), 5 (licence).


1. Positioning: governed runtime under any agent, or our own agent? (section 3)
2. Are teal and green meant to coexist, and is the `.aurora` glow staying? (section 2)
3. Is the Figma file the single source of truth for Studio, and where does the website's design come from?
4. Who is the first buyer: defense and regulated teams (air-gap, audit) or cost-sensitive developers
   (local models)? The two lead to different P0 orderings.
5. License: the README says proprietary. The website preview draft mentioned "source available"; that line
   was a placeholder and should be removed or corrected.

## 6. Process notes for Devin

- Work from a branch off current `origin/main`. This doc and the preview live on
  `handoff/design-direction-and-roadmap` (local only, not pushed).
- Run tests with a venv: `python -m venv .venv && .venv/bin/pip install -e ".[dev]" pytest && .venv/bin/pytest -q`.
- The owner's global rule: new repos created for them get `~/.ai/bin/creova-bootstrap`. Not relevant to this
  repo, mentioned only so it is not forgotten if a new repo appears.
- Do not write `DESIGN.md` until the owner answers question 2 and confirms the Figma stays the source.
