# 06 — AI Engineering Framework (verified)

## Model gateway (`core/models/`)

- `ModelGateway.adapters: Dict[Provider, Union[ModelAdapter, BaseModelProvider]]`
  — legacy `ModelAdapter.complete(CompletionRequestSchema)` and modern
  `BaseModelProvider.complete(ChatCompletionRequest)` coexist with
  isinstance dispatch (KEEL-ENG-062 made this explicit).
- Providers: `local` (OpenWeight→Ollama/vLLM), `cloud` adapters for
  Anthropic/OpenAI/Gemini; `MockTransport`/`ASGITransport` used in tests.
- Routing honesty: `routing_reason` discloses fallbacks; `private`
  payloads raise `AirGapViolationError`; `request.model` defaults to
  `keelway-core:7b` (simulated path, labeled).

## Runtime (`core/opencore/`)

- `OllamaBridge` forwards inference; **hardcodes 127.0.0.1:11434**
  (P0-6 — ignores `OLLAMA_BASE_URL`; wedges seen live ~120 s timeouts).
- vLLM bridge + serving layer; `stream_complete` async-generator
  contract on all adapters.

## Eval / conformance

- `evals/` + `core/eval/` — mirofish swarm benchmarks, conformance
  scenarios (`DEFAULT_CONFORMANCE_SCENARIOS`), pricing simulator.
- Known flake: `MiroFishSwarmHarness` event-loop deadlock (P1-1).

## Token & cost controls

- Cost ledger in `core/storage/ledger.py` (tokens, $, savings vs cloud).
- Quota/pricing simulator panel in dev-app.

## Tool-permission boundaries

- Agent commands run only inside verified sandbox; P-10 human gate
  (`P10ApprovalCard`) for high-risk actions; tiered autonomy in AGENTS.md §6.

## Prompt-injection posture

- Env scrubbing before subprocess (`scrub_env`), secrets never into
  tapes; supply-chain validation on tool manifests
  (`SupplyChainValidationError`). Dedicated injection test cases: P1 scope.
