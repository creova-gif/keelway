# Kora AI — Commercial Shipping Gap Analysis & Production Roadmap

**Author:** Principal Systems Architect & Senior Product Lead  
**Scope:** `creova-gif/kora` Core Engine, Dev Studio, Agent Runtime, and CLI  
**Objective:** Exhaustive audit of what is missing if Kora AI were to ship to commercial software engineers today as a sovereign, local-first developer tool competing against Devin, Cursor, Claude Code, and Aider.

---

## Executive Summary: The "Day 1" Reality

Kora AI has achieved breakthrough foundational IP:
1. A **closed-loop AST self-healing engine** (`core/orchestration/self_healing.py`) that operates on syntax trees rather than brittle regex.
2. A **2.58x speculative decoding engine** (`core/models/speculative.py`) that accelerates local inference on commodity laptops.
3. An **air-gapped cryptographic kill switch** (`core/security/airgap.py`) guaranteeing zero outgoing network egress.
4. An **omnichannel mobile/Telegram approval loop** (`core/api/messaging.py`) with biometric commit gates.
5. A **Devin × VS Code × Cursor hybrid IDE interface** (`core/studio/index.html`) running locally with zero npm dependencies.

However, if a developer were to download Kora **today** on an external clean machine, they would encounter **7 critical production gaps** that separate an advanced architectural prototype from a commercial developer tool.

---

## The 7 Critical Gaps to Commercial Shipping

```
┌────────────────────────────────────────────────────────────────────────┐
│               7 GAPS TO SHIP KORA COMMERCIALLY TODAY                   │
├──────────────────────────┬──────────────────┬──────────────────────────┤
│ PILLAR                   │ STATUS TODAY     │ REQUIRED FOR SHIP TODAY  │
├──────────────────────────┼──────────────────┼──────────────────────────┤
│ 1. Model Cold-Start      │ Requires Ollama  │ Auto-pull + embedded     │
│                          │ already running  │ llama.cpp C++ runtime    │
├──────────────────────────┼──────────────────┼──────────────────────────┤
│ 2. Real File System IO   │ Hardcoded diff   │ Dynamic workspace tree,  │
│                          │ catalog in Studio│ real read/write/save API │
├──────────────────────────┼──────────────────┼──────────────────────────┤
│ 3. Agent Tool Loop       │ Single-turn chat │ Multi-step ReAct loop    │
│                          │ & test healing   │ (read, edit, bash, plan) │
├──────────────────────────┼──────────────────┼──────────────────────────┤
│ 4. Codebase Indexing     │ Basic SQLite kwd │ Local AST symbol graph + │
│                          │ search in memory │ fastembed vector index   │
├──────────────────────────┼──────────────────┼──────────────────────────┤
│ 5. Two-Way Code Editor   │ Read-only diff   │ Monaco / CodeMirror with │
│                          │ inspector        │ real disk save (Cmd+S)   │
├──────────────────────────┼──────────────────┼──────────────────────────┤
│ 6. Distribution Pipeline │ Manual git clone │ Homebrew, PyPI, and      │
│                          │ + install.sh     │ signed macOS .dmg / App  │
├──────────────────────────┼──────────────────┼──────────────────────────┤
│ 7. Automated Evals Suite │ 1 manual eval doc│ Golden benchmark runner  │
│                          │ (EVAL-001)       │ for SWE-bench & safety   │
└──────────────────────────┴──────────────────┴──────────────────────────┘
```

---

### Gap 1: The Model Cold-Start Problem (Day 1 Zero-Config)

* **The Problem Today:**
  When a user clones Kora and runs `kora chat`, `LocalAdapter` tries connecting to `http://localhost:11434/api/chat`. If the user does not already have Ollama installed, running, and populated with `qwen2.5-coder:7b`, Kora immediately fails with a connection error.
