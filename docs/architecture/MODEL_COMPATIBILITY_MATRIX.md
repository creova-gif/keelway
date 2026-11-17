# Keelway Model Compatibility Matrix — Tested Evidence

> **Phase 6 deliverable.** Every cell states what is *verified* (with reproducible
> evidence), what is *implemented but unverified*, and what is *not supported*.
> We do not claim universal compatibility. Last verified: 2026-11-17.

Status legend: **VERIFIED** = exercised against a real runtime or the authoritative
test suite with named evidence · **IMPL** = code path exists, covered only by
unit tests/mocks · **NO** = not implemented / not claimed · **GATED** = blocked
externally (quota, auth, vendor EOL) — infrastructure proven to the boundary.

## 1. Provider × Capability

| Provider | Detect / health | Chat completion | Streaming | Tool calling | Structured output | Failover | Evidence |
|---|---|---|---|---|---|---|---|
| **Ollama** (local daemon) | VERIFIED | VERIFIED | VERIFIED | IMPL | IMPL | VERIFIED (auto-select chain) | `keelway-core:7b` → `qwen3.5:latest` live completion ~6.3s, `simulated:false`, alias disclosed in routing reason (2026-11-16). `tests/test_local_adapter.py`, `tests/test_opencore_runtime_alias.py` |
| **vLLM** (self-hosted) | IMPL | IMPL | IMPL | NO | NO | VERIFIED (chain position OLLAMA→VLLM→MOCK) | Adapter code `core/models/adapters/local.py`; no live vLLM endpoint available on test host |
| **Mock / simulated** | VERIFIED | VERIFIED | VERIFIED | NO | VERIFIED | n/a (terminal fallback) | Flagship aliases degrade to `simulated:true` with disclosure; full suite relies on it |
| **Anthropic** (`anthropic` adapter) | IMPL | IMPL | IMPL | NO | NO | NO | `core/models/adapters/anthropic.py`, `tests/test_anthropic_adapter.py`; no live call verified — requires `ANTHROPIC_API_KEY` |
| **OpenAI** (`openai` adapter) | IMPL | IMPL | IMPL | NO | NO | NO | `core/models/adapters/openai.py`; no live call verified — requires `OPENAI_API_KEY` |
| **Gemini** (`gemini` adapter) | IMPL | IMPL | IMPL | NO | NO | NO | `core/models/adapters/gemini.py`, `tests/test_gemini_adapter.py`; no live call verified |
| **Open-weight** (`open_weight`, HF/served) | IMPL | IMPL | VERIFIED (SSE `stream_complete`) | NO | NO | VERIFIED (privacy fail-closed routing) | `core/models/adapters/open_weight.py`; air-gap routing proven — `AirGapViolationError` on classified egress |

## 2. Keelway model IDs × backend resolution (KEEL-PROD-041)

| Model ID | Kind | Auto-select order | Verified resolution | If no runtime |
|---|---|---|---|---|
| `keelway-core:7b` | runtime alias | OLLAMA→VLLM→MOCK | `qwen3.5:latest` (Ollama, live 2026-11-16) | `simulated:true` mock, disclosed |
| `keelway-coder:7b` | runtime alias | OLLAMA→VLLM→MOCK | registry + alias tests | `simulated:true` mock, disclosed |
| `keelway-reasoning:14b` | runtime alias | OLLAMA→VLLM→MOCK | registry + alias tests (canonical ID; `keelway-reasoner:*` fixture drift swept 2026-11-17) | `simulated:true` mock, disclosed |
| `keelway-nano:1.5b` | explicit simulation | MOCK only | `simulated:true` by design | n/a |

**GGUF artifacts**: manifests exist as placeholders with `artifact_verified:false`.
No verified proprietary weight-hosting claim is made anywhere (KEEL-PROD-042 is
founder-gated). **BYOM**: customer models register via `ModelMetadata` +
provider adapters — unverified against third-party registries.

## 3. Third-party agent hosts (external inference surface)

| Host | Detect | Launch | Policy verdicts | Live session | Live permission request | Evidence / limit |
|---|---|---|---|---|---|---|
| `hermes_acp` 0.22.5 | VERIFIED (`--check` probe) | VERIFIED | VERIFIED | VERIFIED (86 events, `end_turn`) | **VERIFIED** — ALLOW on `.env` edit (`hint-9a33253240b2`) **and HOLD_TICKET on live `git reset --hard`** (`hint-50968b6320c1` → `ptkt-b767068fbfab`, command not executed) | DENY fixture-verified + content-DLP e2e (KEEL-ENG-053): Hermes doesn't gate cred reads, its model refused `~/.ssh` writes pre-tool-call; edit bodies now fold into evaluation → `sk-*` in proposed writes → real DENY |
| `claude_code` | VERIFIED | VERIFIED | VERIFIED (hooks + intercept CLI) | GATED (daily quota 104%, resets midnight) | n/a | Hook delivery proven to vendor boundary |
| `codex_cli` | VERIFIED | VERIFIED | VERIFIED | GATED (usage limit ~Nov 20) | n/a | Same boundary |
| `cursor` | VERIFIED | VERIFIED | VERIFIED — official schema pinned (`preToolUse`/`sessionEnd`, lowercase) | GATED (`agent login` required) | n/a | Contract test against pinned `cursor.com/docs/hooks` schema |
| `opencode` | VERIFIED (adapter) | VERIFIED | VERIFIED (`git push`→HOLD_TICKET+`ptkt-*`, exit 2) | NO (`opencode` not installed) | n/a | TypeScript plugin `tool.execute.before/after`; 1.x can't return "ask" |
| `gemini_cli` (`--acp`) | VERIFIED | VERIFIED | VERIFIED | **VENDOR-EOL** — `-32000` "migrate to Antigravity" at `session/new` | n/a | Google retired Code Assist individual OAuth; not an ACP-bridge defect |

## 4. Cross-cutting guarantees (verified)

- **Privacy fail-closed**: `private`/`air_gap`/classified payloads route local-only; cloud egress raises `AirGapViolationError` (403). Test suite enforces.
- **Usage accounting**: `tests/test_model_cost_ledger.py`, `tests/test_model_economics.py` — token/cost ledger per request.
- **Routing disclosure**: alias-capable models emit `runtime_model=...` in routing reasons; simulated responses are labeled `simulated:true`.
- **No universal claim**: this matrix is the compatibility contract — cells not marked VERIFIED are not claimed.

## 5. How to re-verify

```bash
# Provider adapters + registry + routing
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/test_local_adapter.py tests/test_hybrid_adapters.py \
  tests/test_hybrid_routing_and_api.py tests/test_opencore_runtime_alias.py \
  tests/test_anthropic_adapter.py tests/test_gemini_adapter.py -v

# External agent hosts
PYTHONPATH=. .venv/bin/python -m pytest tests/test_external_agent_adapters.py -v

# Live ACP session (requires hermes-acp on PATH)
keelway harness agents acp --host hermes_acp --prompt "reply with ACP_OK" --tape /tmp/acp-tape.json
```
