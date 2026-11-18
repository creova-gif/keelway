# Keelway current state — November 2026

Verified on `main` at `15383607b23829c1282973e2eca336cd6284d5bd` (2026-11-08), Ubuntu 22.04 VM, Python 3.11 venv.
Baseline `073d5e86e3dba727c4dd0e561e24927e98fe51db` is an ancestor of `main`; 26 commits since
(`git rev-list --count 073d5e8..main`). This file supersedes the counts and gate claims in
[current-state-2026-11-05.md](current-state-2026-11-05.md); that audit describes a different checkout
(`10265a5`, a macOS path, Python 3.14, a live Ollama daemon) and its deployment URL now returns 404.

Labels: **VERIFIED WORKING** (ran it here), **IMPLEMENTED BUT UNVERIFIED** (code + unit tests, not exercised
end to end here), **PARTIAL**, **PLANNED** (docs only), **BROKEN**, **DEPRECATED**, **UNKNOWN**.

## 1. Build and test baseline

| Check | Result | Evidence |
|---|---|---|
| `ruff check .` | VERIFIED WORKING: clean | local run |
| `pytest -q` (Profile A) | 845 passed, 16 skipped, 1 deselected | local run, 327 s |
| Real-model test `test_slice2_..._real_local_model` | BROKEN (nondeterministic): local model answered `a - b` for `a * b` | earlier local run with Ollama |
| CI `test` 3.11 / 3.14 | passing | PR #40 checks |
| CI `test` 3.12 | BROKEN on main: `test_workspace_filesystem_safe_path_resolution` ~118–120 µs vs 100 µs SLA | PR #40 and main checks |
| CI `release-live-verification` | BROKEN on Linux by design: needs a live Ollama model and the 13 macOS seatbelt proofs | `tests/release_live_gate.py` |
| The "862 passed / all 10 beta gates satisfied" claim | Not reproducible: CI on main is red | §1 above |

## 2. Subsystems

