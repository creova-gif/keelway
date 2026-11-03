# Status for Devin, 2026-11-02: where things stand and where to resume

Written after reviewing `main` @ `a8b327e` and every open PR. Verified items say how; everything else is from PR
descriptions and is labelled.

## 1. You are not blocked any more

Your recent PR descriptions say "doesn't touch the files in open PRs #17, #18 or #20". Those were my PRs, and they
were stale against your `cli.py` changes. They are fixed:

| PR | What | State now |
|---|---|---|
| **#18** | **The whole agent-platform stack in one PR, targeting `main`.** Agent Manifest v1, run-time enforcement (`guard.py`), the macOS command sandbox, the manifest run route + audit entries (`POST /v1/agent/run` with `manifest`, `POST /v1/agents/validate`), and the portable Record format. #19 and #31 were merged *into this branch* (not into `main`), and #17's commits are included. | `main` merged in, mergeable, CI green on the tip (`test 3.11`/`3.12`). 343 tests pass on macOS. **Merging this lands everything.** |
| **#17** | Earlier slice of the same work | Redundant once #18 merges (its commits are in #18). Safe to close. |
| **#20** | Stop passing API keys/tokens to commands an agent runs | Independent. Merges cleanly into `main`. CI green. |
| **#32** | Redact credentials before they are written to a flight tape | Independent, new. Based on `main`, 237 tests pass. See section 4. |
| **#16** | These handoff docs | Docs only. |

**Recommended merge order:** #20, #32, then #18 (which makes #17 redundant), then #16 (any time).

**Nothing from the manifest, sandbox or Record work is on `main` yet.** That matters for the website, see section 4.

`core/orchestration/agent_loop.py` is safe to edit after #18 lands. My changes there are three small additive hooks
(`guard`, `command_runner`, and a result filter in `_run_approved_tool`) plus #20's `env=` argument.

`Vercel: Deployment was blocked` appears on my PRs. That is a Vercel team-access setting for the commit author, not a
code problem. The `test` jobs are the real signal.

## 2. What you shipped (reviewed, not re-verified line by line)

`main` is healthy: **206 tests pass, ruff clean, CI green** (I ran it locally on `a8b327e`).

| PR | Result | Your own caveat |
|---|---|---|
| #22/#23 Telegram/WhatsApp approval relay, blocked while air-gapped, nonce per message, audited as `remote_approval` | merged | **Not verified against live accounts** (needs a bot token / Cloud API credentials) |
| #24 Runnable Expo app: pairing, live runs, biometric approvals, air-gap, RTL | merged | Tested on Expo web against `keelway demo`; a real phone and push notifications were not tested |
| #25/#27 Local models: detects Ollama and vLLM/llama.cpp/LM Studio, routes local only when up | merged | |
| #28/#29 `keelway mcp`: stdio MCP server, read-only workspace tools for Cursor/Claude Code/Zed | merged | Behaviour change: tool errors return `result.isError: true` |
| #30 Website landing page, no third-party loads, same-origin only | merged | Screen-reader pass not done |
| #26 README quickstart fix | **open**, CI green | |

You also implemented, without the roadmap asking in these words: the MCP stdio transport (roadmap P2-9, the read-only
half), most of mobile approvals (P2-10), and local-model detection (part of P1-5).

## 3. What I built since the first version of this note

The manifest run route is **done** (it was only a plan here before): `POST /v1/agent/run` accepts a `manifest`
(validated 422, signature-checked 400, `require_signed_manifests` setting, autonomy taken from the manifest,
`approve_tier3` still required for `autonomous`, unrunnable manifests refused), `POST /v1/agents/validate` is a dry
run, and starts/refusals/blocked tool calls go into the hash-chained audit log with the manifest digest. All of it is
in #18. See `docs/spec/agent-manifest-v1.md` ("HTTP API").

**Next in line, not started:** a manifest registry (store by `name@version`, owner, enable/disable kill switch, a run
referencing a registered manifest instead of sending it inline), then a Studio view of the `manifest` block that
`/v1/agent/status` now returns.

## 4. Website and README claims checked against `main` (a8b327e)

I read `website/index.html` and checked each claim against the code. Most hold up (MCP hides credentials files,
private requests route to local only, the mobile app has English/Kiswahili/French/Arabic, tokens are stored as
hashes). These do **not** hold on `main` today:

1. **"The agent's manifest limits which tools and paths it may use. Anything outside that is refused."** There is no
   `core/agents` on `main`. It is true only after #18 merges. Until then, remove or soften the sentence.
2. **"Append-only, sealed run records with secrets removed."** I reproduced the opposite: an agent that reads `.env`
   or runs `cat .env` puts the key **verbatim** in the saved tape. **#32 fixes the "secrets removed" half** (best
   effort, pattern based; say "common credentials are removed", not "secrets removed"). The **"sealed"** half is weak:
   `tape_sha256` is stored inside the same file it covers, so it detects accidental corruption but anyone who edits a
   tape can recompute it. Either reword ("checksummed") or chain the tape hash into the audit log.
3. **"Any edit or deletion breaks the chain."** True for edits and for deletion in the middle. Cutting entries off the
   END of the log is not detected unless the head hash is published somewhere (`docs/spec/record-v1.md`). Say "edits
   and deletions in the middle", or add head anchoring.
4. **The "4-tier safety gate"** (README and older docs) does not exist in code: three autonomy policies and one RBAC
   permission. Your website does not use the phrase; check the README.

Not re-verified: the live Telegram/WhatsApp relay and the mobile app on a real phone (your own caveats).

## 5. Known gaps, ordered

1. **No Linux sandbox.** `core/agents/sandbox.py` works on macOS only (seatbelt). On Linux an agent with
   `run_command` and `sandbox: worktree` is *refused*, not run unconfined. A bubblewrap backend needs a Linux machine
   to test. The confinement tests skip on CI, so **CI does not prove confinement; run the suite on a Mac.**
2. **README/marketing vs code.** The README and older docs say "4-tier safety gate". The code has three autonomy
   policies and one RBAC permission (`approve_tier3`). Embeddings are hashed n-grams, not a semantic model. See
   `2026-11-01-design-direction-and-roadmap.md` section 1. Your website says it only claims what the code backs up;
   worth re-checking that against these two points.
3. Cost metering (`budget.max_usd_per_run`) is not enforced. MCP servers in a manifest are declared but unused.
4. Record export route (`GET /v1/audit/export`), head anchoring, per-entry signatures: see `docs/spec/record-v1.md`.
5. Run board for several concurrent runs, private team registry, Studio builder: `docs/spec/agent-manifest-v1.md`.

## 6. Decisions that belong to the owner, not to you or me

- Company name (Keelway as company vs Sorvex Labs) and the brand direction. The owner accepted the v0.2 direction
  (K mark, Archivo/Instrument Sans/Martian Mono, one teal accent) *for now*, to be revisited at YC. Your landing page
  predates it and uses Inter and JetBrains Mono; do not restyle it without the owner saying so.
- Licence. Recommended: Apache-2.0 for runtime, CLI and the Record spec; proprietary for Cloud/Enterprise. There is
  still no LICENSE file.
- **`DESIGN.md` has deliberately not been written.** Do not create it without the owner's go-ahead.

## 7. Two ways to be wrong that I want to flag

- The sandbox is process confinement on a shared kernel, not a container. Do not describe it as one.
- This status is from reading PR text and running tests, not from using the product end to end.
