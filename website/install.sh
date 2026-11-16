#!/bin/sh
# Keelway Local-First AI Platform Installer (POSIX sh)
# Usage:
#   curl -fsSL https://kora-sable.vercel.app/install.sh | sh

set -eu

say() { printf '%s\n' "$*"; }
die() { printf '[x] %s\n' "$*" >&2; exit 1; }

say ""
say "================================================================="
say "  Installing Keelway - Unified Local-First AI Agent Platform"
say "================================================================="
say ""

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
say "[+] System detected: ${OS} (${ARCH})"

PYTHON="${KEELWAY_PYTHON:-}"
if [ -z "$PYTHON" ]; then
    for candidate in python3.13 python3.12 python3.11 python3; do
        if command -v "$candidate" >/dev/null 2>&1 && \
           "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    done
fi
[ -n "$PYTHON" ] || die "Python 3.11+ is required. Install Python 3.11+ or set KEELWAY_PYTHON=/path/to/python3."
say "[+] Python runtime:  $("$PYTHON" -c 'import sys; print(sys.version.split()[0])') ($PYTHON)"

INSTALL_DIR="${KEELWAY_INSTALL_DIR:-${HOME}/.keelway/runtime}"
BIN_DIR="${HOME}/.local/bin"
mkdir -p "$INSTALL_DIR" "$BIN_DIR"

say "[+] Creating isolated Keelway virtual environment..."
"$PYTHON" -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet --upgrade pip

if [ -n "${KEELWAY_SOURCE_DIR:-}" ] && [ -f "${KEELWAY_SOURCE_DIR}/pyproject.toml" ]; then
    say "[+] Installing Keelway from local checkout (${KEELWAY_SOURCE_DIR})..."
    "${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet -e "${KEELWAY_SOURCE_DIR}"
elif [ -n "${KEELWAY_PACKAGE:-}" ]; then
    say "[+] Installing ${KEELWAY_PACKAGE} CLI & OpenCore runtime..."
    "${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet "${KEELWAY_PACKAGE}"
else
    die "No install source configured. Set KEELWAY_SOURCE_DIR=/path/to/keelway for a source checkout, or KEELWAY_PACKAGE=<dist> once the package is published. The 'keelway' name is not yet on PyPI."
fi

ln -sf "${INSTALL_DIR}/.venv/bin/keelway" "${BIN_DIR}/keelway"

case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *)
        say ""
        say "[!] Add ${BIN_DIR} to your PATH in ~/.zshrc or ~/.bashrc:"
        say "    export PATH=\"${BIN_DIR}:\$PATH\""
        ;;
esac

say ""
say "[+] Keelway installed. Run 'keelway init && keelway dev' to launch your workspace."
