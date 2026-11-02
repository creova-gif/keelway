<div align="center">

# ⚡ Keelway
### Local-first, deterministic AI agent infrastructure for developers — by Sorvex Labs

[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![CI](https://github.com/creova-gif/kora/actions/workflows/ci.yml/badge.svg)](https://github.com/creova-gif/kora/actions/workflows/ci.yml)
[![Security Firewall](https://img.shields.io/badge/security-DLP%20%2B%20Prompt%20Guard-orange.svg)](core/security/)
[![Architecture](https://img.shields.io/badge/architecture-Sovereign%20AI%20Core-purple.svg)](docs/architecture/)
[![License: Proprietary](https://img.shields.io/badge/license-Keelway%20Proprietary-red.svg)](LICENSE)

*Built for zero vendor lock-in, automated failover, verifiable state machines, hybrid memory retrieval, and edge offline execution.*

---

</div>

## 📌 Executive Summary

Modern AI agent frameworks suffer from three systemic engineering flaws:
1. **Opaque Loop Failures**: Infinite recursive retries that silently drain API credit balances without deterministic exit conditions.
2. **Context Amnesia & Hallucination**: Unscoped retrieval where agents cite outdated or non-existent files.
3. **Security Vulnerabilities**: External text from PRs, documentation, or untrusted user input can execute indirect prompt injections or exfiltrate private credentials.

**Keelway** is a hardened, production-ready sovereign agent runtime. It unifies multi-provider routing, proactive DLP/injection firewalls, dual-index hybrid vector memory, and human-in-the-loop state machines into a single, cohesive developer platform.

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
* If external cloud frontier APIs experience outages, rate limits, or quota exhaustion, Keelway automatically routes traffic to local edge models with **$0.00 inference cost**.

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

## 🧪 Experimental / Simulated Modules

The following modules are prototypes: they have data models and unit tests, but are not yet wired to real transports, models, or providers. Their outputs are simulated or in-memory only.

| Module | Current state |
|---|---|
| `core/orchestration/mesh.py` (multi-agent mesh) | Returns fixed review results; no agents are invoked |
| `core/orchestration/p2p_mesh.py` (team mesh) | Peer registry only; no network discovery or task dispatch |
| `core/models/speculative.py` | Simulated draft/verify loop; no model calls |
| `core/models/edge_loader.py` | Hardware/Ollama probe; not used by the local adapter |
| `core/storage/ap2.py`, `ledger.py`, `payment_broker.py` | Payload builders only; no live payment rails, not for real funds |
| `core/api/messaging.py`, `keelway notify` | Builds Telegram/WhatsApp/push/SMS payloads; nothing is sent |
| `core/api/telephony.py` | USSD formatting helpers; no webhook route |
| `core/storage/crdt.py` | In-memory LWW register; no persistence or transport |
| `core/orchestration/mcp.py` | In-process JSON-RPC dispatcher; no stdio/SSE transport |
| `core/security/telemetry.py` | In-memory spans; no OpenTelemetry exporter |
| `core/studio/index.html` panels | Client-side demos; not yet connected to the API/WebSocket |
| `mobile/` | Expo scaffold; not runnable yet |

---

## ⚡ Quickstart

### 1. Installation & Environment Setup

```bash
# Clone the repository
git clone https://github.com/creova-gif/kora.git
cd keelway

# Create and activate Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Keelway and its dependencies (add ",postgres" for PostgreSQL)
pip install -e ".[dev]"

# Configure environment variables
cp env.example .env
```

### 2. Run Diagnostics

Verify your local environment, database connectivity, and configured providers:
```bash
./bin/keelway doctor
```

---

## 🔐 Authentication, RBAC & Audit

Every `/v1` route and the Studio WebSocket require an API token (`/health` and the Studio page itself are public).

- `keelway dev` prints a Studio link with this run's **launch token** (owner role). Set `KEELWAY_API_TOKEN` to pin it.
- Mint named tokens for scripts, CI, or teammates: `keelway token create --name ci --role engineer` (also `keelway token list`, `keelway token revoke <id>`). Only SHA-256 hashes are stored.
- Send tokens as `Authorization: Bearer <token>` (WebSocket: `?token=`).

| Role | Can |
|---|---|
| `owner` | everything, including minting/revoking tokens |
| `admin` | run agents, approve `awaiting_approval` tasks, build payment intents, toggle air-gap, manage memories, read audit |
| `engineer` | run agents (tasks, completions, workflows, self-healing, flight forks), manage memories, read audit |
| `auditor` | read-only, including the audit log |

Every permission decision on a mutating action is appended to a hash-chained audit log (`GET /v1/audit`, `GET /v1/audit/verify`, and the Studio **Audit** tab). `AUTH_REQUIRED=false` disables auth for throwaway local hacking only.

---

## 💻 CLI Commands & Workflows

### 💬 Interactive Terminal REPL (`keelway chat`)
Launch the stateful conversational workspace with automated hybrid memory recall and thinking token display:
```bash
./bin/keelway chat --provider local
```
*In-chat commands:*
* `/memory <query>` — Run live hybrid semantic search over memory.
* `/clear` — Reset dialogue turn context while retaining system safety instructions.
* `/exit` — Gracefully close session.

---

### 🧠 Scoped Memory & Document Ingestion (`keelway memory`)
Ingest architecture decisions, codebases, or research notes into chunked memories with line-level provenance:
```bash
# Ingest an architecture document into the 'architecture' scope
./bin/keelway memory ingest docs/architecture/ADR-001-AI-Core-Architecture.md --scope architecture

# Run a hybrid vector + lexical search
./bin/keelway memory search "model routing architecture" --hybrid --scope architecture
```

---

### 📋 Workflow 1: Engineering Brief Generator (`keelway brief`)
Generates an evidence-grounded pull request brief, assesses risks, and verifies governance alignment:
```bash
./bin/keelway brief \
  --title "Add task state machine to agent backend" \
  --desc "Deterministic state machine with retry loop" \
  --files core/orchestration/state.py tests/test_state.py \
  --failing test_retry_on_transient_error \
  --provider local
```

---

### 🔬 Workflow 2: Research Summarization (`keelway summarize`)
Synthesizes research whitepapers or ADRs and persists key takeaways into memory:
```bash
./bin/keelway summarize docs/architecture/ADR-001-AI-Core-Architecture.md --store-memory --provider local
```

---

### 🛡️ Workflow 3: Ephemeral Sandboxed Test Analysis (`keelway test-sandbox`)
Executes test commands within an isolated container environment with mandatory human sign-off:
```bash
./bin/keelway test-sandbox "pytest tests/test_gateway.py" --approve --provider local
```

---

### 📦 LoRA Training Dataset Exporter (`keelway dataset`)
Export verified agent execution traces into fine-tuning datasets:
```bash
./bin/keelway dataset export \
  --output research/datasets/seed/v1.jsonl \
  --format sharegpt \
  --limit 50
```

---

### 📊 Benchmark Evaluation Harness (`keelway eval`)
Runs the standardized `EVAL-COMPARE-001` test suite comparing latency, token consumption, and citation accuracy:
```bash
./bin/keelway eval --providers local
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
pytest
```

CI runs `ruff check .` and `pytest` on Python 3.11 and 3.12 for every push and pull request.

---

## 📂 Project Organization

```text
keelway/
├── bin/
│   └── keelway                            # Executable CLI entrypoint
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
│   ├── architecture/                   # ADR-001, KEELWAY.md, engineering framework
│   ├── research/                       # Research agenda, own-model track, LoRA plan
│   ├── roadmap/                        # 90-day implementation plan, workflows
│   └── archive/                        # Historical project kickoff materials
├── evaluations/
│   ├── EVAL-COMPARE-001.md             # Benchmark specification & rubric
│   └── run_compare.py                  # Multi-model evaluation benchmark runner
├── research/
│   └── datasets/                       # Trace extraction, formatting, and JSONL seeds
├── tests/                              # Pytest test suite
├── env.example                         # Sanitized environment configuration template
├── pytest.ini                          # Pytest configuration
└── requirements.txt                    # Points to pyproject.toml (pip install -e .)
```

---

## 🔒 Security Policy

* **API Key Safety**: Never commit `.env` or credentials to version control. Pre-commit scans enforce zero secret exposure.
* **Secrets stay out of agent commands**: commands an agent runs (`run_command`), the sandboxed test workflow and the self-healing test runs do not inherit API keys, tokens, cloud credentials or URLs containing passwords (`core/security/env_scrub.py`). To pass a specific variable on purpose, start Keelway with `KEELWAY_COMMAND_ENV_PASSTHROUGH=NAME1,NAME2`. This is a filter on variable names and common credential shapes, not isolation: there is no container sandbox yet, so a command can still read files your user can read.
* **Audit Trails**: All task transitions, prompt payloads, model latencies, and human approvals are permanently recorded in SQLite/PostgreSQL audit logs.

---

<div align="center">
  <sub>Engineered by Sorvex Labs. Dedicated to building sovereign, affordable, and resilient artificial intelligence.</sub>
</div>
