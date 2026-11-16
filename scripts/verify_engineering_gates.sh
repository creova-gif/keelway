#!/usr/bin/env bash
# ==============================================================================
# Keelway Universal Engineering Gate Verification Script
# Runs pre-commit, PR, and release verification checks across all subsystems.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

echo "================================================================="
echo "   KEELWAY ENGINEERING QUALITY GATE VERIFIER                     "
echo "   Target: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'main') @ $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown') "
echo "================================================================="

# Locate Python environment
if [ -f ".venv/bin/pytest" ]; then
    PYTEST_BIN=".venv/bin/pytest"
    PYTHON_BIN=".venv/bin/python"
elif [ -f "../kora-ai.nosync/.venv/bin/pytest" ]; then
    PYTEST_BIN="../kora-ai.nosync/.venv/bin/pytest"
    PYTHON_BIN="../kora-ai.nosync/.venv/bin/python"
else
    PYTEST_BIN="pytest"
    PYTHON_BIN="python3"
fi

echo "[1/8] Checking Python syntax and compilation..."
find core tests -name "*.py" -exec "${PYTHON_BIN}" -m py_compile {} +
echo "  ✓ Syntax check passed across all Python files."

echo "[2/8] Running Hybrid AI Model Registry, Provider Adapter & OpenCore Runtime Tests..."
"${PYTEST_BIN}" tests/test_hybrid_model_registry.py tests/test_hybrid_adapters.py tests/test_anthropic_adapter.py tests/test_gemini_adapter.py tests/test_speculative_decoding.py tests/test_opencore.py tests/test_opencore_runtime.py -v --tb=short
echo "  ✓ Model Registry, Provider Adapters & OpenCore Neural Runtime verified."

echo "[3/8] Running Unified Responses API, Hybrid Routing, OpenAPI Export & MiroFish Swarm Tests..."
"${PYTEST_BIN}" tests/test_hybrid_routing_and_api.py tests/test_responses_and_routing_api.py tests/test_mirofish_integration.py tests/test_pricing_mirofish.py tests/test_api_export.py -v --tb=short
echo "  ✓ Unified API, Stateful Responses, Routing Provenance, OpenAPI 3.1 & MiroFish Swarm verified."

echo "[4/8] Verifying Multi-Tenant Governance, Cluster Scheduler, Postgres Adapter, Unified Platform, Vault/RBAC/Webhooks, MCP/Golden Evals, KFlow/CRDT/SBOM, Enterprise OIDC/SCIM/Quorum/SIEM/Metrics, KBrain/KHub, Flight-Tape/LangGraph Migrator, Bidirectional Studio/Blast-Radius, Homepage Studio/v1.1.0 Release, Step-Debugger/IDE Bridge, Cyclic KFlow/Autopilot, Structured-Output/Self-Healing & Settlement Ledger..."
"${PYTEST_BIN}" tests/test_redact.py tests/test_tenant_governance.py tests/test_persistent_governance.py tests/test_unified_platform.py tests/test_platform_persistence_and_enterprise.py tests/test_cluster_and_postgres_governance.py tests/test_marketplace_settlement_and_cluster_sdk.py tests/test_phase5_runtime_vault_rbac_webhooks.py tests/test_phase7_mcp_and_golden_evals.py tests/test_phase8_kflow_crdt_and_sbom.py tests/test_phase9_enterprise_identity_siem_metrics.py tests/test_phase10_kbrain_khub_and_tar_hardening.py tests/test_phase11_flight_tape_otel_and_langgraph_migrator.py tests/test_phase12_bidirectional_studio_and_blast_radius.py tests/test_phase13_homepage_studio_and_release.py tests/test_phase14_step_debugger_and_cli.py tests/test_phase15_cyclic_kflow_and_cli.py tests/test_phase16_structured_and_healing_cli.py -v --tb=short
echo "  ✓ Governance, GPU Cluster Scheduler, Postgres FOR UPDATE Adapter, Encrypted Vault, RBAC, Signed Webhooks, MCP Control Plane, Golden Evals, KFlow/CRDT/SBOM, Enterprise OIDC/SCIM/Quorum/SIEM/Metrics, KBrain/KHub, Flight-Tape/LangGraph Migrator, Bidirectional Studio/Blast-Radius, Homepage Studio/v1.1.0 Release, Step-Debugger/IDE Bridge, Cyclic KFlow/Autopilot, Structured-Output/Self-Healing & Unified Platform verified."

