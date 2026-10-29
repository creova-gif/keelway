# Kora Labs — 2026–2031 Research Program

## Research mission (proposed)
Produce reproducible evidence and original engineering knowledge about reliable, affordable, secure and portable AI under infrastructure constraints. Transfer validated work into Kora products through RFCs, ADRs, tested code and documented IP ownership.

## Research tracks
| Track | Hypothesis | First experiment | Product transfer |
|---|---|---|---|
| Agent reliability | bounded agents with verification outperform unrestricted autonomy on high-risk tasks | coding/operations benchmark with approval and replay | Kora AI Core / Dev |
| Inference economics | routing/caching/small models reduce cost per successful task | compare hosted models under identical tasks | model gateway |
| Retrieval and memory | hybrid retrieval with provenance reduces unsupported claims | time-sensitive repo Q&A dataset | personal agent |
| Edge/offline AI | selected local models remain useful under low-connectivity constraints | CPU/RAM/network impairment matrix | Kora Edge / Sync |
| AI security | tool-level policy blocks attacks that prompt-only defenses miss | malicious README / prompt-injection fixtures | policy gateway |
| African language/domain AI | targeted evaluation reveals under-served tasks | curated consented multilingual task suite | domain adapters |
| Interoperability | stable typed contracts reduce integration churn | adapter compatibility suite | SDKs / Connect |

## Five-year horizon
**2026–2027:** establish eval harness, model gateway, agent security, hybrid retrieval, initial edge baselines. **Confidence: high** in demand for these capabilities, uncertain in vendor leadership.

**2028–2029:** investigate adaptive model routing, durable multi-agent workflows, specialized small models, multimodal edge and enterprise assurance. **Confidence: medium** in adoption speed.

**2030+:** explore distributed intelligence, specialized training, advanced verification and regional infrastructure coordination. **Confidence: low–medium** in specific architectures.

## Experiment contract
Each experiment must have ID, owner, hypothesis, baseline, dataset provenance/license, environment, hardware, model/version, prompt/config, evaluation protocol, seeds where possible, metric definitions, raw results, limitations, cost, review and reproducibility instructions.

## Evidence quality gates
No '10x cheaper', 'first in Africa', 'production-ready', or compliance claims without independently reviewable evidence. Separate internal results from external benchmarks; do not treat synthetic data as real-world demand.

## Labs-to-product handoff
Research question → literature/evidence → hypothesis → experiment → reproducible result → peer review → RFC → ADR → implementation ticket → tests → deployment evaluation → publication/IP decision.

## Suggested metrics
Task success and hidden tests, policy violations, factual citation precision, cost per successful task, p50/p95 latency, RAM/CPU/power, offline completion rate, provider error recovery, cross-lingual accuracy and data licensing coverage.

## Intellectual property and publication
Classify each output as third-party, contributed under license, Kora-owned, jointly owned or uncertain. Record author/contributor provenance before publication or open sourcing. Legal review required for claims and licensing.
