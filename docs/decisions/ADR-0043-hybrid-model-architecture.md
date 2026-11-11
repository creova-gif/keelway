# ADR-0043: Hybrid Model Architecture and Agnostic Provider Abstraction

## Context
Keelway initially inherited codebase patterns oriented toward single-model or ad-hoc local model executions without a formal abstraction layer, unified catalog, or clean coexistence with commercial frontier models.

To evolve Keelway into a commercially viable, enterprise-grade AI engineering platform, the system requires first-class support for both downloadable open-weight models (Qwen, Meta Llama, Mistral, DeepSeek) and closed proprietary commercial APIs (OpenAI, Anthropic, Google Gemini), while strictly preventing vendor lock-in, unmetered cost overruns, and data residency leaks.

## Decision
1. **Centralized Model Registry:** Implement a unified catalog (`core/models/registry.py`) holding immutable metadata for open-weight and proprietary models (context window, capabilities, licensing, pricing, and hardware requirements).
2. **Provider Normalization Abstraction:** Establish `BaseModelProvider` (`core/models/provider.py`) defining uniform contracts for non-streaming completions, SSE chunk streaming, token metrics, and typed error hierarchies.
3. **Local-First Cost Arbitrage:** Default routing directs requests to local/self-hosted open-weight instances ($0.00 marginal API cost). Escalation to commercial cloud providers occurs only when requested capabilities (e.g., vision, 128k context) or user preferences demand frontier models.
4. **Hard Fail-Closed Privacy Boundary:** When `privacy_level == "private"` or air-gap mode is active, cloud providers are strictly excluded. Explicit requests for cloud models under private mode fail closed with a permission error.
5. **OpenAI-Compatible Unified API:** Expose `GET /v1/models`, `POST /v1/chat/completions` (supporting both streaming and non-streaming), and `GET /v1/usage`.

## Consequences
### Positive
- Zero structural vendor lock-in: swapping providers requires no application rewrites.
- Substantial cost savings: routine developer requests operate at zero cloud cost.
- Complete regulatory and data sovereignty compliance: sensitive source code never leaves the host machine when private mode is engaged.
- Backward compatibility: existing `POST /v1/completions` and agent task loops remain 100% functional.

### Negative / Trade-offs
- Local open-weight models require developer workstations with sufficient unified memory or VRAM (minimum 8 GB RAM for 7B models).
- Maintaining rate-card pricing in the model registry requires periodic synchronization as commercial providers update their pricing.
