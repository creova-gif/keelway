#!/bin/sh
# Keelway installer (POSIX sh)
# Usage: from a clone of https://github.com/creova-gif/kora
#   sh website/install.sh
# This script is not a keelway.dev or get.keelway.dev installer.

set -eu

say() { printf '%s\n' "$*"; }
die() { printf '[x] %s\n' "$*" >&2; exit 1; }

say ""
say "================================================================="
say "  Installing Keelway - Sovereign Agent Engineering Runtime"
say "================================================================="
say ""

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
say "[+] System detected: ${OS} (${ARCH})"

command -v git >/dev/null 2>&1 || die "git is required but was not found."

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
[ -n "$PYTHON" ] || die "Python 3.11+ is required. Install it or set KEELWAY_PYTHON=/path/to/python3.11."
say "[+] Python runtime:  $("$PYTHON" -c 'import sys; print(sys.version.split()[0])') ($PYTHON)"

INSTALL_DIR="${KEELWAY_INSTALL_DIR:-${HOME}/.keelway/app}"
BIN_DIR="${HOME}/.local/bin"
mkdir -p "$(dirname "$INSTALL_DIR")" "$BIN_DIR"

if [ -d "${INSTALL_DIR}/.git" ]; then
    say "[+] Updating existing Keelway installation..."
    git -C "$INSTALL_DIR" pull --quiet origin main
else
    say "[+] Downloading Keelway core..."
    git clone --depth 1 --quiet https://github.com/creova-gif/kora.git "$INSTALL_DIR"
fi

say "[+] Creating virtual environment and installing dependencies..."
"$PYTHON" -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet --upgrade pip
"${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet -e "$INSTALL_DIR"

ln -sf "${INSTALL_DIR}/.venv/bin/keelway" "${BIN_DIR}/keelway"

case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *)
        say ""
        say "[!] Add ${BIN_DIR} to your PATH in ~/.bashrc or ~/.zshrc:"
        say "    export PATH=\"\${HOME}/.local/bin:\$PATH\""
        say ""
        ;;
esac

say "[ok] Installation complete."
say "Run 'keelway dev' to launch Keelway Studio at http://localhost:7420"
say "Run 'keelway doctor' to run system diagnostic checks."
