<div align="center">

# Keelway v1.1.0 by Sorvex Labs

**Sovereign Local-First Hybrid AI Engineering, Governance & Multi-Agent Platform**

[![Version 1.1.0](https://img.shields.io/badge/release-v1.1.0-emerald.svg)](./CHANGELOG.md)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.14-blue.svg)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-indigo.svg)](./LICENSE)
[![CI](https://github.com/creova-gif/keelway/actions/workflows/ci.yml/badge.svg)](https://github.com/creova-gif/keelway/actions/workflows/ci.yml)

</div>

Keelway `v1.1.0` unifies local open-weight neural inference (**OpenCore**), 4D provenance-routed frontier APIs, deterministic human-approval governance (**P-10 Gate**), Model Context Protocol (**MCP `2025-06-18`**), **KFlow** topological DAG automation, **KSpaces** CRDT state sync, and tri-language zero-dependency SDKs in a single customer-managed stack.

---

## Platform Surfaces

| Surface | Default Bind | Entrypoint / Source | Launch Command |
|---|---|---|---|
| **Unified 10-View Sovereign Dev Tool** | `127.0.0.1:7420/app` | `dev-app/` → `core/dev_app_dist/` (`core.main:app`) | `keelway dev` |
| **Keelway Studio IDE** | `127.0.0.1:7420/studio` | `core/studio/` (`core.main:app`) | `keelway dev` or `keelway desktop` |
| **Governance Control Plane** | `127.0.0.1:8000/` | `keelway/api/app.py` (`keelway-ops`) | `keelway-ops serve` or `make serve` |
| **Next.js 15 Product & Docs Site** | `:3000` (dev/prod) | `website/` | `npm --prefix website run dev` |

---

## Core v1.1.0 Capabilities

- **Unified 10-View Sovereign Dev Tool (`/app`)**: Overview, Coding Workspace (AST symbol index + safe patcher), Agent Teams, PM Issues & Sprints, Product PRDs & Feedback, Diataxis Docs, KFlow Automation & KSpaces CRDT, No-Code Blueprint Studio, Security/Vault/MCP/SBOM, and Subscriptions/Golden Evals — verified against **WCAG 2.2 AA (`axe-core`)**.
- **Hybrid OpenCore + Frontier 4D Gateway**: Drop-in `/v1/chat/completions`, stateful `/v1/responses`, `/v1/routing/explain` (weight license, hosting, inference operator, data residency boundary), `/v1/opencore/*` hardware/LoRA/Modelfile control, and `/v1/eval/swarm` MiroFish multi-agent simulation.
- **Calibrated 5-Tier Pricing & BYOM 0% Markup**: Community (`$0`), BYOM Seat (`$15/seat/mo` annual — **0% token markup** on customer API keys or local GPUs), Pro (`$29/seat/mo`), Team (`$49/seat/mo`), and Enterprise Custom.
- **P-10 Human Approval Gate & Supply Chain Security**: Separation-of-duty P-10 human approval gate (`core/security/approval_rules.py`, `keelway/approvals/quorum.py`), workspace RBAC (`owner`, `admin`, `developer`, `operator`, `viewer`), AES-256-GCM local secret vault, SSRF-hardened HMAC-SHA256 webhooks, OS sandboxing (macOS Seatbelt & Linux Bubblewrap), and CycloneDX 1.5 SBOM provenance (`/v1/platform/security/sbom`).
- **MCP `2025-06-18` Control Plane, KFlow DAGs & KSpaces CRDT**: Built-in + SSE/stdio MCP server registry with automatic DLP secret redaction (`/v1/platform/mcp/*`), cycle-checked topological DAG execution with per-run token budgets and P-10 pause/resume (`/v1/platform/automation/workflows/execute`), and deterministic Lamport LWW CRDT state sync (`/v1/platform/kspaces/*`).
- **16-Probe Deterministic Golden Evaluation Suite**: Zero-egress subsystem verification across `workspace_ast`, `governance_p10`, `security_redteam`, and `routing_pricing` with SHA-256 SQLite WAL receipts (`keelway eval-suite --category all`).

---

## Installation

### 1. Source Checkout or Python Wheel (`pip` / `uv`)

```bash
git clone https://github.com/creova-gif/keelway.git
cd keelway
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Build & install standalone wheel (bundles /app and /studio SPA assets)
python -m build --wheel --outdir dist/
```

Installed console scripts:
- `keelway` → `cli:main` (Unified Dev Tool, Studio, MCP, Golden Eval Suite, Vault, Workspace, TUI)
- `keelway-ops` → `keelway.cli.main:main` (Governance Control Plane `:8000`, Runner Daemon, Audit Verification)
- `keelway-core` → deprecated alias for `keelway-ops` (emits a warning; will be removed in a future release)

### 2. POSIX Installer & Homebrew Formula

```bash
# Inspect zero-write installation plan first
./scripts/install.sh --dry-run --json
sh website/public/install.sh --dry-run

# Homebrew formula (macOS / Linuxbrew)
ruby -c Formula/keelway.rb
```

### 3. Non-Root Docker & Docker Compose

`Dockerfile` builds a multi-stage `python:3.12-slim` image running as unprivileged UID `10001:10001` with a persistent `/data` volume (`KEELWAY_STATE_DIR=/data/.keelway`, `KEELWAY_DB_PATH=/data/keelway_audit.db`), exposing both `:8000` (Governance Control Plane) and `:7420` (Unified Platform API & `/app`).

```bash
export KEELWAY_POLICY_SIGNING_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
docker compose up -d
```

---

## Official Tri-Language SDKs (100% Parity)

All three SDKs expose full parity across Inference, 4D Routing, OpenCore, Governance, GPU Cluster Scheduling, MCP Control Plane, Golden Evals, KFlow DAG Execution, KSpaces CRDT Sync, and CycloneDX SBOM verification:

1. **Python (`core.sdk`)** — Sync `KeelwayClient` & Async `AsyncKeelwayClient`:
   ```python
   from core.sdk import KeelwayClient

   with KeelwayClient(base_url="http://127.0.0.1:7420", token="kw_live_...") as client:
       run = client.platform.execute_kflow_dag("WF-01", nodes=[{"id": "lint", "kind": "agent"}])
       sbom = client.platform.get_platform_sbom()
   ```
2. **TypeScript (`@keelway/sdk` in `sdk/typescript/`)** — Zero runtime dependencies, Node 20+ / Bun / Deno / Workers:
   ```ts
   import { KeelwayClient } from "@keelway/sdk";

   const client = new KeelwayClient({ baseUrl: "http://127.0.0.1:7420", apiKey: "kw_live_..." });
   const state = await client.platform.getKspacesState({ workspace_id: "default" });
   ```
3. **Go (`github.com/keelway/keelway-go` in `sdk/go/`)** — Pure Go 1.22+ standard library:
   ```go
   client := keelway.NewClient("http://127.0.0.1:7420", keelway.WithAPIKey("kw_live_..."))
   sbom, err := client.Platform.GetPlatformSbom(ctx, "default")
   ```

---

## Engineering Verification & Release Gates

```bash
# 1. Universal 8-stage engineering quality gate (Python, Tri-SDKs, Website drift, Sandbox, E2E)
./scripts/verify_engineering_gates.sh

# 2. Deterministic 16-probe Golden Evaluation Suite
keelway eval-suite --category all --json

# 3. Official TypeScript & Go SDK suites + Unified Dev Tool WCAG 2.2 AA suite
./website/node_modules/.bin/tsc -p sdk/typescript/tsconfig.json && npm --prefix sdk/typescript test
(cd sdk/go && go vet ./... && go test ./... -race)
npm --prefix dev-app test

# 4. Fail-closed macOS Seatbelt + live Ollama release gate (.github/workflows/release-gate-macos.yml)
python -m tests.release_live_gate
```

---

## Repository Layout

```text
├── cli.py                    # Sovereign developer CLI (`keelway`)
├── core/                     # Unified Platform API (:7420), OpenCore, MCP, KFlow, KSpaces, Vault, SDK
├── keelway/                  # Governance Control Plane (:8000), Policy Engine, Quorum, Audit Ledger
├── dev-app/                  # React 19 + TypeScript Unified 10-View Sovereign Dev Tool -> core/dev_app_dist/
├── website/                  # Next.js 15 App Router marketing, interactive pricing, docs & marketplace
├── sdk/
│   ├── typescript/           # @keelway/sdk v1.1.0 (zero runtime dependencies)
│   └── go/                   # keelway-go (pure Go stdlib)
├── Formula/keelway.rb        # Homebrew formula
└── tests/                    # Comprehensive unit, adversarial safety, E2E, and live release gates
```
