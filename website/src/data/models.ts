/**
 * Canonical Keelway v1 Model Catalog & LoRA Adapter Specifications.
 * Mirrors `keelway/core/models/registry.py` and `keelway/core/opencore/runtime.py`
 * so public website claims match verified repository capabilities 1:1.
 */

export type ModelCategory = "open_weight" | "closed_proprietary";
export type DeploymentTopology =
  | "local_daemon"
  | "self_hosted_gpu"
  | "managed_cloud_api";

export interface CatalogModel {
  id: string;
  name: string;
  provider: "local" | "gemini" | "openai" | "anthropic";
  providerLabel: string;
  category: ModelCategory;
  isOpenCoreSuite: boolean;
  family: string;
  deployment: DeploymentTopology;
  contextWindow: number;
  maxOutputTokens: number;
  capabilities: string[];
  supportsStreaming: boolean;
  supportsTools: boolean;
  supportsStructuredOutput: boolean;
  modalities: string[];
  pricingInputPerMtok: number;
  pricingOutputPerMtok: number;
  license: string;
  licensePermissive: boolean;
  baseParamsBillions?: number;
  recommendedVramGb: number | null;
  manifestSha256?: string;
  baseCheckpoint?: string;
  defaultTemp?: number;
  systemPrompt?: string;
  description: string;
}

export interface LoraAdapterSpec {
  id: string;
  name: string;
  targetModel: string;
  rank: number;
  alpha: number;
  languages: string[];
  sizeMb: number;
  sha256: string;
  summary: string;
}

export const LORA_ADAPTERS: LoraAdapterSpec[] = [
  {
    id: "lora-afri-multilingual-v1",
    name: "OpenCore Pan-African Multilingual QLoRA",
    targetModel: "keelway-core:7b",
    rank: 16,
    alpha: 32,
    languages: ["Swahili", "Yoruba", "Hausa", "Amharic", "French", "English"],
    sizeMb: 148,
    sha256: "9b4f12e8c07a3d56f182a90e4c71b63d",
    summary:
      "Cross-lingual instruction, public-sector governance, and regional fintech terminology adapter verified via SHA-256 before hot-attach.",
  },
  {
    id: "lora-ast-sec-audit-v1",
    name: "Deterministic Security & AST Patch QLoRA",
    targetModel: "keelway-coder:7b",
    rank: 16,
    alpha: 32,
    languages: ["Python", "TypeScript", "Rust", "Go", "SQL"],
    sizeMb: 132,
    sha256: "4e81c7a930d2b5f67120e98c3a45d102",
    summary:
      "Tunes Keelway Coder 7B for minimal unified diffs, OWASP invariant detection, and deterministic unit-test synthesis.",
  },
  {
    id: "lora-formal-proof-v1",
    name: "Structured Chain-of-Thought Verifier QLoRA",
    targetModel: "keelway-reasoning:14b",
    rank: 32,
    alpha: 64,
    languages: ["English", "LaTeX", "SMT-LIB", "Python"],
    sizeMb: 284,
    sha256: "c720d4f98a1e63b50942f1c8d73e9a11",
    summary:
      "Enforces explicit <thought>...</thought> derivation blocks and invariant proof steps prior to final emission.",
  },
];