* **What Competitive Tools Do:**
  - *Ollama / Jan / LM Studio:* Provide single-click model downloads with real-time ETA and GB progress bars.
  - *Aider:* Prompts the user: *"No local model found. Enter your API key (Anthropic/OpenAI) or type `ollama pull qwen2.5-coder`"*.
* **Required to Ship Today:**
  1. **Built-in `kora pull <model>` CLI & UI Dialog:** A streaming HTTP downloader that fetches quantized GGUF weights directly from HuggingFace with chunked progress reporting (`0% -> 100%`).
  2. **Bundled Zero-Daemon C++ Inference Runtime:** Include pre-compiled `llama.cpp` shared libraries (`libllama.dylib` on macOS Metal, `libllama.so` on Linux CUDA) so Kora can load GGUF weights directly into VRAM without requiring Ollama or Docker.
  3. **Seamless Cloud Fallback:** If local RAM is <8GB and no Ollama daemon is detected, Kora should offer a clean 1-click prompt: *"Would you like to connect an Anthropic, OpenAI, or Gemini key, or run a 1.5B edge model?"*

---

### Gap 2: Real File System IO & Dynamic Workspace Scanning

* **The Problem Today:**
  The Dev Studio currently displays a rich, pre-packaged catalog of Kora's own core modules (`self_healing.py`, `speculative.py`, `payment_broker.py`). If a developer launches `kora dev` inside an arbitrary project (e.g., a Django backend or a Next.js frontend), the studio does not yet dynamically scan the user's project directory or serve their real files.
* **What Competitive Tools Do:**
  - *VS Code / Cursor / Devin:* The server reads `process.cwd()`, walks the directory tree adhering to `.gitignore`, and serves real file contents via WebSocket/REST.
* **Required to Ship Today:**
  1. `GET /v1/files/tree`: A fast directory walker returning nested JSON representing the real workspace folder structure, ignoring `.git`, `node_modules`, `__pycache__`, and `.venv`.
  2. `GET /v1/files/content?path=<path>`: Returns raw file content with MIME type and syntax language identifier.
  3. `POST /v1/files/save`: Saves user edits or agent patches directly to disk with atomic backup.
  4. `GET /v1/git/diff`: Computes real live `git diff HEAD` against the active repository and renders it in the studio's split-diff viewer.

---

### Gap 3: Autonomous Agent Tool Loop (The "Devin / Antigravity" Action Loop)

* **The Problem Today:**
  `kora chat` currently operates as a single-turn stateful conversational session (`core/orchestration/chat.py`). While `core/orchestration/self_healing.py` can autonomously patch failing tests, Kora does not yet have a generalized multi-step **ReAct Tool-Calling Loop** for general developer instructions.
* **What Devin / Claude Code / Antigravity Do:**
  When a user says: *"Add rate limiting to our payment webhook"*, the agent executes an autonomous loop:
  1. Calls `search_codebase("def payment_webhook")` → Finds `routes.py:112`.
  2. Calls `read_file("routes.py", start_line=100, end_line=130)` → Inspects code.
  3. Calls `edit_file("routes.py", target="...", replacement="...")` → Applies rate-limit decorator.
  4. Calls `run_command("pytest tests/test_payment.py")` → Tests pass.
  5. Displays complete diff to developer and requests commit approval.
* **Required to Ship Today:**
  1. Implement a generalized `AutonomousAgentLoop` in `core/orchestration/agent_loop.py` that loops: `Observe -> Plan -> Call Tool -> Evaluate Output -> Next Step -> Final Propose`.
  2. Register standard developer tools in `core/orchestration/mcp.py`:
     - `read_file(path, start, end)`
     - `write_file(path, content)`
     - `edit_file(path, target, replacement)`
     - `run_command(cmd, timeout)`
     - `search_codebase(regex, directory)`
     - `list_dir(path)`

---

### Gap 4: Codebase Semantic Indexing & Vector Search

* **The Problem Today:**
  In a large codebase (50,000 to 500,000 lines of code), an agent cannot dump every file into the LLM context window without exceeding local VRAM limits or causing prompt dilution.
