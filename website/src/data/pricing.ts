export interface FaqItem {
  q: string;
  a: string;
}

export const PRICING_FAQS: FaqItem[] = [
  {
    q: "Does Keelway mark up commercial OpenAI, Gemini, or Anthropic token prices?",
    a: "No. Team Hybrid and Enterprise Sovereign VPC tiers use Bring-Your-Own-Key (BYOK) with 0% token markup. You pay upstream commercial providers directly at their published rate cards, while OpenCore local inference runs at $0.00 marginal token cost on your own hardware.",
  },
  {
    q: "Can I use Keelway 100% offline or in an air-gapped facility?",
    a: "Yes. The OpenCore Open Source tier and Enterprise Sovereign VPC runner operate completely offline over loopback (127.0.0.1) or private VPC subnets. Variable fonts, studio assets, SQLite hash-chained audit logs, and Ollama/vLLM model weights require zero internet connectivity.",
  },
  {
    q: "Are all models in the catalog covered by the same open-source license?",
    a: "No — and Keelway tracks every license explicitly in the Layer 4 Model Registry. Keelway's OpenCore suite, Qwen 2.5 Coder, and Mistral Nemo use Apache-2.0; DeepSeek R1 Distill uses MIT; Llama 3.3 uses the Meta Llama Community License; and Gemini, OpenAI, and Anthropic are commercial APIs.",
  },
  {
    q: "What happens when an engineering team hits its monthly cloud spend cap?",
    a: "Your TenantPolicy controls the exact behavior: either seamlessly downgrade overflow requests to local keelway-core:7b ($0.00) with zero application downtime, or fail-closed with a typed HTTP 402 BudgetExceededError.",
  },
  {
    q: "How does Enterprise Sovereign VPC support Africa and regulated global regions?",
    a: "We deploy dedicated vLLM/Ollama GPU runners directly inside your regional cloud VPC or on-premises data center (Lagos, Nairobi, Johannesburg, Frankfurt, or US-Gov/Enterprise) paired with SHA-256 verified multilingual QLoRA adapters for Swahili, Yoruba, Hausa, Amharic, and French.",
  },
];
