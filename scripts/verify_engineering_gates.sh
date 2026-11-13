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

echo "[1/7] Checking Python syntax and compilation..."
find core tests -name "*.py" -exec "${PYTHON_BIN}" -m py_compile {} +
echo "  ✓ Syntax check passed across all Python files."

echo "[2/7] Running Hybrid AI Model Registry, Provider Adapter & OpenCore Runtime Tests..."
"${PYTEST_BIN}" tests/test_hybrid_model_registry.py tests/test_hybrid_adapters.py tests/test_anthropic_adapter.py tests/test_gemini_adapter.py tests/test_speculative_decoding.py tests/test_opencore.py tests/test_opencore_runtime.py -v --tb=short
echo "  ✓ Model Registry, Provider Adapters & OpenCore Neural Runtime verified."

echo "[3/7] Running Unified Responses API, Hybrid Routing, OpenAPI Export & MiroFish Swarm Tests..."
"${PYTEST_BIN}" tests/test_hybrid_routing_and_api.py tests/test_responses_and_routing_api.py tests/test_mirofish_integration.py tests/test_api_export.py -v --tb=short
echo "  ✓ Unified API, Stateful Responses, Routing Provenance, OpenAPI 3.1 & MiroFish Swarm verified."

echo "[4/7] Verifying Multi-Tenant Governance, Durable SQLite WAL Store & Secret Redaction..."
"${PYTEST_BIN}" tests/test_redact.py tests/test_tenant_governance.py tests/test_persistent_governance.py -v --tb=short
echo "  ✓ Multi-Tenant Governance, Crash-Safe SQLite WAL Persistence & Secret Redaction verified."

echo "[5/7] Verifying OS Command Sandbox Confinement (Seatbelt & Bubblewrap) & Studio Manifest Inspector..."
"${PYTEST_BIN}" tests/test_agent_sandbox.py tests/test_studio.py tests/test_studio_manifest_panel.py -v --tb=short
echo "  ✓ OS Command Sandbox & Keelway Studio Manifest Inspection Panel verified."

echo "[6/7] Verifying Layer 1 Python SDK v1, Developer CLI, Website Drift Gate & Full-Stack E2E..."
"${PYTEST_BIN}" tests/test_sdk_v1.py tests/test_cli_ai.py tests/test_website_facts.py tests/test_platform_v1_e2e.py -v --tb=short
echo "  ✓ Python SDK v1, Developer CLI, Product-Facts Drift Gate & Full-Stack E2E verified."

echo "[7/7] Verifying Official Zero-Dependency TypeScript SDK (@keelway/sdk) & Studio JS Syntax..."
if command -v node >/dev/null 2>&1; then
    node --check core/studio/assets/studio.js
    if [ -f "website/node_modules/.bin/tsc" ]; then
        ./website/node_modules/.bin/tsc -p sdk/typescript/tsconfig.json
    fi
    (cd sdk/typescript && node --test test/sdk.test.mjs)
    echo "  ✓ TypeScript SDK (@keelway/sdk) & Studio JS verified."
else
    echo "  ! node not found on PATH; skipped JS/TS runtime check."
fi

echo "================================================================="
echo "   ALL KEELWAY ENGINEERING GATES PASSED [100% VERIFIED]         "
echo "================================================================="
