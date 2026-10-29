<div align="center">

# ⚡ Kora AI
### Sovereign, Deterministic Runtime Infrastructure for Autonomous AI Agents

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![Tests Passing](https://img.shields.io/badge/tests-29%2F29%20passed-brightgreen.svg)](tests/)
[![Security Firewall](https://img.shields.io/badge/security-DLP%20%2B%20Prompt%20Guard-orange.svg)](core/security/)
[![Architecture](https://img.shields.io/badge/architecture-Sovereign%20AI%20Core-purple.svg)](docs/architecture/)
[![License: Proprietary](https://img.shields.io/badge/license-Kora%20Proprietary-red.svg)](LICENSE)

*Built for zero vendor lock-in, automated failover, verifiable state machines, hybrid memory retrieval, and edge offline execution.*

---

</div>

## 📌 Executive Summary

Modern AI agent frameworks suffer from three systemic engineering flaws:
1. **Opaque Loop Failures**: Infinite recursive retries that silently drain API credit balances without deterministic exit conditions.
2. **Context Amnesia & Hallucination**: Unscoped retrieval where agents cite outdated or non-existent files.
3. **Security Vulnerabilities**: External text from PRs, documentation, or untrusted user input can execute indirect prompt injections or exfiltrate private credentials.

**Kora AI** is a hardened, production-ready sovereign agent runtime. It unifies multi-provider routing, proactive DLP/injection firewalls, dual-index hybrid vector memory, and human-in-the-loop state machines into a single, cohesive developer platform.

---

## 🏛️ System Architecture

```text
                               ┌──────────────────────────────────────────────┐
                               │       Client Interfaces & Access Layers       │
                               │   CLI Tool  •  Interactive REPL  •  REST API │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │          AI Security Firewall (DLP)          │
                               │   • Regex Secret Redaction (API/SSH/DB keys) │
                               │   • Prompt Injection & Jailbreak Detector    │
                               │   • Tool Execution Allowlist & Path Guard    │
                               └──────────────────────┬───────────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
┌──────────────────────────────────────────────┐              ┌──────────────────────────────────────────────┐
│        Hybrid Semantic Memory & RAG          │              │         Multi-Provider Model Gateway         │
│  • BM25 Lexical + 128-dim Dense Vectors      │              │  • Dynamic Policy Router & Latency Fallback  │
│  • Provenance Tracking (#L1-L40 File URIs)   │              │  • Anthropic Claude 3.5 Sonnet               │
│  • Sub-millisecond Cosine Similarity         │              │  • OpenAI GPT-4o / Google Gemini 3.8 Flash   │
│  • Chunked Document Ingestion Engine         │              │  • Local Edge (Ollama / Qwen 3.5 / Llama 3)  │
└──────────────────────┬───────────────────────┘              └──────────────────────┬───────────────────────┘
                       │                                                             │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │         Deterministic State Machine          │
                               │  CREATED ➔ PLANNING ➔ [APPROVAL] ➔ EXECUTING │
                               │  Trace Auditing • Task Replay • Evidence Log │
                               └──────────────────────┬───────────────────────┘
                                                      │
                                                      ▼
                               ┌──────────────────────────────────────────────┐
                               │      Autonomous Training Pipeline (LoRA)     │
                               │   Extracts verified traces ➔ ShareGPT/OpenAI │
                               │   Generates SHA-256 Manifest for Unsloth/SFT │
                               └──────────────────────────────────────────────┘
```

---

## 🚀 Key Capabilities

### 1. Multi-Provider Fallback & Local Edge Execution
* Seamless automated failover across **Anthropic Claude**, **Google Gemini**, **OpenAI GPT**, and **Local Ollama** (`qwen3.5:latest`).
* If external cloud frontier APIs experience outages, rate limits, or quota exhaustion, Kora automatically routes traffic to local edge models with **$0.00 inference cost**.

### 2. Proactive Security & DLP Firewall
* Intercepts and masks credentials (Anthropic `sk-ant-*`, OpenAI `sk-proj-*`, Google `AIza*`, AWS tokens, and database passwords) before prompts touch model APIs or database traces.
* Blocks indirect prompt injection attacks, jailbreaks, and delimiter manipulation with weighted risk scores.
* Strictly prevents destructive shell commands (`rm -rf /`, `mkfs`, fork bombs) and unauthorized directory traversals (`/etc/shadow`, `~/.ssh`).

### 3. Hybrid Semantic Memory (Lexical + Dense Vector RAG)
* Dual-scoring algorithm: Combines token frequency overlap with normalized 128-dimensional dense vector embeddings.
* Every memory record stores exact line-level provenance (e.g., `file:///path/to/ADR-001.md#L41-L57`) so agents cite real sources without hallucination.

### 4. Deterministic State Machine & 4-Tier Safety Gate
* All background actions run through an explicit state machine (`CREATED` $\rightarrow$ `PLANNING` $\rightarrow$ `AWAITING_APPROVAL` $\rightarrow$ `EXECUTING` $\rightarrow$ `VERIFYING` $\rightarrow$ `COMPLETED`).
* High-risk operations (Tier 3: sandbox shell command execution) are hard-gated and refuse to run without human authorization (`--approve`).

### 5. Autonomous LoRA Training Pipeline
* Extracts verified production task traces from SQLite (`kora_tasks` and `kora_traces`).
* Cleans and formats conversations into **ShareGPT** and **OpenAI Fine-Tuning JSONL** datasets.
* Automatically writes a cryptographic `manifest.json` (SHA-256 hash, sample count, licensing, and consent flags) for fine-tuning 7B models on Unsloth or Axolotl.

---

## ⚡ Quickstart

### 1. Installation & Environment Setup

```bash
# Clone the repository
git clone https://github.com/creova-gif/kora.git
cd kora

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp env.example .env
```

### 2. Run Diagnostics

Verify your local environment, database connectivity, and configured providers:
```bash
./bin/kora doctor
```

---

## 💻 CLI Commands & Workflows

### 💬 Interactive Terminal REPL (`kora chat`)
Launch the stateful conversational workspace with automated hybrid memory recall and thinking token display:
```bash
./bin/kora chat --provider local
```
*In-chat commands:*
* `/memory <query>` — Run live hybrid semantic search over memory.
* `/clear` — Reset dialogue turn context while retaining system safety instructions.
* `/exit` — Gracefully close session.

---

### 🧠 Scoped Memory & Document Ingestion (`kora memory`)
Ingest architecture decisions, codebases, or research notes into chunked memories with line-level provenance:
```bash
# Ingest an architecture document into the 'architecture' scope
./bin/kora memory ingest docs/architecture/ADR-001-AI-Core-Architecture.md --scope architecture

# Run a hybrid vector + lexical search
./bin/kora memory search "model routing architecture" --hybrid --scope architecture
```

---

### 📋 Workflow 1: Engineering Brief Generator (`kora brief`)
Generates an evidence-grounded pull request brief, assesses risks, and verifies governance alignment:
```bash
./bin/kora brief \
  --title "Add task state machine to agent backend" \
  --desc "Deterministic state machine with retry loop" \
  --files core/orchestration/state.py tests/test_state.py \
  --failing test_retry_on_transient_error \
  --provider local
```

---

### 🔬 Workflow 2: Research Summarization (`kora summarize`)
Synthesizes research whitepapers or ADRs and persists key takeaways into memory:
```bash
./bin/kora summarize docs/architecture/ADR-001-AI-Core-Architecture.md --store-memory --provider local
```

---

### 🛡️ Workflow 3: Ephemeral Sandboxed Test Analysis (`kora test-sandbox`)
Executes test commands within an isolated container environment with mandatory human sign-off:
```bash
./bin/kora test-sandbox "pytest tests/test_gateway.py" --approve --provider local
```

---

### 📦 LoRA Training Dataset Exporter (`kora dataset`)
Export verified agent execution traces into fine-tuning datasets:
```bash
./bin/kora dataset export \
  --output research/datasets/seed/v1.jsonl \
  --format sharegpt \
  --limit 50
```

---

### 📊 Benchmark Evaluation Harness (`kora eval`)
Runs the standardized `EVAL-COMPARE-001` test suite comparing latency, token consumption, and citation accuracy:
```bash
./bin/kora eval --providers local
```

---

## 📈 Benchmark Results (`EVAL-COMPARE-001`)

Evaluated on local Apple Silicon hardware with zero cloud dependencies:

| Metric | Local Edge (`qwen3.5:latest`) | Anthropic Claude 3.5 Sonnet | OpenAI GPT-4o-mini |
| :--- | :--- | :--- | :--- |
| **Overall Score** | **5.0 / 5.0 (PASS)** | 5.0 / 5.0 (PASS) | 4.8 / 5.0 (PASS) |
| **Summary Precision** | 1.0 / 1.0 | 1.0 / 1.0 | 1.0 / 1.0 |
| **Risk Prioritization** | 1.0 / 1.0 | 1.0 / 1.0 | 0.9 / 1.0 |
| **File Citations** | 1.0 / 1.0 | 1.0 / 1.0 | 1.0 / 1.0 |
| **Inference Cost** | **$0.00000** | ~$0.01500 | ~$0.00300 |
| **Data Privacy** | **100% On-Device / Air-Gapped** | Cloud API | Cloud API |

---

## 🧪 Test Suite & Verification

The test suite enforces 100% verification before code is merged:

```bash
PYTHONPATH=. pytest tests/
```

```text
============================= test session starts ==============================
collected 29 items

tests/test_api.py ...                                                    [ 10%]
tests/test_chat.py .                                                     [ 13%]
tests/test_dataset_pipeline.py .                                         [ 17%]
tests/test_gateway.py ...                                                [ 27%]
tests/test_memory.py ...                                                 [ 37%]
tests/test_security.py .....                                             [ 55%]
tests/test_state_machine.py ....                                         [ 68%]
tests/test_state_machine_unittest.py ....                                [ 82%]
tests/test_workflows.py .....                                            [100%]

============================== 29 passed in 0.41s ==============================
```

---

## 📂 Project Organization

```text
kora/
├── bin/
│   └── kora                            # Executable CLI entrypoint
├── cli.py                              # Central CLI dispatcher and command router
├── core/
│   ├── api/                            # FastAPI REST endpoints & Pydantic schemas
│   ├── config.py                       # Pydantic Settings & environment variables
│   ├── main.py                         # FastAPI application factory
│   ├── models/
│   │   ├── adapters/                   # Anthropic, OpenAI, Gemini, Local adapters
│   │   └── gateway.py                  # Model Gateway with policy routing & failover
│   ├── orchestration/
│   │   ├── chat.py                     # Interactive REPL session engine
│   │   ├── state.py                    # Deterministic state machine & approval tiers
│   │   └── workflows/                  # PR Brief, Research Summary, Sandboxed Tests
│   ├── security/
│   │   └── firewall.py                 # DLP scanner, injection detector, tool guard
│   └── storage/
│       ├── database.py                 # Async SQLAlchemy engine & connection manager
│       ├── memory.py                   # Hybrid semantic vector search & RAG service
│       └── models.py                   # Task, Trace, Evidence, Memory ORM schemas
├── docs/
│   ├── architecture/                   # ADR-001, KORA.md, engineering framework
│   ├── research/                       # Research agenda, own-model track, LoRA plan
│   ├── roadmap/                        # 90-day implementation plan, workflows
│   └── archive/                        # Historical project kickoff materials
├── evaluations/
│   ├── EVAL-COMPARE-001.md             # Benchmark specification & rubric
│   └── run_compare.py                  # Multi-model evaluation benchmark runner
├── research/
│   └── datasets/                       # Trace extraction, formatting, and JSONL seeds
├── tests/                              # Pytest test suite (29 unit & integration tests)
├── env.example                         # Sanitized environment configuration template
├── pytest.ini                          # Pytest configuration
└── requirements.txt                    # Pinned Python package dependencies
```

---

## 🔒 Security Policy

* **API Key Safety**: Never commit `.env` or credentials to version control. Pre-commit scans enforce zero secret exposure.
* **Least Privilege**: Sandboxed processes run under isolated container namespaces without root privileges.
* **Audit Trails**: All task transitions, prompt payloads, model latencies, and human approvals are permanently recorded in SQLite/PostgreSQL audit logs.

---

<div align="center">
  <sub>Engineered by Kora Technologies. Dedicated to building sovereign, affordable, and resilient artificial intelligence.</sub>
</div>
