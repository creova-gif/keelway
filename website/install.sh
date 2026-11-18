#!/bin/sh
# Keelway Local-First AI Platform Installer (POSIX sh)
# Usage:
#   curl -fsSL https://kora-sable.vercel.app/install.sh | sh
#
# Install sources (first match wins):
#   KEELWAY_SOURCE_DIR=/path/to/checkout  local source tree
#   KEELWAY_PACKAGE=<pip spec>            published package (once on PyPI)
#   KEELWAY_GIT_URL=<git url>             clone + editable install
#                                        (default: public canonical repo)

set -eu

say() { printf '%s\n' "$*"; }
die() { printf '[x] %s\n' "$*" >&2; exit 1; }

INSTALL_DIR="${KEELWAY_INSTALL_DIR:-${HOME}/.keelway/runtime}"
BIN_DIR="${HOME}/.local/bin"
DATA_DIR="${KEELWAY_DATA_DIR:-${HOME}/.keelway}"
UNINSTALL=0
PURGE=0
while [ "$#" -gt 0 ]; do
    case "$1" in
        --uninstall) UNINSTALL=1; shift ;;
        --purge) PURGE=1; shift ;;
        -h|--help)
            say "Usage: install.sh [--uninstall] [--purge]"
            say "  Installs Keelway into ${INSTALL_DIR} with a CLI symlink in ${BIN_DIR}."
            say "  --uninstall removes the runtime + symlink, preserving ${DATA_DIR}."
            say "  --purge (with --uninstall) also removes the data directory."
            say "  Rollback: KEELWAY_GIT_REF=<tag-or-branch> sh install.sh"
            exit 0 ;;
        *) die "Unknown option: $1 (pass --help for usage)." ;;
    esac
done
[ "$PURGE" -eq 0 ] || [ "$UNINSTALL" -eq 1 ] || die "--purge requires --uninstall."

if [ "$UNINSTALL" -eq 1 ]; then
    rm -f "${BIN_DIR}/keelway"
    rm -rf "${INSTALL_DIR}"
    say "[+] Removed CLI symlink and runtime: ${INSTALL_DIR}"
    if [ "$PURGE" -eq 1 ]; then
        rm -rf "${DATA_DIR}"
        say "[+] Purged data directory: ${DATA_DIR}"
    else
        say "[+] Preserved data directory: ${DATA_DIR} (re-run with --purge to remove)"
    fi
    exit 0
fi

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

# Resolve install source before touching disk. Default: clone the public
# canonical repo (github.com/creova-gif/kora — public since 2026-11-17).
# KEELWAY_SOURCE_DIR / KEELWAY_PACKAGE still take precedence when set.
KEELWAY_GIT_URL="${KEELWAY_GIT_URL:-https://github.com/creova-gif/kora.git}"
if [ -n "${KEELWAY_SOURCE_DIR:-}" ] && [ -f "${KEELWAY_SOURCE_DIR}/pyproject.toml" ]; then
    INSTALL_SOURCE="source:${KEELWAY_SOURCE_DIR}"
elif [ -n "${KEELWAY_PACKAGE:-}" ]; then
    INSTALL_SOURCE="package:${KEELWAY_PACKAGE}"
elif [ -n "${KEELWAY_GIT_URL:-}" ]; then
    INSTALL_SOURCE="git:${KEELWAY_GIT_URL}"
else
    die "No install source configured. Set one of:
    KEELWAY_SOURCE_DIR=/path/to/checkout   (local source tree)
    KEELWAY_PACKAGE=<pip spec>             (published package)
    KEELWAY_GIT_URL=<git url>              (public source mirror)"
fi

mkdir -p "$INSTALL_DIR" "$BIN_DIR"

say "[+] Creating isolated Keelway virtual environment..."
"$PYTHON" -m venv "${INSTALL_DIR}/.venv"
"${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet --upgrade pip

case "$INSTALL_SOURCE" in
    source:*)
        say "[+] Installing Keelway from local checkout (${KEELWAY_SOURCE_DIR})..."
        "${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet -e "${KEELWAY_SOURCE_DIR}"
        ;;
    package:*)
        say "[+] Installing ${KEELWAY_PACKAGE} CLI & OpenCore runtime..."
        "${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet "${KEELWAY_PACKAGE}"
        ;;
    git:*)
        GIT_URL="${KEELWAY_GIT_URL}"
        command -v git >/dev/null 2>&1 || die "git is required to install from ${GIT_URL}. Install git or set KEELWAY_SOURCE_DIR/KEELWAY_PACKAGE."
        SRC_DIR="${INSTALL_DIR}/src"
        if [ -n "${KEELWAY_GIT_REF:-}" ]; then
            say "[+] Cloning Keelway source from ${GIT_URL} at ref ${KEELWAY_GIT_REF}..."
            git clone --depth 1 --quiet --branch "$KEELWAY_GIT_REF" "$GIT_URL" "$SRC_DIR" || die "Failed to clone ${GIT_URL} at ref ${KEELWAY_GIT_REF} (tag/branch names only with --depth 1)."
        else
            say "[+] Cloning Keelway source from ${GIT_URL}..."
            git clone --depth 1 --quiet "$GIT_URL" "$SRC_DIR" || die "Failed to clone ${GIT_URL}"
        fi
        say "[+] Installing Keelway from cloned source..."
        "${INSTALL_DIR}/.venv/bin/python" -m pip install --quiet -e "${SRC_DIR}"
        ;;
esac

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
