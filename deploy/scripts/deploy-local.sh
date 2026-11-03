#!/usr/bin/env bash
set -euo pipefail

echo "===================================================================="
echo "  🚀 KEELWAY SOVEREIGN INFRASTRUCTURE: LOCAL DEPLOYMENT"
echo "===================================================================="

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker &> /dev/null; then
    echo "[-] Error: docker is not installed or not in PATH."
    exit 1
fi

echo "[+] 1. Building and launching containerized infrastructure stack..."
docker compose up -d --build

echo "[+] 2. Waiting for Keelway Control Plane to become healthy..."
MAX_RETRIES=30
RETRY_COUNT=0
HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:8000/ > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    echo "    Waiting for services to initialize... ($((RETRY_COUNT + 1))/$MAX_RETRIES)"
    sleep 2
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ "$HEALTHY" = true ]; then
    echo ""
    echo "===================================================================="
    echo "  ✓ KEELWAY LOCAL INFRASTRUCTURE IS LIVE AND HEALTHY!"
    echo "===================================================================="
    echo "  • Studio Web IDE:      http://localhost:8000"
    echo "  • REST API Docs:       http://localhost:8000/docs"
    echo "  • Local LLM Engine:    http://localhost:11434 (Ollama)"
    echo "  • Outbound Runner:     Active in container 'keelway-runner'"
    echo "===================================================================="
else
    echo "[-] Warning: Health check did not return 200 within timeout. Check container logs:"
    echo "    docker compose logs"
    exit 1
fi
