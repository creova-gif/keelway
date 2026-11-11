#!/usr/bin/env bash
# ==============================================================================
# Keelway Universal Engineering Gate Verification Script
# Runs pre-commit, PR, and release verification checks across all subsystems.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"

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

echo "[1/4] Checking Python syntax and compilation..."
find core tests -name "*.py" -exec "${PYTHON_BIN}" -m py_compile {} +
echo "  ✓ Syntax check passed across all Python files."

echo "[2/4] Running Hybrid AI Model Registry & Provider Adapter Tests..."
"${PYTEST_BIN}" tests/test_hybrid_model_registry.py tests/test_hybrid_adapters.py -v --tb=short
echo "  ✓ Model Registry & Provider Adapters verified."

echo "[3/4] Running Hybrid Routing & API Integration Tests..."
"${PYTEST_BIN}" tests/test_hybrid_routing_and_api.py -v --tb=short
echo "  ✓ Unified API & Routing Policies verified."

echo "[4/4] Verifying Security Invariants & Secret Redaction..."
"${PYTEST_BIN}" tests/test_redact.py -v --tb=short
echo "  ✓ Security Invariants and Redaction verified."

echo "================================================================="
echo "   ALL KEELWAY ENGINEERING GATES PASSED [100% VERIFIED]         "
echo "================================================================="
