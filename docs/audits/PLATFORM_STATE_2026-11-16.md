# Keelway Platform State Audit — 2026-11-16

> Evidence-based audit per the Platform Development Directive. All claims below are backed by command output, merged commits, or file inspection on `main` @ `6d82a4c`. Supersedes nothing; complements `KEELWAY_CURRENT_STATE_2026-11.md` and `current-state-2026-11-05.md` (the latter is marked superseded).

## 1. Live Verification Evidence (this session)

Isolated stack launched via `.cursor/skills/verify-keelway` (`/tmp/keelway-verify-run1`, port 53565, ephemeral token, isolated `HOME` + `platform_runtime.db`):

| Check | Result | Evidence |
|---|---|---|
| `control-keelway doctor` | 6/6 invariants green (server+Chrome alive, isolated DB, auth gate owned, overview 200, React `/app` hydrated, workspace `default`) | `/tmp/keelway-evidence-directive/` |
| `GET /v1/platform/overview` | 200 — workspace, 12 agent views, branch, active model | `01-overview.json` |
| `cli.py workspace list --json` | 200 — `default` + `hipaa-intake` (airgap_strict) workspaces | `02-cli-workspace.json` |
| `GET /v1/models` | 15-model registry: 10 open_weight + 5 closed_proprietary | `03-models.json` |
| `POST /v1/chat/completions` `keelway-core:7b` | **SIMULATED** canned reply, 12.5 ms — now disclosed via `simulated: true` (KEEL-ENG-038) | `04-chat-local.json` |
| `POST /v1/chat/completions` `qwen3.5:latest` | **REAL** Ollama inference, 5.6–8.2 s; empty `content` when `max_tokens` consumed by thinking trace | `05/07-*.json` |
| `POST /v1/chat/completions` `qwen2.5-coder:7b` | `model_unavailable` — fail-closed, correct | `06-chat-qwen25.json` |

Host Ollama: `qwen3.5:latest` installed (7.6 GB). It is the only chat model present.

## 2. Shipped vs. Simulated — Verified Inventory

### Real, tested functionality
- Hybrid model gateway: `/v1/chat/completions`, `/v1/responses`, `/v1/routing/explain`; privacy fail-closed (`private`/`air_gap`/classified → local only, `AirGapViolationError` 403).
- **Real local inference works**: Ollama adapter (`core/models/adapters/local.py`, `open_weight.py`) performs live `/api/chat` calls with runtime model discovery (`/api/tags` probe, 30 s TTL).
- Unified 10-view dev app (`/app`) + `web-console` + VS Code extension (webview now zinc-branded).
- SQLite WAL governance store, hash-chained audit, P-10 dual-human approval (trusted-click enforcement verified by skill design).
- Seatbelt (macOS) / Bubblewrap (Linux) sandboxing; AES-256-GCM vault; SSRF-hardened HMAC webhooks; CycloneDX SBOM endpoint; 16-probe golden eval suite.
- Marketplace Ed25519 manifest verification + settlement ledger; first-party signing now env/key-file managed, fail-closed (KEEL-SEC-030).
- Tri-language SDKs (Python/TS/Go), ~150 test files, CI matrix, `requirements.lock` + freshness gate (KEEL-ENG-032).
- Migration census CLI: `keelway doctor --migration-check` (KEEL-ENG-033).

### Simulated / prototype — must not be marketed as production
| Surface | Reality |
|---|---|
| `keelway-*` registry models (10 advertised) | Mock backend canned replies; `simulated: true` now disclosed (KEEL-ENG-038). No real weights mapped. |
| OIDC/SAML enterprise SSO | Self-issued HS256 shared-secret profile only; `federation_profile: "self_issued_hs256"` disclosed; SAML unimplemented (KEEL-SEC-037). |
| `payment_broker` | In-memory intents; env secret now required, fail-closed (KEEL-SEC-031); no processor. |
| Speculative decoding cost figures | Heuristic estimates, not measured. |
| Cluster scheduler | Single-process bookkeeping, not distributed. |
| Several CLI paths (`pay`, `mesh`, `heal`, `pilot`) | Simulated. |
| `sso_saml_required` policy flag | Checklist marker only. |

## 3. CLI / Studio Functionality Matrix (verified surfaces)

| Surface | Status | Notes |
|---|---|---|
| `cli.py` (~70 subcommands) | Working | `doctor`, `workspace`, `vault`, `eval-suite`, `migration-check` verified live; several subcommands simulated (above) |
| Dev App `/app` (10 views) | Working | React 19 hydrated in isolated run; axe-core WCAG tests pass in CI |
| `web-console` | Working | zinc tokens migrated (KEEL-WEB-029) |
| VS Code extension | Working | bridge + step-debugger webview; palette migrated (KEEL-WEB-035) |
| Shared policy/runtime | Yes | Both surfaces share `SecurityGateway`, approval tokens, flight tape, WAL store |

## 4. Model & Runtime Compatibility Matrix

| Provider | Status | Evidence |
|---|---|---|
| Ollama (`/api/chat`, `/api/tags`) | **Real** | live qwen3.5 inference verified |
| OpenAI-compatible local (vLLM/llama.cpp/LM Studio) | Implemented, untested live | `local.py` `/v1/chat/completions` path |
| `keelway-*` OpenCore models | **Mock only** | canned replies; needs weight mapping or bundled GGUF |
| Frontier (OpenAI/Anthropic/Gemini) | Implemented adapters | requires customer keys; privacy-gated |
| Thinking models (qwen3.5, deepseek-r1) | Works but `thinking` trace not surfaced; empty `content` if `num_predict` exhausted by reasoning | observed live |

## 5. Priority-Ordered Gap Register

1. **P1 — `keelway-*` models have no real weights.** Either map to installed Ollama models, ship GGUF bundles, or relabel registry entries as simulated. *(Decision needed: product vs. honesty.)*
2. **P1 — Thinking-model UX.** Surface `message.thinking` or auto-raise `num_predict`; empty `content` responses confuse agents.
3. **P2 — Model registry vs. reality.** `/v1/models` advertises 15 models; only installed ones are callable. Add `installed`/`simulated` fields to registry output.
4. **P2 — Real OIDC federation** (discovery + JWKS + asymmetric algs) if enterprise SSO is in scope.
5. **P2 — ADR-0042 Phase 2** consolidation planning (collisions documented in KEEL-ENG-033).
6. **P3 — Payment processor**, cloud control plane, third-party agent integrations (MCP exists for tools; agent-level ACP/Codex/Claude Code adapters unverified).

## 6. Recommended Next Implementation PRs

- **KEEL-ENG-039**: `/v1/models` returns `installed` + `simulated` flags per model (registry-vs-reality fix, small).
- **KEEL-ENG-040**: Ollama thinking-model handling — pass through `thinking` or bump token budget; never return empty `content` silently.
- **KEEL-PROD-041**: Founder decision — real weights for `keelway-*` vs. registry relabel.

*All acceptance cases in `keelway_architecture_v71/` remain `DEFINED_NOT_RUN`; architecture generation is frozen per ADR-091.*
