# Keelway OpenCore — Sovereign Foundation Models & Serving Architecture

## 1. Executive Summary & Mission

**Keelway OpenCore** is the native open-weight foundation model subsystem of the Keelway platform. Designed from the ground up for **sovereign AI engineering**, OpenCore guarantees:
- **Zero Cloud Egress**: Weights and user prompts remain confined entirely to local memory or customer-controlled virtual private clouds (VPCs) with \$0.00 cloud API billing.
- **Hardware-Adaptive Quantization**: Dynamic profiling that selects optimal quantization levels (GGUF `Q4_K_M`, `Q8_0`, `Q4_0`, or `AWQ_4BIT`) tailored to available Apple Silicon Metal, NVIDIA CUDA, or low-memory edge CPU nodes.
- **Multilingual Sovereignty**: Native instruction tuning and domain adaptation recipes for major African languages (Swahili, Yoruba, Hausa, Amharic) alongside global languages and high-assurance code synthesis.
- **Air-Gap Compliance**: Mathematical and architectural fail-closed guarantees preventing silent telemetry egress.

---

## 2. Canonical Model Family

All OpenCore models are released under permissive **Apache-2.0** licensing and registered in the unified `core.models.registry`:

| Model ID | Target Parameter Size | Native Context | Primary Modality & Specialization | Recommended VRAM / RAM | License |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`keelway-core:7b`** | 7.2 Billion | 65,536 tokens | General reasoning, multilingual instruction following, structured JSON | 5.8 GB (`Q4_K_M`) / 9.5 GB (`Q8_0`) | Apache-2.0 |
| **`keelway-coder:7b`** | 7.2 Billion | 65,536 tokens | Full-stack software engineering, AST inspection, test harness synthesis | 5.8 GB (`Q4_K_M`) / 9.5 GB (`Q8_0`) | Apache-2.0 |
| **`keelway-reasoning:14b`** | 14.1 Billion | 131,072 tokens | Deep chain-of-thought mathematical derivation, algorithmic verification | 11.5 GB (`Q4_K_M`) / 18.0 GB (`Q8_0`) | Apache-2.0 |
| **`keelway-nano:1.5b`** | 1.5 Billion | 32,768 tokens | Edge embedded intelligence, speculative lookahead drafting | 1.6 GB (`Q4_K_M`) / 2.8 GB (`FP16`) | Apache-2.0 |

---

## 3. Weight Management & Cryptographic Integrity

Weights are indexed via `WeightManifest` objects anchored with verified SHA-256 checksums to eliminate supply-chain tampering.

### Supported Weight Formats
- **GGUF (v3)**: Optimized for `llama.cpp` and Apple Silicon Metal unified memory.
- **SafeTensors**: Zero-copy memory mapping for high-throughput vLLM clusters.
- **AWQ / EXL2**: 4-bit activation-aware weight quantization for high-concurrency cloud GPU nodes.

### Hardware Profiler Topology Rules
The `HardwareProfiler` automatically detects host hardware and selects the quantization profile:
- **High-Memory / Multi-CUDA ($\ge 32\text{ GB}$)**: Selects `Q8_0` or `FP16` for near-lossless perplexity.
- **Apple Silicon Metal or Mid-Tier GPU ($\ge 12\text{ GB}$)**: Selects `Q4_K_M` (balanced token throughput and high reasoning fidelity).
- **Edge CPU Nodes ($\le 8\text{ GB}$)**: Selects `Q4_0` or activates `keelway-nano:1.5b`.

---

## 4. High-Performance Serving Engine

The `OpenCoreServingEngine` (`core/opencore/serving.py`) acts as the in-process and cluster orchestrator:

```mermaid
stateDiagram-v2
    [*] --> UNLOADED
    UNLOADED --> LOADING : POST /v1/opencore/models/load
    LOADING --> READY : Weights Mapped & KV Cache Allocated
    READY --> BUSY : forward_inference(request)
    BUSY --> READY : Tokens Streamed / Completed
    READY --> UNLOADED : POST /v1/opencore/models/unload
    LOADING --> ERROR : Checksum or VRAM Failure
```

### Key Capabilities
- **KV Cache Telemetry**: Live tracking of context slot utilization and hit-rate percentages.
- **Throughput Accounting**: Real-time tokens-per-second (TPS) and request counters.
- **Zero-Cost Billing**: Injects exact token counts into the Keelway Cost Ledger at \$0.00 cloud cost.

---

## 5. Sovereign Adaptation & LoRA Distillation

The adaptation pipeline (`core/opencore/adaptation.py`) enables enterprises and sovereign operators to fine-tune base weights on private corpora without leaking proprietary data:

### Domain Dataset Builder
Automated curation of training pairs across:
1. **Multilingual Localization**: Authentic conversational and idiomatic instruction pairs in:
   - **Swahili (Kiswahili)**: E.g., *"Eleza dhana ya akili bandia (AI)..."*
   - **Yoruba (Èdè Yorùbá)**: E.g., *"Ṣàlàyé ohun tí a ń pè ní ìmọ̀ ẹ̀rọ..."*
   - **Hausa**: E.g., *"Bayanin abin da ake nufi da fasahar sadarwa..."*
   - **Amharic (አማርኛ)**: E.g., *"የሰው ሰራሽ አስተውሎት ምን እንደሆነ በአጭሩ አስረዳ..."*
2. **Code AST Specialization**: Typed Python/TypeScript synthesis with formal type assertions.
3. **Mathematical Reasoning**: Explicit `<thought>` chain-of-thought derivations.

### Recipe Generators
- **Unsloth QLoRA**: Generates standalone, copy-pasteable Python scripts utilizing 4-bit base weights, gradient checkpointing, and `adamw_8bit`.
- **Hugging Face PEFT**: Generates standard JSON LoRA configurations (`r=16/32`, `lora_alpha=32/64`, target projection modules).

---

## 6. OpenCore REST API Contract

Mounted at `/v1/opencore/*`:

### 1. `GET /v1/opencore/status`
Returns host compute topology, detected accelerators, active workers, allocated VRAM, and KV cache telemetry.

### 2. `GET /v1/opencore/weights`
Enumerates all canonical weight manifests, required VRAM, verified checksums, and local disk cache status.

### 3. `POST /v1/opencore/models/load`
```json
{
  "model_id": "keelway-core:7b",
  "quantization": "q4_k_m",
  "backend": "mock"
}
```
Loads model weights into memory and returns `LoadedModelInfo`.

### 4. `POST /v1/opencore/models/unload`
```json
{
  "model_id": "keelway-core:7b"
}
```
Unloads weights and reclaims accelerator memory.

### 5. `POST /v1/opencore/adapt/recipe`
```json
{
  "base_model_id": "keelway-core:7b",
  "task": "multilingual_localization",
  "target_languages": ["swahili", "yoruba", "english"]
}
```
Generates executable Unsloth scripts, PEFT configuration, and synthetic training sample previews.

---

## 7. Verification & Engineering Quality Gate

OpenCore is integrated into the Keelway verification pipeline:
```bash
cd keelway && ./scripts/verify_engineering_gates.sh
```
All 47 tests pass in $< 1.0\text{s}$ across all 4 gate stages.
