# Keelway Developer Quickstart & Testing Guide

Welcome to **Keelway by Sorvex Labs**. This guide helps engineers and teams test, run, and evaluate Keelway's local governance envelope around AI coding agents.

---

## 1. Fast Setup

### Prerequisites
- Python 3.11+ (Python 3.14 fully supported)
- Git 2.30+

### Installation
```bash
git clone <repo-url>
cd keelway
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## 2. Automated Test Suite (71 Tests)

Before making any changes, run the full automated test suite:

```bash
PYTHONPATH=keelway pytest keelway/tests -v
```

All 71 tests execute in ~7 seconds without external network dependencies.

---

## 3. One-Click Interactive Developer Demo

To immediately observe all security invariants in action (deny-by-default, isolated worktrees, evaluation gating, human review, two-human quorum, SQLite WAL persistence, and anti-tamper verification):

```bash
python examples/run_developer_demo.py
```

---

## 4. Testing with the Web Dashboard

Keelway includes an interactive operator web dashboard for launching runs, inspecting diffs, and granting approvals.

### Launch Server
```bash
python -m keelway.cli.main serve --host 127.0.0.1 --port 8000
```
Open **`http://127.0.0.1:8000`** in your browser.

### Developer Test Flow in the Dashboard:
1. **Launch an Internal Run:**
   - Select `Internal / Dev (Single Human Review)`.
   - Enter a task prompt (e.g. `Add telemetry endpoint`).
   - Click **Launch Governed Run**.
   - Notice the candidate diff rendered in real-time from the isolated worktree without dirtying your main workspace.
   - Click **Approve Patch** -> Then click **Create Pull Request** and **Deploy to Staging**.
   - Click **Verify Cryptographic Chain** to mathematically verify the hash-chained audit trail.

2. **Launch a Production Run (Two-Human Quorum ADR-045):**
   - Select `Production (Mandatory Two-Human Quorum ADR-045)`.
   - Click **Launch Governed Run**.
   - Notice that single-approval is disabled.
   - Click **Sign as Security Lead (Alice)** -> Status updates to `pending remaining role`.
   - Click **Sign as Platform Owner (Bob)** -> Status updates to `APPROVED`.

---

## 5. Testing with the CLI

You can also operate Keelway entirely from the command line:

### 1. Scaffold a Sandbox Demo Repo
```bash
python -m keelway.cli.main init-demo --dir examples/demo_service
```

### 2. Run a Governed Change
```bash
python -m keelway.cli.main run --repo examples/demo_service --task "Add telemetry healthcheck endpoint"
```
Output:
```
🛡️ Keelway: Initializing governed run for task: Add telemetry healthcheck endpoint
✅ Governed run reached approval gate.
   Run ID: <RUN_ID>
   Approval ID: <APPROVAL_ID>
   Candidate Patch Hash: <HASH>...

--- CANDIDATE PATCH DIFF (ISOLATED WORKSPACE) ---
...
```

### 3. Inspect Run Status & Audit Trail
```bash
python -m keelway.cli.main status --run-id <RUN_ID>
```

### 4. Verify Cryptographic Chain Integrity
```bash
python -m keelway.cli.main verify --run-id <RUN_ID>
```
Output:
```
✅ Run <RUN_ID> VERIFIED: 5 events, 0 tampering detected.
```

### 5. Export Cryptographically Sealed Audit Bundle (FR-09)
```bash
python -m keelway.cli.main export --run-id <RUN_ID> --out audit_bundle.json
```

---

## 6. Inspecting Hardware Qualification Status (Tier 2)

Keelway provides an explicit API endpoint reporting physical hardware readiness vs software emulators:

```bash
curl -s http://127.0.0.1:8000/v1/system/hardware-status | jq .
```

---

## 7. Configuration & Model Switching

Keelway defaults to an offline deterministic mock for instant testing. To connect real LLM inference engines, set environment variables:

- **Local Ollama:** `export KEELWAY_MODEL_PROVIDER=ollama && export OLLAMA_HOST=http://localhost:11434`
- **Local vLLM:** `export KEELWAY_MODEL_PROVIDER=vllm && export VLLM_HOST=http://localhost:8000/v1`
- **OpenAI-Compatible:** `export OPENAI_API_KEY=sk-... && export KEELWAY_MODEL_PROVIDER=openai`
