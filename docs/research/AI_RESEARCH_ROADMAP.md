# Keelway — AI Research & Adaptation Roadmap

> **Status**: Approved Parallel Track  
> **Governance Constraint**: Research tracks must not block production infrastructure milestones. No foundation pre-training from scratch without explicit executive scope and budget authorization.

---

## 1. Strategic Research Thesis: Small, Sovereign, Domain-Adapted Models

Rather than burning millions on general-purpose frontier pre-training, Keelway's research strategy focuses on **high-efficiency domain adaptation** of top-performing open-weight foundations (Qwen 2.5, Llama 3.3, DeepSeek R1).

Our research goals:
1. **Domain-Specific Adaptation**: Fine-tune 7B–14B models on verified Keelway engineering traces, architecture briefs, and code reviews so they match or exceed frontier model performance on Keelway-native tasks.
2. **Multilingual Technical Capabilities**: Native support for African and global languages (Swahili, French, Arabic, English) in technical software engineering contexts.
3. **Low-Latency Speculative Inference**: Pair small draft models (1.5B–3B) with larger local models (7B–32B) to double inference throughput on commodity hardware.
4. **Sovereign Privacy Training**: Training pipelines that operate purely on synthetic, sanitized, or explicitly consented developer flight tapes with complete PII and credential stripping.

---

## 2. Research Phases & Milestones

```
[ Phase A: Data & Evaluation Harness ] (Days 1–45)
  ├── 5 Seed Task Families: Eng briefs, PR review, ADR synthesis, test triage, African-language Q&A
  ├── Strict dataset governance in `research/datasets/` (zero private user data)
  └── Standardized benchmark harness (EVAL-COMPARE-001)

[ Phase B: Supervised LoRA / QLoRA Adaptation ] (Days 30–90)
  ├── Base: Qwen2.5-Coder-7B-Instruct & Llama-3.1-8B-Instruct
  ├── Training: Unsloth / Axolotl on single 24GB–48GB GPU (Rank 16/32)
  ├── Evaluation Metric: Task accuracy, citation accuracy, P95 latency vs Claude 3.5 baseline
  └── Decision Gate: Must achieve >= base model accuracy and close 60%+ gap to frontier model

[ Phase C: Speculative Edge Inference & Deployment ] (Day 90+)
  ├── Quantization (4-bit AWQ / GGUF) for Apple Silicon and edge workstations
  ├── Speculative draft decoding verification
  └── KHub air-gapped model bundle packaging
```

---

## 3. Evaluation Benchmark Suite (`evaluations/`)

All adapted models must be systematically evaluated against canonical baselines:
- `evals/eval_compare.py`: Automated multi-model scoring across correctness, reasoning depth, latency, and token efficiency.
- Model checkpoints are tagged in the Model Registry (`core/models/registry.py`) under `ModelFamily.KEELWAY_ADAPTED` and `ModelCategory.OPEN_WEIGHT`.
