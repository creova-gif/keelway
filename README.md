# Kora AI

Shared intelligence infrastructure for Kora Technologies.

## Audience

Kora engineering and research team. Later: external developers via Kora Dev.

## Problem

Agent systems multiply cost, latency, and failure modes. Persistent context is lost or becomes unreliable. Tool access is unsafe without scoped permissions, audit, and recovery. Pure API integration does not produce reliable, economical, portable systems under real infrastructure constraints.

**SDG alignment:** SDG 9 (Industry, Innovation and Infrastructure), SDG 8 (Decent Work and Economic Growth).

## Solution

Three connected initiatives on one AI Core:

- **Kora AI Core** — model routing, retrieval, memory, evaluations, security, inference, agent execution.
- **Kora Dev** — CLI-first developer platform with coding agents and sandboxed workspaces.
- **Kora Personal Agent** — internal assistant for research, engineering briefs, documentation, and authorized operations.

## Quick Start

```bash
# Clone and enter
git clone <repo>
cd kora-ai

# Backend
cd core
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Set environment variables (see .env.example)
uvicorn main:app --reload

# Database
# Start PostgreSQL with pgvector and run migrations
```

## Google Cloud Integration

- Backend: Cloud Run
- Data: AlloyDB / Cloud SQL (PostgreSQL) or Firestore
- Storage: Cloud Storage
- Analytics: BigQuery
- Identity: IAM + OIDC

Document exact services used and how they support the product feature.

## Model Providers

The system is multi-provider by design. The model gateway routes requests based on capability, cost, latency, privacy, and residency.

Supported from the start (add more via adapters):

- Anthropic Claude
- OpenAI
- Google Gemini
- NVIDIA NIM / API catalog
- Open-weight models (local or hosted)
- Local / edge small models

See `.env.example` for configuration. Never commit API keys.

**Path to custom models:** Evaluation harness and data pipelines are built first. Fine-tuning (LoRA/QLoRA) or training small domain / African-language models is a later research step, only when measured results justify it.

## Setup / Run Instructions

1. Copy `.env.example` to `.env` and fill secrets.
2. Start PostgreSQL with pgvector extension.
3. Run migrations.
4. Start the FastAPI server.
5. Open the chat interface and authenticate.
6. Test a read-only GitHub retrieval.

## Screenshots / Demo Links

- [Add screenshots of chat interface]
- [Add link to recorded walkthrough]
- [Add link to presentation deck]

## Team Credits & Individual Contributions

| Name | Role | Contributions |
|------|------|---------------|
|      |      |               |

## Project Structure

See `docs/architecture/` and the root structure in the kickoff document.

## Evaluation

Run the evaluation suite:

```bash
python -m evaluations.run --suite coding
```

## Security Notes

- Four permission levels: read, draft, sandbox, modify.
- Secrets only in secret manager.
- External content treated as untrusted.
- Audit log for all tool calls.

## License

[Add license]

## Links

- [Written summary]
- [Presentation deck]
- [Recorded walkthrough]
- ADRs in `docs/adr/`
