# Status for Devin, 2026-11-02: where things stand and where to resume

Written after reviewing `main` @ `a8b327e` and every open PR. Verified items say how; everything else is from PR
descriptions and is labelled.

## 1. You are not blocked any more

Your recent PR descriptions say "doesn't touch the files in open PRs #17, #18 or #20". Those were my PRs, and they
were stale against your `cli.py` changes. They are fixed:

| PR | What | State now |
|---|---|---|
| **#20** | Stop passing API keys/tokens to commands an agent runs (`env_scrub.py`, README correction) | Merges cleanly into `main`. CI `test (3.11)` and `(3.12)` pass. **Merge this first; it's independent.** |
| **#17** | Agent Manifest v1 + portable Record format and standalone verifier (`core/agents/manifest.py`, `core/security/record_format.py`, `keelway agent ...`, `keelway record ...`) | `main` merged in, `cli.py` conflict resolved (kept your `keelway mcp` and my `agent`/`record`). Mergeable. CI passes. |
| **#18** | Manifest enforcement (`core/agents/guard.py`) **and the macOS sandbox** (#19 was merged into this branch, not into `main`) | `main` and #17 merged in. 323 tests pass on macOS. A Linux CI failure (guard tests assumed a sandbox backend) is fixed and verified by simulating a platform with no backend. Needs #17 merged first; GitHub then retargets it to `main`. |
| **#16** | These handoff docs | Docs only. |

**Recommended merge order:** #20, then #17, then #18, then #16 (any time).

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

## 3. Where I stopped, and how to continue

**In progress, not committed anywhere:** the API route that starts an agent run from a manifest. Nothing of it is
written. The plan, so you can take it if I do not:

1. In `core/api/routes.py` `run_agent_task`: accept an optional `payload["manifest"]` (inline JSON).
   - Validate with `core.agents.manifest.validate`. Invalid: HTTP 422 with `{"errors": [...]}` and an audit entry
     (`agent_run_manifest`, allowed=False).
   - If it carries a `signature`: verify against `<workspace>/.keelway/agent_signing.key`
     (`manifest.load_or_create_key` / `verify`); reject a bad one (400). Add a setting
     `require_signed_manifests` (default false) that rejects unsigned ones.
   - The manifest's `permissions.autonomy` becomes the policy; reject a conflicting `payload["policy"]`. The existing
     `approve_tier3` check for `autonomous` stays.
   - Build with `guard.loop_from_manifest(...)` (`ManifestNotRunnable` becomes 422 plus an audit entry). **Build it
     before the duplicate-`task_id` check, with `asyncio.to_thread`** (the sandbox self-test spawns processes), then
     check-and-register with no `await` in between, as the existing comment requires.
   - On success write the audit entry `agent_run_manifest` with `task_id name@version digest`.
2. In `step_agent_tool`: when the result is `denied_by_manifest`, `record_audit(principal, "manifest_denied",
   "<task> <tool>: <code> [<digest>]", False)`. This puts denials in the hash-chained audit log, not only the flight tape.
3. `AutonomousAgentLoop.get_state()`: add `"manifest": guard.summary()` (name, version, digest, steps used and max,
   signed). Expose it in `/v1/agent/status` and the runs list so Studio can show it.
4. `POST /v1/agents/validate`: dry run returning errors, warnings, digest, `guard.not_enforced(manifest)`, and whether
   it is runnable on this machine (`runnable`, `reason`).
5. Tests with the `client` fixture from `tests/test_approval_rules.py` (monkeypatch `routes._workspace_fs` and
   `_active_agent_loops`). Cover: invalid manifest, bad signature, autonomous without `approve_tier3` (auth marker),
   policy conflict, unrunnable, an out-of-scope step is denied **and** audited, in-scope step still pauses for approval.

## 4. Known gaps, ordered

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

## 5. Decisions that belong to the owner, not to you or me

- Company name (Keelway as company vs Sorvex Labs) and the brand direction. The owner accepted the v0.2 direction
  (K mark, Archivo/Instrument Sans/Martian Mono, one teal accent) *for now*, to be revisited at YC. Your landing page
  predates it and uses Inter and JetBrains Mono; do not restyle it without the owner saying so.
- Licence. Recommended: Apache-2.0 for runtime, CLI and the Record spec; proprietary for Cloud/Enterprise. There is
  still no LICENSE file.
- **`DESIGN.md` has deliberately not been written.** Do not create it without the owner's go-ahead.

## 6. Two ways to be wrong that I want to flag

- The sandbox is process confinement on a shared kernel, not a container. Do not describe it as one.
- This status is from reading PR text and running tests, not from using the product end to end.
