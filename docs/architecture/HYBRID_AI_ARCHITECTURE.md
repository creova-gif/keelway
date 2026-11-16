# Keelway — Hybrid AI Architecture Specification

> **Version**: 1.0  
> **Status**: Approved Architecture  
> **Scope**: Universal Model Ingestion, Routing Engine, Privacy Fail-Closed, Cost Accounting

---

## 1. Architectural Philosophy: Both Model Classes as First-Class Citizens

Keelway rejects vendor lock-in and the binary choice between proprietary cloud models and self-hosted models. Both categories are first-class citizens within the Keelway unified inference fabric:

1. **Open-Weight Models** (e.g. Qwen 2.5 Coder, Llama 3.3 70B, DeepSeek R1 / V3, Mistral NeMo):
   - **Deployment Topologies**: Local daemons (Ollama, llama.cpp) for offline development, workstations, and edge nodes; private self-hosted GPU clusters (vLLM, TGI, Triton) for enterprise cloud/VPC workloads.
   - **Key Advantages**: Zero external data egress, deterministic privacy, sovereign control, immunity to cloud API outages, and $0.00 incremental token cost.
2. **Closed / Frontier Proprietary Models** (e.g. Claude 3.5/3.7 Sonnet, GPT-4o, OpenAI o1/o3-mini, Gemini 1.5/2.0 Pro):
   - **Deployment Topologies**: Managed cloud APIs accessed via enterprise zero-retention agreements.
   - **Key Advantages**: Peak reasoning benchmarks for complex architectural decisions and large-scale synthesis.

---

## 2. Model Tier Taxonomy & Metadata Schema

Every model integrated into Keelway is registered in `core/models/registry.py` under the `ModelMetadata` schema:

```python
class ModelCategory(str, Enum):
    OPEN_WEIGHT = "open_weight"
    CLOSED_PROPRIETARY = "closed_proprietary"

class DeploymentType(str, Enum):
    LOCAL_DAEMON = "local_daemon"         # Ollama, llama.cpp
    SELF_HOSTED_GPU = "self_hosted_gpu"   # Private vLLM/TGI cluster
    MANAGED_CLOUD_API = "managed_cloud_api" # OpenAI, Anthropic, Google
```

### Canonical Registry Matrix

| Model Identifier | Category | Family | Default Deployment | Context | Capabilities | Input/Output Rate ($/Mtok) |
|---|---|---|---|---|---|---|
| `qwen2.5-coder:7b` | `open_weight` | Qwen | `local_daemon` | 32,768 | Chat, Code, Tools, Streaming | $0.00 / $0.00 |
| `qwen2.5-coder:32b` | `open_weight` | Qwen | `self_hosted_gpu` | 32,768 | Chat, Code, Tools, Streaming | $0.00 / $0.00 |
| `llama-3.3:70b` | `open_weight` | Llama | `self_hosted_gpu` | 131,072 | Chat, Code, Reasoning, Tools | $0.00 / $0.00 |
| `deepseek-r1:latest` | `open_weight` | DeepSeek | `self_hosted_gpu` | 65,536 | Reasoning, Code, Math | $0.00 / $0.00 |
| `mistral-nemo:12b` | `open_weight` | Mistral | `local_daemon` | 128,000 | Chat, Multilingual, Tools | $0.00 / $0.00 |
| `gpt-4o` | `closed_proprietary` | GPT | `managed_cloud_api` | 128,000 | Multimodal, Tools, Fast | $2.50 / $10.00 |
| `claude-3-5-sonnet` | `closed_proprietary` | Claude | `managed_cloud_api` | 200,000 | Code, System Design, Analysis | $3.00 / $15.00 |
| `gemini-1.5-pro` | `closed_proprietary` | Gemini | `managed_cloud_api` | 2,000,000 | Extreme Context, Multimodal | $1.25 / $5.00 |

---

## 3. Deterministic Routing Engine & Policy Enforcement

The Model Gateway (`core/models/gateway.py`) evaluates every incoming completion or streaming request across four sequential policy stages:

```
[ Inbound Request ] 
        |
        v
[ Stage 1: Explicit Request Override ] ---> Did caller request a specific model ID?
        |
        v
[ Stage 2: Privacy & Air-Gap Constraint ] --> Is `is_private=True` or `air_gap=True`?
        |                                       IF YES: Filter candidate pool strictly to
        |                                       ModelCategory.OPEN_WEIGHT.
        |                                       Any attempt to target cloud raises AirGapViolationError.
        v
[ Stage 3: Capability & Workload Match ] ---> Requires code generation, vision, or extreme context?
        |
        v
[ Stage 4: Health & Latency Probe ] --------> Is local Ollama/vLLM daemon responsive?
        |                                       IF NO & not private: Fall back to cloud backup.
        v
[ Execution via Provider Adapter ]
```

### Privacy Fail-Closed Invariant

> **INVARIANT**: If a payload is flagged with tenant privacy or air-gap requirements, cloud models (`closed_proprietary`) are structurally inaccessible. Under no circumstances may an automatic fallback re-route a private payload to an external provider API. If no local open-weight model is available, the request **fails closed** with an HTTP 403 Forbidden (`AirGapViolationError`).

---

## 4. Economic Observability & Sovereign Cost Ledger

Keelway maintains an active accounting ledger in `core/models/cost_ledger.py` recording every inference:
- **Cloud Expenditure Tracking**: Accurately accounts for external API spend per model rate card.
- **Quantified Local Savings**: Evaluates how much an open-weight execution would have cost had it run on frontier cloud models (e.g. Claude 3.5 Sonnet baseline).
- **Sovereign Efficiency Index (SEI)**: A composite score (0..100) balancing:
  - 50% Local Autonomy Ratio (fraction of requests served without cloud egress)
  - 30% Economic Benefit (net savings vs external spend)
  - 20% Latency Responsiveness (P95 latency under 100ms)

All metrics are queryable via `GET /v1/usage`.
