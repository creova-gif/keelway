# Keelway Developer Quickstart & Evaluation Guide

Welcome to **Keelway by Sorvex Labs**. This guide helps software engineers, tech leads, and security professionals test, run, and evaluate Keelway's local-first developer infrastructure and multi-agent coordination engine.

---

## 1. Fast Setup (Under 60 Seconds)

### Prerequisites
- Python 3.11+ (Python 3.14 fully supported)
- Git 2.30+
- macOS (Apple Silicon arm64 or Intel) or Linux (x86_64 or aarch64)

### One-Line Install Script
```bash
curl -fsSL https://keelway.dev/install.sh | bash
```

### Or Manual Installation
```bash
git clone https://github.com/creova-gif/kora.git keelway
cd keelway
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## 2. Pre-Flight System Diagnostics (`keelway doctor`)

Before executing agent tasks, verify your local environment across all 7 operational dimensions:

```bash
keelway doctor
```

Output:
```
====================================================================
  KEELWAY — Sovereign System Diagnostics & Enterprise Pre-Flight
  Status: HEALTHY | Python 3.14.0 | Darwin 27.0.0
====================================================================

  [1] Database Engine                                            [OK]
  [2] Workspace & Git Context                                    [OK]
  [3] Model Providers & Gateway                                  [OK]
  [4] Air-Gap Compliance (NIST SP 800-53 SC-7)                   [OK]
  [5] Enterprise Entitlements                                    [OK]
  [6] Software Bill of Materials (SBOM)                          [OK]
  [7] Tier 2 Hardware Security HAL                               [OK]

====================================================================
  Diagnostic Result: HEALTHY — 7/7 Dimensions Evaluated.
====================================================================
```

---

## 3. Automated Test Suite (752 Tests, 0 Failures)

Run the complete zero-mock test suite:

```bash
pytest tests -q
```

All 752 unit, integration, and security tests execute locally without cloud egress or network dependencies.

---

## 4. Golden Benchmark Evaluation (`keelway bench`)

Run the 10-task golden benchmark panel verifying directory traversal gates, atomic persistence, AST extraction, semantic search, ReAct loops, policy gating, prompt injection firewall, speculative decoding, payment intent, and flight tape cryptographic seals:

```bash
keelway bench
```

Output:
```
=================================================================
  🏆 KEELWAY GOLDEN EVALUATION BENCHMARK REPORT
  Passed: 10/10 (100.0%)
  Duration: 3.42 ms | p50: 0.28 ms | p95: 0.56 ms
=================================================================
```

---

## 5. Milestone M1: 10-Stage Vertical Slice (`keelway m1`)

Execute the canonical end-to-end autonomous developer workflow:
1. Core Engine Launch
2. Open Local Source Repository
3. Project Explorer Discovery
4. Submit Agent Goal
5. Formulate 3-Step Plan
6. Review Sandboxed Unified Diff
7. Human Approver Grants Mutation
8. Apply Authorized Changes to Disk
9. Run Real Repo Tests (`unittest` / `pytest`)
10. Seal Cryptographic Flight Tape with SHA-256 Hash Chain

```bash
keelway m1
```

---

## 6. Dual-Mode Sovereign IDE & External Editor Sync

Keelway provides two seamless operational modes:

### Mode 1: Sovereign Desktop IDE
Launch the built-in Monaco editor, file tree, terminal, and agent task board:
```bash
keelway dev --desktop
# Or launch the local web server at http://localhost:7420
keelway dev
```

### Mode 2: External Editor Sync Bridge (VS Code & Cursor)
Keep using your preferred editor with live bidirectional synchronization and pessimistic pause on concurrent mutations:
```bash
# Check editor sync watcher status
keelway sync editor

# Launch active workspace directly in VS Code
keelway sync editor --open vscode

# Launch active workspace directly in Cursor
keelway sync editor --open cursor
```

When an external editor modifies a file currently being edited by an agent, Keelway automatically pauses the agent, emits an `EXTERNAL_CONCURRENT_MUTATION` flight tape event, and prompts the developer for a 3-way visual resolution.

---

## 7. Zero-Risk Seeded Demo (`keelway demo`)

To test Keelway inside an isolated sandbox with a seeded bug (`apply_discount(1000, 10)` returning 990 instead of 900):

```bash
keelway demo
```

This launches Keelway Studio on `~/keelway-demo` without modifying your personal code repositories or global settings.
