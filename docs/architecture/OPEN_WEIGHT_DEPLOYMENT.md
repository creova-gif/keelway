# Keelway Open-Weight Model Deployment Guide

## 1. Supported Open-Weight Runtime Options

Keelway supports three primary deployment runtimes for open-weight models:

| Runtime Engine | Optimal Use Case | Supported Protocols | Minimum System Memory |
|---|---|---|---|
| **Ollama** | Local developer laptops, edge workstations, Apple Silicon | Native `/api/chat` + OpenAI `/v1/chat/completions` | 8 GB RAM (for 7B Q4_K_M) |
| **vLLM** | High-throughput multi-GPU production servers | OpenAI `/v1/chat/completions` | 24 GB VRAM (for 7B FP16 / 70B AWQ) |
| **llama.cpp** | Embedded appliances, CPU-only servers, constrained nodes | Native HTTP server + OpenAI `/v1` | 4 GB RAM (for 1.5B/3B Q4) |

---

## 2. Canonical Open-Weight Model Catalog

The initial Keelway open-weight catalog focuses on four high-utility families:

1. **Qwen 2.5 Coder 7B (`qwen2.5-coder:7b`)**
   - **Focus:** Primary local code generation, function synthesis, structured JSON extraction.
   - **Quantization:** Q4_K_M (4.7 GB disk footprint).
   - **Context Window:** 32,768 tokens.
   - **Hardware Requirement:** 8 GB unified memory (Apple M1/M2/M3/M4) or 8 GB VRAM (RTX 3060+).

2. **Qwen 2.5 Coder 1.5B (`qwen2.5-coder:1.5b`)**
   - **Focus:** Low-power edge devices, ultra-fast inline completions (<30ms).
   - **Quantization:** Q4_K_M (1.1 GB disk footprint).
   - **Context Window:** 32,768 tokens.
   - **Hardware Requirement:** 4 GB system RAM.

3. **Meta Llama 3.3 70B Instruct (`llama3.3:70b`)**
   - **Focus:** Complex local reasoning, multi-turn architecture planning, deep code analysis.
   - **Quantization:** Q4_K_M (43 GB footprint) or FP8 on GPU clusters.
   - **Context Window:** 131,072 tokens.
   - **Hardware Requirement:** 64 GB unified memory (Apple Mac Studio) or 2x 24GB VRAM.

4. **DeepSeek R1 7B (`deepseek-r1:7b`)**
   - **Focus:** Chain-of-thought mathematical and algorithmic verification.
   - **Quantization:** Q4_K_M (4.7 GB footprint).
   - **Context Window:** 65,536 tokens.

---

## 3. Step-by-Step Local Deployment Workflow

### Step 1: Install and Launch Ollama
```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve
```

### Step 2: Pull Permitted Model Weights
```bash
# Pull primary coding model
ollama pull qwen2.5-coder:7b

# (Optional) Pull reasoning model
ollama pull deepseek-r1:7b
```

### Step 3: Configure Keelway Environment
Set the following environment variables in `.env` or your shell:
```bash
KEELWAY_LOCAL_MODEL_URL=http://localhost:11434
KEELWAY_DEFAULT_MODEL=qwen2.5-coder:7b
KEELWAY_LOCAL_API=ollama
```

### Step 4: Verify Deployment Health
```bash
curl http://localhost:8000/v1/models
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen2.5-coder:7b", "messages": [{"role": "user", "content": "hello"}]}'
```

---

## 4. Hardware Sizing Matrix for Enterprise Deployments

| Scale Tier | Target Inferences/Day | Recommended Hardware | Models Hosted | Est. Monthly Power / Infra Cost |
|---|---|---|---|---|
| **Tier 1 (Developer Edge)** | 100 - 1,000 | Apple Mac Mini M4 (24GB Unified) | Qwen 2.5 Coder 7B | ~$15 / month (Electricity) |
| **Tier 2 (Engineering Team)** | 1,000 - 20,000 | 1x NVIDIA RTX 4090 (24GB) or Mac Studio M2 Max | Qwen 2.5 Coder 7B + DeepSeek R1 7B | ~$80 / month |
| **Tier 3 (Enterprise On-Prem)** | 50,000+ | 2x NVIDIA A100/H100 (80GB) with vLLM | Llama 3.3 70B + Qwen 7B | ~$800 - $1,500 / month |