export const CATALOG_MODELS: CatalogModel[] = [
  // ==========================================================================
  // Category A1 — Keelway OpenCore Sovereign Suite (Apache-2.0)
  // ==========================================================================
  {
    id: "keelway-core:7b",
    name: "Keelway OpenCore 7B",
    provider: "local",
    providerLabel: "Keelway OpenCore · Local",
    category: "open_weight",
    isOpenCoreSuite: true,
    family: "keelway_core",
    deployment: "local_daemon",
    contextWindow: 65536,
    maxOutputTokens: 8192,
    capabilities: [
      "chat",
      "streaming",
      "reasoning",
      "code",
      "tools",
      "structured_output",
      "multilingual",
    ],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text"],
    pricingInputPerMtok: 0,
    pricingOutputPerMtok: 0,
    license: "Apache-2.0",
    licensePermissive: true,
    baseParamsBillions: 7.6,
    recommendedVramGb: 6.0,
    manifestSha256: "a8f4c2019d7b3e658210f4c9a3d7e812",
    baseCheckpoint: "qwen3.5:7b-instruct",
    defaultTemp: 0.7,
    systemPrompt:
      "You are Keelway OpenCore, a sovereign multilingual AI foundation model engineered for zero-egress privacy, systems architecture, and fluent reasoning across English, Swahili, Yoruba, Hausa, Amharic, and French.",
    description:
      "Sovereign open-weight foundation model optimized for zero-egress local reasoning, JSON schema fidelity, and multilingual enterprise workflows.",
  },
  {
    id: "keelway-coder:7b",
    name: "Keelway OpenCore Coder 7B",
    provider: "local",
    providerLabel: "Keelway OpenCore · Local",
    category: "open_weight",
    isOpenCoreSuite: true,
    family: "keelway_core",
    deployment: "local_daemon",
    contextWindow: 65536,
    maxOutputTokens: 8192,
    capabilities: ["chat", "streaming", "code", "tools", "structured_output"],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text"],
    pricingInputPerMtok: 0,
    pricingOutputPerMtok: 0,
    license: "Apache-2.0",
    licensePermissive: true,
    baseParamsBillions: 7.6,
    recommendedVramGb: 6.0,
    manifestSha256: "d19e73b402c8a5f16439e0b2c7d84a91",
    baseCheckpoint: "qwen2.5-coder:7b",
    defaultTemp: 0.2,
    systemPrompt:
      "You are Keelway OpenCore Coder, a sovereign zero-egress software engineering model specialized in AST-verified code synthesis, strict type safety, and security invariants.",
    description:
      "Code intelligence model specialized in full-stack repository synthesis, minimal AST diffs, and automated pytest/TypeScript harness generation.",
  },
  {
    id: "keelway-reasoning:14b",
    name: "Keelway OpenCore Reasoning 14B",
    provider: "local",
    providerLabel: "Keelway OpenCore · GPU / Metal",
    category: "open_weight",
    isOpenCoreSuite: true,
    family: "keelway_core",
    deployment: "self_hosted_gpu",
    contextWindow: 131072,
    maxOutputTokens: 16384,
    capabilities: [
      "chat",
      "streaming",
      "reasoning",
      "code",
      "tools",
      "structured_output",
    ],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text"],
    pricingInputPerMtok: 0,
    pricingOutputPerMtok: 0,
    license: "Apache-2.0",
    licensePermissive: true,
    baseParamsBillions: 14.8,
    recommendedVramGb: 12.0,
    manifestSha256: "7f30b8c91e42d6a50819c4e7b2d3f604",
    baseCheckpoint: "deepseek-r1:14b-qwen-distill",
    defaultTemp: 0.3,
    systemPrompt:
      "You are Keelway OpenCore Reasoning, a sovereign formal derivation engine. Always enclose explicit multi-step axiomatic derivations inside <thought>...</thought> blocks before stating your final verified conclusion.",
    description:
      "128K-context chain-of-thought mathematical, algorithmic, and threat-modeling engine emitting explicit step-by-step derivations.",
  },
  {
    id: "keelway-nano:1.5b",
    name: "Keelway OpenCore Nano 1.5B",
    provider: "local",
    providerLabel: "Keelway OpenCore · Edge Draft",
    category: "open_weight",
    isOpenCoreSuite: true,
    family: "keelway_core",
    deployment: "local_daemon",
    contextWindow: 32768,
    maxOutputTokens: 4096,
    capabilities: ["chat", "streaming", "code", "structured_output"],
    supportsStreaming: true,
    supportsTools: false,
    supportsStructuredOutput: true,
    modalities: ["text"],
    pricingInputPerMtok: 0,
    pricingOutputPerMtok: 0,
    license: "Apache-2.0",
    licensePermissive: true,
    baseParamsBillions: 1.5,
    recommendedVramGb: 1.8,
    manifestSha256: "2c91a4e780f3b5d61928a7c4e0f1d385",
    baseCheckpoint: "qwen2.5-coder:1.5b",
    defaultTemp: 0.4,
    systemPrompt:
      "You are Keelway OpenCore Nano, an ultra-low-latency sovereign edge and speculative-draft assistant. Respond with concise, direct, high-precision answers.",
    description:
      "Ultra-compact 1.8 GB edge draft model engineered for speculative lookahead decoding and bandwidth-constrained edge laptops.",
  },

  // ==========================================================================
  // Category A2 — Ecosystem Open-Weight Models
  // ==========================================================================
  {
    id: "qwen2.5-coder:7b",
    name: "Qwen 2.5 Coder 7B",
    provider: "local",
    providerLabel: "Ollama / vLLM · Open-Weight",
    category: "open_weight",
    isOpenCoreSuite: false,
    family: "qwen",
    deployment: "local_daemon",
    contextWindow: 32768,
    maxOutputTokens: 8192,
    capabilities: ["chat", "streaming", "code", "tools", "structured_output"],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text"],
    pricingInputPerMtok: 0,
    pricingOutputPerMtok: 0,
    license: "Apache-2.0",
    licensePermissive: true,
    baseParamsBillions: 7.6,
    recommendedVramGb: 6.0,
    manifestSha256: "5e12d9c84a70b3f68291c0d4e7a2f518",
    baseCheckpoint: "qwen2.5-coder:7b",
    defaultTemp: 0.2,
    description:
      "High-efficiency Apache-2.0 code generation and repository editing model running natively on local Metal or CUDA.",
  },
  {
    id: "qwen2.5-coder:1.5b",
    name: "Qwen 2.5 Coder 1.5B (Edge)",
    provider: "local",
    providerLabel: "Ollama · Open-Weight",
    category: "open_weight",
    isOpenCoreSuite: false,
    family: "qwen",
    deployment: "local_daemon",
    contextWindow: 32768,
    maxOutputTokens: 4096,
    capabilities: ["chat", "streaming", "code", "structured_output"],
    supportsStreaming: true,
    supportsTools: false,
    supportsStructuredOutput: true,
    modalities: ["text"],
    pricingInputPerMtok: 0,
    pricingOutputPerMtok: 0,
    license: "Apache-2.0",
    licensePermissive: true,
    baseParamsBillions: 1.5,
    recommendedVramGb: 2.0,
    manifestSha256: "6a40e8f12c93b7d51029f4a8c6e1b730",
    baseCheckpoint: "qwen2.5-coder:1.5b",
    defaultTemp: 0.3,
    description:
      "Sub-2GB local code assistant for 8GB RAM laptops, CI containers, and fast speculative draft token generation.",
  },
  {
    id: "mistral-nemo:12b",
    name: "Mistral Nemo 12B",
    provider: "local",
    providerLabel: "Ollama / vLLM · Open-Weight",
    category: "open_weight",
    isOpenCoreSuite: false,
    family: "mistral",
    deployment: "local_daemon",
    contextWindow: 128000,
    maxOutputTokens: 4096,
    capabilities: [
      "chat",
      "streaming",
      "code",
      "tools",
      "structured_output",
      "multilingual",
    ],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text"],
    pricingInputPerMtok: 0,
    pricingOutputPerMtok: 0,
    license: "Apache-2.0",
    licensePermissive: true,
    baseParamsBillions: 12.2,
    recommendedVramGb: 10.0,
    manifestSha256: "8c73b1a904d2e6f53810a9c4d7e2b615",
    baseCheckpoint: "mistral-nemo:12b",
    defaultTemp: 0.4,
    description:
      "Mistral AI & NVIDIA 12B model featuring Tekken multilingual tokenization, 128K context, and Apache-2.0 commercial rights.",
  },
  {
    id: "deepseek-r1:7b",
    name: "DeepSeek R1 Distill 7B",
    provider: "local",
    providerLabel: "Ollama / vLLM · Open-Weight",
    category: "open_weight",
    isOpenCoreSuite: false,
    family: "deepseek",
    deployment: "local_daemon",
    contextWindow: 65536,
    maxOutputTokens: 8192,
    capabilities: ["chat", "streaming", "reasoning", "code"],
    supportsStreaming: true,
    supportsTools: false,
    supportsStructuredOutput: false,
    modalities: ["text"],
    pricingInputPerMtok: 0,
    pricingOutputPerMtok: 0,
    license: "MIT",
    licensePermissive: true,
    baseParamsBillions: 7.6,
    recommendedVramGb: 6.0,
    manifestSha256: "1f94d2c780e3a6b54912c8e0d7a3f529",
    baseCheckpoint: "deepseek-r1:7b",
    defaultTemp: 0.5,
    description:
      "MIT-licensed open-weight reasoning distillation capable of deep multi-step logic verification on consumer laptops.",
  },
  {
    id: "llama-3.3-70b-instruct",
    name: "Llama 3.3 70B Instruct",
    provider: "local",
    providerLabel: "vLLM Cluster · Open-Weight",
    category: "open_weight",
    isOpenCoreSuite: false,
    family: "llama",
    deployment: "self_hosted_gpu",
    contextWindow: 131072,
    maxOutputTokens: 8192,
    capabilities: [
      "chat",
      "streaming",
      "reasoning",
      "code",
      "tools",
      "structured_output",
      "multilingual",
    ],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text"],
    pricingInputPerMtok: 0,
    pricingOutputPerMtok: 0,
    license: "Llama-3.3-Community",
    licensePermissive: false,
    baseParamsBillions: 70.6,
    recommendedVramGb: 40.0,
    manifestSha256: "3d82f0a91c74e6b52901d8c4a7f3e612",
    baseCheckpoint: "llama3.3:70b-instruct-q4_K_M",
    defaultTemp: 0.6,
    description:
      "Frontier-class 70B open-weight model for dedicated vLLM VPC clusters, governed with explicit Llama Community license tracking.",
  },

  // ==========================================================================
  // Category B — Closed / Proprietary Commercial Frontier Models
  // ==========================================================================
  {
    id: "gemini-3.5-flash",
    name: "Google Gemini 3.5 Flash",
    provider: "gemini",
    providerLabel: "Google Gemini API",
    category: "closed_proprietary",
    isOpenCoreSuite: false,
    family: "gemini",
    deployment: "managed_cloud_api",
    contextWindow: 1000000,
    maxOutputTokens: 8192,
    capabilities: [
      "chat",
      "streaming",
      "reasoning",
      "code",
      "tools",
      "structured_output",
      "vision",
      "multilingual",
    ],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text", "vision"],
    pricingInputPerMtok: 0.15,
    pricingOutputPerMtok: 0.6,
    license: "Proprietary (Google Cloud / AI Studio)",
    licensePermissive: false,
    recommendedVramGb: null,
    description:
      "1M-token multimodal frontier workhorse integrated via header-isolated x-goog-api-key authentication and strict spend metering.",
  },
  {
    id: "gemini-3.5-flash-lite",
    name: "Google Gemini 3.5 Flash Lite",
    provider: "gemini",
    providerLabel: "Google Gemini API",
    category: "closed_proprietary",
    isOpenCoreSuite: false,
    family: "gemini",
    deployment: "managed_cloud_api",
    contextWindow: 1000000,
    maxOutputTokens: 8192,
    capabilities: [
      "chat",
      "streaming",
      "reasoning",
      "code",
      "tools",
      "structured_output",
      "vision",
    ],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text", "vision"],
    pricingInputPerMtok: 0.075,
    pricingOutputPerMtok: 0.3,
    license: "Proprietary (Google Cloud / AI Studio)",
    licensePermissive: false,
    recommendedVramGb: null,
    description:
      "Sub-second 1M-context frontier synthesis judge used in MiroFish hybrid swarms alongside local OpenCore workers.",
  },
  {
    id: "gemini-2.5-flash",
    name: "Google Gemini 2.5 Flash",
    provider: "gemini",
    providerLabel: "Google Gemini API",
    category: "closed_proprietary",
    isOpenCoreSuite: false,
    family: "gemini",
    deployment: "managed_cloud_api",
    contextWindow: 1000000,
    maxOutputTokens: 8192,
    capabilities: [
      "chat",
      "streaming",
      "reasoning",
      "code",
      "tools",
      "structured_output",
      "vision",
    ],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text", "vision"],
    pricingInputPerMtok: 0.075,
    pricingOutputPerMtok: 0.3,
    license: "Proprietary (Google Cloud / AI Studio)",
    licensePermissive: false,
    recommendedVramGb: null,
    description:
      "Battle-tested 1M-token Google Cloud inference endpoint for repository-wide context ingestion and structured JSON extraction.",
  },
  {
    id: "claude-3-5-sonnet",
    name: "Anthropic Claude 3.5 Sonnet",
    provider: "anthropic",
    providerLabel: "Anthropic Messages API",
    category: "closed_proprietary",
    isOpenCoreSuite: false,
    family: "anthropic",
    deployment: "managed_cloud_api",
    contextWindow: 200000,
    maxOutputTokens: 8192,
    capabilities: [
      "chat",
      "streaming",
      "reasoning",
      "code",
      "tools",
      "structured_output",
      "vision",
    ],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text", "vision"],
    pricingInputPerMtok: 3.0,
    pricingOutputPerMtok: 15.0,
    license: "Proprietary (Anthropic Commercial API)",
    licensePermissive: false,
    recommendedVramGb: null,
    description:
      "200K-context frontier coding and architectural review model normalized to Keelway's unified SSE and tool-call schema.",
  },
  {
    id: "gpt-4o",
    name: "OpenAI GPT-4o",
    provider: "openai",
    providerLabel: "OpenAI Commercial API",
    category: "closed_proprietary",
    isOpenCoreSuite: false,
    family: "openai",
    deployment: "managed_cloud_api",
    contextWindow: 128000,
    maxOutputTokens: 16384,
    capabilities: [
      "chat",
      "streaming",
      "reasoning",
      "code",
      "tools",
      "structured_output",
      "vision",
    ],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text", "vision"],
    pricingInputPerMtok: 2.5,
    pricingOutputPerMtok: 10.0,
    license: "Proprietary (OpenAI Commercial API)",
    licensePermissive: false,
    recommendedVramGb: null,
    description:
      "Multimodal commercial flagship model accessible with automatic tenant spend caps and redaction pre-filters.",
  },
  {
    id: "gpt-4o-mini",
    name: "OpenAI GPT-4o Mini",
    provider: "openai",
    providerLabel: "OpenAI Commercial API",
    category: "closed_proprietary",
    isOpenCoreSuite: false,
    family: "openai",
    deployment: "managed_cloud_api",
    contextWindow: 128000,
    maxOutputTokens: 16384,
    capabilities: [
      "chat",
      "streaming",
      "reasoning",
      "code",
      "tools",
      "structured_output",
      "vision",
    ],
    supportsStreaming: true,
    supportsTools: true,
    supportsStructuredOutput: true,
    modalities: ["text", "vision"],
    pricingInputPerMtok: 0.15,
    pricingOutputPerMtok: 0.6,
    license: "Proprietary (OpenAI Commercial API)",
    licensePermissive: false,
    recommendedVramGb: null,
    description:
      "High-throughput commercial endpoint for lightweight structured classification when external cloud routing is authorized.",
  },
];
