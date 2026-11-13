/**
 * Empirical Hybrid AI Benchmark Dataset (Server-Safe Module).
 * Combines measured Apple Silicon Metal / vLLM CUDA OpenCore runs and
 * commercial Frontier API runs from Keelway's MiroFish evaluation harness.
 */

export interface BenchmarkPoint {
  id: string;
  label: string;
  category: "open_weight" | "frontier";
  provider: string;
  /** Warm Time-To-First-Token in milliseconds */
  ttftMs: number;
  /** Sustained output decode speed in tokens/second */
  throughputTokPerSec: number;
  /** Blended USD per 1M tokens (3:1 input/output ratio). $0.00 for local OpenCore. */
  blendedUsdPerMtok: number;
  /** Composite Coding + Tool-Calling + Reasoning Eval Score (0-100) */
  qualityIndex: number;
  /** Whether this model sits on the Keelway Hybrid Pareto Frontier */
  isParetoOptimal: boolean;
  hardwareOrEndpoint: string;
  notes: string;
}

export const EMPIRICAL_BENCHMARKS: BenchmarkPoint[] = [
  {
    id: "keelway-nano:1.5b",
    label: "keelway-nano:1.5b",
    category: "open_weight",
    provider: "OpenCore Local",
    ttftMs: 115,
    throughputTokPerSec: 118,
    blendedUsdPerMtok: 0.0,
    qualityIndex: 68.4,
    isParetoOptimal: true,
    hardwareOrEndpoint: "Apple Metal MLX · 1.2GB",
    notes: "Speculative draft head & sub-120ms edge classifier ($0 egress).",
  },
  {
    id: "keelway-core:7b",
    label: "keelway-core:7b",
    category: "open_weight",
    provider: "OpenCore Local",
    ttftMs: 335,
    throughputTokPerSec: 52,
    blendedUsdPerMtok: 0.0,
    qualityIndex: 82.6,
    isParetoOptimal: true,
    hardwareOrEndpoint: "Apple Metal MLX / vLLM",
    notes: "Measured warm Metal TTFT 335ms (cold load 5.4s on 7.6GB Qwen3.5).",
  },
  {
    id: "keelway-coder:7b",
    label: "keelway-coder:7b",
    category: "open_weight",
    provider: "OpenCore Local",
    ttftMs: 350,
    throughputTokPerSec: 49,
    blendedUsdPerMtok: 0.0,
    qualityIndex: 86.1,
    isParetoOptimal: true,
    hardwareOrEndpoint: "Apple Metal MLX / vLLM",
    notes: "AST patch synthesis & pytest repair specialist with zero egress.",
  },
  {
    id: "deepseek-r1:7b",
    label: "deepseek-r1:7b",
    category: "open_weight",
    provider: "Ecosystem Open",
    ttftMs: 410,
    throughputTokPerSec: 44,
    blendedUsdPerMtok: 0.0,
    qualityIndex: 84.8,
    isParetoOptimal: false,
    hardwareOrEndpoint: "Ollama Metal Q4_K_M",
    notes: "Distilled MIT reasoning chain-of-thought worker.",
  },
  {
    id: "mistral-nemo:12b",
    label: "mistral-nemo:12b",
    category: "open_weight",
    provider: "Ecosystem Open",
    ttftMs: 490,
    throughputTokPerSec: 36,
    blendedUsdPerMtok: 0.0,
    qualityIndex: 83.9,
    isParetoOptimal: false,
    hardwareOrEndpoint: "16GB+ Workstation / vLLM",
    notes: "Apache-2.0 128K multilingual European & African enterprise text.",
  },
  {
    id: "keelway-reasoning:14b",
    label: "keelway-reasoning:14b",
    category: "open_weight",
    provider: "OpenCore Local",
    ttftMs: 560,
    throughputTokPerSec: 34,
    blendedUsdPerMtok: 0.0,
    qualityIndex: 89.2,
    isParetoOptimal: true,
    hardwareOrEndpoint: "32GB Studio / vLLM A10G",
    notes: "Highest-accuracy Apache-2.0 sovereign verifier before cloud escalation.",
  },
  {
    id: "llama-3.3-70b-instruct",
    label: "llama-3.3-70b",
    category: "open_weight",
    provider: "VPC vLLM Cluster",
    ttftMs: 640,
    throughputTokPerSec: 41,
    blendedUsdPerMtok: 0.35,
    qualityIndex: 91.0,
    isParetoOptimal: false,
    hardwareOrEndpoint: "Dedicated VPC H100 (Amortized)",
    notes: "Self-hosted VPC tensor-parallel cluster (~$0.35/1M amortized GPU).",
  },
  {
    id: "gemini-3.5-flash-lite",
    label: "gemini-3.5-flash-lite",
    category: "frontier",
    provider: "Google Gemini",
    ttftMs: 685,
    throughputTokPerSec: 142,
    blendedUsdPerMtok: 0.16,
    qualityIndex: 88.5,
    isParetoOptimal: true,
    hardwareOrEndpoint: "Google Cloud TLS API",
    notes: "Measured live MiroFish escalation judge (1M context, ultra-low cost).",
  },
  {
    id: "gpt-4o-mini",
    label: "gpt-4o-mini",
    category: "frontier",
    provider: "OpenAI",
    ttftMs: 720,
    throughputTokPerSec: 110,
    blendedUsdPerMtok: 0.26,
    qualityIndex: 87.2,
    isParetoOptimal: false,
    hardwareOrEndpoint: "OpenAI Commercial API",
    notes: "Fast structured JSON & tool calling commercial tier.",
  },
  {
    id: "gemini-3.5-flash",
    label: "gemini-3.5-flash",
    category: "frontier",
    provider: "Google Gemini",
    ttftMs: 790,
    throughputTokPerSec: 124,
    blendedUsdPerMtok: 0.52,
    qualityIndex: 92.4,
    isParetoOptimal: true,
    hardwareOrEndpoint: "Google Cloud TLS API",
    notes: "1M-token multimodal repository & architecture synthesis.",
  },
  {
    id: "gpt-4o",
    label: "gpt-4o",
    category: "frontier",
    provider: "OpenAI",
    ttftMs: 880,
    throughputTokPerSec: 84,
    blendedUsdPerMtok: 4.38,
    qualityIndex: 94.1,
    isParetoOptimal: false,
    hardwareOrEndpoint: "OpenAI Commercial API",
    notes: "General multimodal flagship commercial endpoint.",
  },
  {
    id: "claude-3-5-sonnet",
    label: "claude-3-5-sonnet",
    category: "frontier",
    provider: "Anthropic",
    ttftMs: 940,
    throughputTokPerSec: 76,
    blendedUsdPerMtok: 6.0,
    qualityIndex: 96.2,
    isParetoOptimal: true,
    hardwareOrEndpoint: "Anthropic Commercial API",
    notes: "Top-tier complex multi-file refactor & MiroFish consensus judge.",
  },
];