* **What Competitive Tools Do:**
  - *Cursor & Windsurf:* Build an AST symbol index + vector embeddings database (`sqlite-vec` or LanceDB) to find relevant files in 15 milliseconds.
* **Required to Ship Today:**
  1. **AST Symbol Table:** A lightweight Python background task that extracts classes, functions, docstrings, and imports for every file in the repository upon `kora dev` boot.
  2. **Zero-Cloud Local Embeddings:** Use a tiny 30MB ONNX embedding model (like `nomic-embed-text-v1.5` or `all-MiniLM-L6-v2`) running via pure CPU/Metal to generate embeddings stored in SQLite, allowing semantic code search with zero external cloud egress.

---

### Gap 5: Two-Way Interactive Code Editor (Monaco Editor Integration)

* **The Problem Today:**
  The Dev Studio currently renders unified and split 2-column diffs in read-only syntax blocks. While great for reviewing agent patches, developers frequently want to tweak a line of code manually, add a comment, or fix an import directly in the editor before hitting commit.
* **What Competitive Tools Do:**
  - Embed the **Monaco Editor** (the exact code editor engine that powers VS Code).
* **Required to Ship Today:**
  - Embed Monaco Editor into `core/studio/index.html` via CDN/local bundle so developers have true VS Code-level editing: syntax coloring, bracket matching, multi-cursor, and `Cmd+S` keyboard saving.

---

### Gap 6: Packaging, Distribution & Desktop Binary

* **The Problem Today:**
  Users currently need Git and Python installed to run `kora`. To reach mainstream developers, installation must be a single native action.
* **Required to Ship Today:**
  1. **macOS Homebrew Formula:**
     ```bash
     brew install creova-gif/kora/kora
     ```
  2. **PyPI Package:**
     ```bash
     pip install kora-ai
     ```
  3. **Native Desktop App (Tauri / Rust Wrapper):**
     - Compile a lightweight 12MB native desktop app wrapper using Tauri (`Kora.app` on macOS, `Kora.exe` on Windows).
     - Bundles the local UI and auto-spawns the Kora background daemon with no terminal window required.

---

### Gap 7: Production Evals & Golden Regression Benchmark (`evals/`)

* **The Problem Today:**
  As mandated by our Engineering Framework: *"No AI feature reaches production without an evals/ directory covering correctness, hallucination rate, tool selection, and safety."*
  We currently have `evaluations/EVAL-COMPARE-001.md`, but no automated test harness that runs before every Git push.
* **Required to Ship Today:**
  - An automated evaluation suite:
    - 20 coding challenge benchmarks (SWE-bench lite style).
    - 10 AST self-healing test repair tasks.
    - 10 adversarial prompt injection and secret exfiltration attacks.
    - Automated metrics reporting: Pass rate, token throughput (tokens/sec), and latency.

---

## Action Plan to Reach Commercial Shippability

```
PHASE 1: Core IO & Dynamic Workspace (Immediate)
├── Add GET /v1/files/tree, GET /v1/files/content, POST /v1/files/save
├── Hook Dev Studio to read user's real project files
└── Compute live Git diffs against HEAD

PHASE 2: Agent Action Loop & Tool Registry (Days 2-3)
├── Implement ReAct Agent Loop in core/orchestration/agent_loop.py
├── Register read_file, edit_file, run_command, search_codebase in MCP
└── Connect Dev Studio prompt box to live multi-step agent

PHASE 3: Zero-Config Model Bootstrapper (Days 4-5)
├── Implement streaming kora pull qwen2.5-coder:7b with progress bar
├── Auto-detect Ollama / vLLM / LM Studio on localhost
└── Cloud API key fallback prompt when local VRAM is insufficient

PHASE 4: Distribution & Packaging (Day 6)
├── Publish to PyPI (pip install kora-ai)
├── Create Homebrew tap (brew install kora)
└── Build automated evals regression runner in evals/
```
