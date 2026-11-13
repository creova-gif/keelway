# Keelway Company Website & Interactive API Reference

Built with **Next.js 15 (App Router)**, **React 19**, **TypeScript**, **Tailwind CSS**, **Radix UI**, **Framer Motion**, and **Vercel Analytics**, implementing the canonical interface specification in [`../DESIGN.md`](../DESIGN.md).

## Routes

| Route | Purpose |
|---|---|
| `/` | Dual-track conversion hub with live WebCrypto Approval Gate, 6-Layer Topology Circuit, 5-step Flight-Recorder, Quickstart Terminal, and Early Access intake |
| `/models` | 15-model OpenCore + Frontier catalog, live Hardware/VRAM Fit Calculator, QLoRA registry, and interactive Ollama Modelfile compiler |
| `/governance` | Interactive 4D Routing Provenance & Monthly USD Cost Savings Simulator + Pre-Egress Secret Redaction & Scoped Key Vault lab |
| `/pricing` | 3-tier deployment matrix (`$0` Apache-2.0 Local, `0%`-markup Team Hybrid, Enterprise Sovereign VPC), seat calculator, and Radix FAQ |
| `/brand` | Official geometric `'K'` mark, click-to-copy dark/light tokens, self-hosted variable font specimens, and usage guardrails |
| `/docs` | 5-minute quickstart, 4 operational surfaces, OpenCore weight workflow, runnable SDK snippets, and honest v1 vs. roadmap matrix |
| `/api-reference` | Server-parsed OpenAPI 3.1 workbench + searchable 183-endpoint directory with 4-language live code tabs |
| `/api/early-access` | Serverless intake filing structured GitHub issues when `EARLY_ACCESS_GH_TOKEN` is configured |

Legacy static paths (`/index.html`, `/docs.html`, `/api.html`, `/brand.html`) permanently `308`-redirect to their App Router counterparts via [`next.config.ts`](./next.config.ts).

## Commands

```bash
cd keelway/website
npm install
npm run dev        # Turbopack local server on http://localhost:3000
npm run typecheck  # Strict TypeScript verification
npm run build      # Production static + serverless build
```

To refresh the OpenAPI 3.1 specification from FastAPI:

```bash
cd keelway
python3 cli.py openapi --out website/openapi.json
cp website/openapi.json website/public/openapi.json
```
