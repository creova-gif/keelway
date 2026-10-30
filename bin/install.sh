#!/usr/bin/env bash
# Kora AI — Single-Line Sovereign Agent Installer
# Usage: curl -fsSL https://get.kora.ai | sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "\n${BLUE}=================================================================${NC}"
echo -e "  ⚡ Installing Kora AI — Sovereign Agent Engineering Runtime"
echo -e "${BLUE}=================================================================${NC}\n"

# 1. Detect Architecture and OS
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
echo -e "[+] System Detected: ${GREEN}${OS} (${ARCH})${NC}"

# 2. Check Python 3.11+
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}[✗] Python 3 is required but was not found. Please install Python 3.11+.${NC}"
    exit 1
fi
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "[+] Python Runtime:  ${GREEN}${PY_VERSION}${NC}"

# 3. Determine Installation Path
INSTALL_DIR="${HOME}/.kora/app"
BIN_DIR="${HOME}/.local/bin"
mkdir -p "${INSTALL_DIR}" "${BIN_DIR}"

# 4. Clone or update repository
if [ -d "${INSTALL_DIR}/.git" ]; then
    echo -e "[+] Updating existing Kora installation..."
    git -C "${INSTALL_DIR}" pull --quiet origin main
else
    echo -e "[+] Downloading Kora AI Sovereign Core..."
    git clone --depth 1 --quiet https://github.com/creova-gif/kora.git "${INSTALL_DIR}"
fi

# 5. Link executable binary
ln -sf "${INSTALL_DIR}/bin/kora" "${BIN_DIR}/kora"

# 6. Verify PATH
if [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
    echo -e "\n${BLUE}[!] Note: Add ${BIN_DIR} to your PATH in ~/.bashrc or ~/.zshrc:${NC}"
    echo -e "    export PATH=\"\${HOME}/.local/bin:\$PATH\"\n"
fi

echo -e "${GREEN}[✓] Installation Complete!${NC}"
echo -e "Run '${GREEN}kora dev${NC}' to launch Kora Dev Studio at http://localhost:7420"
echo -e "Run '${GREEN}kora doctor${NC}' to run system diagnostic checks.\n"
