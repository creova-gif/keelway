# First LoRA Experiment Plan (Week 1–2 of research track)

## Objective
Fine-tune a 7B open model on 20–30 Kora engineering-brief examples and measure whether it beats the base model (and approaches Claude) on the same evaluation task.

## Steps

1. **Prepare data**
   - Generate 25 examples with Claude using the Workflow 1 prompt.
   - Human-review and correct them.
   - Save as `research/datasets/seed/engineering-brief/v1.jsonl`.

2. **Base model**
   - Qwen2.5-7B-Instruct (or Llama-3.1-8B-Instruct).
   - Download once; cache locally.

3. **Fine-tune (LoRA)**
   - Tool: Unsloth or Axolotl.
   - Rank: 16 or 32.
   - Epochs: 1–3 (watch for overfitting on small data).
   - Hardware: single 24 GB GPU or cloud equivalent.

4. **Evaluate**
   - Run EVAL-COMPARE-001 (or a dedicated engineering-brief eval) on:
     - Base Qwen2.5-7B
     - LoRA fine-tune
     - Claude
   - Record correctness, citation quality, latency.

5. **Decision**
   - If fine-tune ≥ base and within acceptable gap of Claude → continue expanding the dataset.
   - If no gain → stop, improve data quality, or try a different base model.

## Output
- Checkpoint path
- Comparison table
- Short note in `research/experiments/lora-eng-brief-v1.md`