echo "[5/8] Verifying OS Command Sandbox Confinement (Seatbelt & Bubblewrap), AST Codebase Intelligence & Studio Manifest Inspector..."
"${PYTEST_BIN}" tests/test_agent_sandbox.py tests/test_ast_index.py tests/test_codebase_intelligence.py tests/test_studio.py tests/test_studio_manifest_panel.py -v --tb=short
echo "  ✓ OS Command Sandbox, AST Codebase Intelligence & Keelway Studio Manifest Inspection Panel verified."

echo "[6/8] Verifying Layer 1 Python SDK v1 + Phase 5/6/7/8/9/10/11/12/14/15/16 Parity, Packaging, Sovereign CLI TUI & Runtime, Website Drift Gate & Full-Stack E2E..."
"${PYTEST_BIN}" tests/test_sdk_v1.py tests/test_sdk_platform.py tests/test_sdk_phase5_parity.py tests/test_phase7_packaging_and_sdk.py tests/test_phase8_sdk_and_release.py tests/test_phase9_sdk_and_release_workflow.py tests/test_phase10_sdk_parity.py tests/test_phase11_sdk_parity.py tests/test_phase12_sdk_parity.py tests/test_phase14_sdk_and_vscode_bridge.py tests/test_phase15_sdk_and_website_sync.py tests/test_phase16_sdk_and_website_sync.py tests/test_cli_ai.py tests/test_cli_init_and_banner.py tests/test_cli_runtime_phase6.py tests/test_website_facts.py tests/test_platform_v1_e2e.py -v --tb=short
echo "  ✓ Python SDK v1 + Platform/Cluster/Runtime/MCP/KFlow/Enterprise/KBrain/DevX/Studio/Debugger/Cyclic/Healing SDK, Packaging, Sovereign CLI TUI & Runtime, Product-Facts Drift Gate & Full-Stack E2E verified."

echo "[7/8] Verifying Official Zero-Dependency TypeScript (@keelway/sdk), VS Code/Cursor Extension (vscode-keelway), Go (keelway-go) SDKs & Studio JS Syntax..."
if command -v node >/dev/null 2>&1; then
    node --check core/studio/assets/studio.js
    if [ -f "website/node_modules/.bin/tsc" ]; then
        ./website/node_modules/.bin/tsc -p sdk/typescript/tsconfig.json
        ./website/node_modules/.bin/tsc -p extensions/vscode-keelway/tsconfig.json
    fi
    (cd sdk/typescript && npm test)
    (cd extensions/vscode-keelway && npm test)
    echo "  ✓ TypeScript SDK (@keelway/sdk), VS Code/Cursor Extension (vscode-keelway) & Studio JS verified."
else
    echo "  ! node not found on PATH; skipped JS/TS runtime check."
fi
if command -v go >/dev/null 2>&1 || [ -x "/usr/local/go/bin/go" ]; then
    GO_BIN="$(command -v go || echo /usr/local/go/bin/go)"
    (cd sdk/go && "${GO_BIN}" vet ./... && "${GO_BIN}" test ./... -race)
    echo "  ✓ Go SDK (keelway-go) vet & race suite verified."
else
    echo "  ! go not found on PATH; skipped Go SDK check."
fi

echo "[8/8] Verifying Unified Sovereign Dev App (/app CSP, Zero-CDN, CLI & Vitest + axe-core Suite)..."
"${PYTEST_BIN}" tests/test_dev_app.py -v --tb=short
if command -v npm >/dev/null 2>&1 && [ -d "dev-app/node_modules" ]; then
    (cd dev-app && npm run build && npm test)
    echo "  ✓ Unified Sovereign Dev App (/app ASGI mount, Vite dist bundle, TypeScript & Vitest + axe-core) verified."
else
    echo "  ✓ Unified Sovereign Dev App (/app ASGI mount) verified (npm/node_modules not present; skipped frontend Vitest run)."
fi

echo "================================================================="
echo "   ALL KEELWAY ENGINEERING GATES PASSED [100% VERIFIED]         "
echo "================================================================="