| Area | Status | Evidence / notes |
|---|---|---|
| Agent loop (`core/orchestration/agent_loop.py`) | IMPLEMENTED BUT UNVERIFIED end to end with a real model | unit + e2e tests pass with fakes; real-model test flaky |
| Task state machine (`core/orchestration/state.py`) | IMPLEMENTED; state inventory aligned: `decision-precedence.md` §2 and `TaskState` both enumerate the canonical 16 states | `TaskState` |
| Approvals: one-time + scoped "Allow always" | VERIFIED WORKING (Studio, PRs #14/#15) | `tests/test_approval_rules*.py` |
| Hash-chained audit + flight tapes | IMPLEMENTED BUT UNVERIFIED externally (tests verify chain) | `core/security/audit*`, `core/orchestration/flight_recorder.py`, `core/platform/flight_tape.py` |
| API auth + RBAC | IMPLEMENTED, tested | PR #5, `keelway token` |
| **Command execution** | **BROKEN for the Studio/chat agent**: `run_command` fails closed unless `command_runner` is set; only `core/agents/guard.py::loop_from_manifest` sets it. Studio (`core/api/routes.py:1511`), chat (`core/orchestration/chat.py:408`), `m1_slice`, `pilot` never do, so those agents cannot run tests | `agent_loop.py:203-221` |
| macOS sandbox (seatbelt) | IMPLEMENTED BUT UNVERIFIED here (no macOS) | `core/agents/sandbox.py::SeatbeltBackend` |
| Linux sandbox (bubblewrap) | **BROKEN on main**: with `bwrap` installed, `Sandbox.verify()` fails (home readable, secret leaked, `.git`/`.keelway` writes not blocked). Fixed in PR #41 (verify passes) | `BubblewrapBackend.wrap` |
| gVisor / Kata / containers | PLANNED | no code |
| `core/agents/builder.py:312` `shell=True` | needs review: host shell path outside the sandbox | grep |
| Local models (Ollama, vLLM, llama.cpp, LM Studio) | VERIFIED WORKING with a real Ollama model (PR #25) | `core/models/adapters/local.py` |
| Cloud escalation | IMPLEMENTED; default `LOCAL_ONLY`, no silent fallback | `decision-precedence.md`, gateway tests |
| Air-gap | PARTIAL: gateway + messaging honor it; startup line `Air-Gap: off` does not read config (PR #34 F6); commands rely on the sandbox `--unshare-net` | `core/security/airgap*.py` |
| MCP stdio (read-only tools) | VERIFIED WORKING with the official MCP Python SDK (PR #28/#29) | `keelway mcp` |
| Telegram / WhatsApp approvals | IMPLEMENTED BUT UNVERIFIED against real bots | PR #22/#23 |
| Mobile (Expo, `mobile/`) | PARTIAL: verified as Expo web build only; no device build | PR #24 |
| Studio (web UI, `core/studio/`) | VERIFIED WORKING locally (PR #13 onward); proof strip invented values until Package B | PR #35 notes |
| Desktop IDE (Electron / Theia / Tauri) | PLANNED: `keelway desktop` opens a Chrome app window; README: "There is no Electron or Tauri app in this tree" | `README.md`, `docs/designs/keelway-dual-mode-sovereign-ide.md` |
| KStack (4 built-in skills) | IMPLEMENTED; no `pin` CLI subcommand (PR #34 F8) | `core/kstack/` |
| KBrain / KFlow / KHub / KSpaces / mesh / heal / speculative | PARTIAL or simulated; `core/models/speculative.py` figures are heuristic (`tokens_gen * 35.0`) | PR #35 finding 5 |
| Payments | **simulated only**: `core/storage/payment_broker.py` (M-Pesa, PIX, UPI, L402, vouchers), `POST` route defaults to `mpesa` (`routes.py:785`), Studio rail picker. No cards, no provider, no webhooks | grep |
| Entitlements | PARTIAL: source-default certificate refused (`SOURCE_DEFAULT_REFUSED`) | `core/billing/entitlements.py` |
| TPM / PIV / WORM HAL | experimental, software-simulated | `decision-precedence.md` |
| Website `kora-sable.vercel.app` | VERIFIED live (200); `get.keelway.dev` does not resolve; fonts mix DM Mono with Inter/JetBrains Mono (brand-kit conflict with `decision-precedence.md`'s Instrument Sans/DM Mono) | curl, `website/styles.css` |
| CLI | IMPLEMENTED: 35+ subcommands, several simulated (`pay`, `mesh`, `heal`, `pilot`). Must run via `.venv/bin/python cli.py`; system `python3.11` fails importing `core.config` | `cli.py --help` |

## 3. Duplication

Three runtime packages coexist: `core/` (~23k lines, the live product), `keelway/` (~4.7k lines: api, approvals,
audit, cli, mcp, policy, runner, sandbox…) and `keelway_core/` (reference workflow engine). `pyproject.toml`
exposes both `keelway = cli:main` and `keelway-core = keelway.cli.main:main`. Which package owns sandbox,
approvals and audit must be decided before more code lands; until then, new work goes in `core/`.

## 4. Open branches

| PR | State | Finding |
|---|---|---|
| #34 docs D, #36 C fail-closed | draft | every commit already on main (`git cherry` = 0 unmerged); can be closed |
| #35 B runtime truth | draft | one commit left, equivalent subject already on main (`d648a7f`); check then close |
| #26 README quickstart | open | 1-line fix still unmerged |
| #41 Linux sandbox | open | fixes §2 bubblewrap |

## 5. Responsibility matrix (beta)

| Concern | Authoritative owner | Never owned by |
|---|---|---|
| Approvals, policy, audit, flight tape | trusted local runtime (`core/`) | Studio, mobile, website |
| Command execution | `core/agents/sandbox.py` verified backend | host shell |
| Model routing + cost ceilings | `core/models/gateway.py` | UI |
| Entitlements / payment state | backend + provider webhooks (planned) | browser redirect |
| Air-gap state | runtime config, enforced at gateway, messaging and sandbox | UI toggle alone |
| Rendering, i18n/RTL, a11y | Studio, mobile, website | — |

## 6. Beta blockers, in order

1. Linux sandbox confines nothing → PR #41.
2. Studio/chat agents cannot run commands or tests: give them the same verified sandbox runner as `loop_from_manifest`, fail closed when unverified.
3. CI red on main: perf SLA on 3.12 (measure variance before touching it); release gate design needs a Linux profile or an explicit macOS runner.
4. Doc truth: state count, fonts, stale audit numbers.
5. Payments: remove simulated rails from user-facing paths until a card-first provider is chosen (needs the incorporation country).
