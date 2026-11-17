#!/bin/sh
# Keelway v1.0.0 Local-First AI Platform Installer (POSIX sh)
# Usage: curl -fsSL https://kora-sable.vercel.app/install.sh | sh
set -eu

say() { printf '%s\n' "$*"; }
die() { printf '[x] %s\n' "$*" >&2; exit 1; }

DRY_RUN=0
UNINSTALL=0
PURGE=0
INSTALL_DIR="${KEELWAY_INSTALL_DIR:-${HOME}/.keelway/runtime}"
BIN_DIR="${KEELWAY_BIN_DIR:-${HOME}/.local/bin}"
DATA_DIR="${KEELWAY_DATA_DIR:-${HOME}/.keelway}"

show_help() {
    cat <<'EOF'
Usage: install.sh [OPTIONS]

Install the Keelway v1.0.0 CLI & OpenCore local-first runtime into an isolated virtualenv.

Options:
  -n, --dry-run       Print resolved installation plan without modifying disk
  --install-dir DIR   Override runtime directory (default: ~/.keelway/runtime)
  --bin-dir DIR       Override binary symlink directory (default: ~/.local/bin)
  --uninstall         Remove the runtime venv, cloned source, and CLI symlink.
                      Preserves ~/.keelway data (projects, vault, audit DBs).
  --purge             With --uninstall: also remove the data directory.
  -h, --help          Show this help message and exit

Environment: KEELWAY_PYTHON, KEELWAY_INSTALL_DIR, KEELWAY_BIN_DIR,
             KEELWAY_DATA_DIR, KEELWAY_SOURCE_DIR, KEELWAY_PACKAGE,
             KEELWAY_GIT_URL, KEELWAY_GIT_REF

Upgrade & rollback:
  Upgrade:  re-run this script (idempotent).
  Rollback: KEELWAY_GIT_REF=<previous-tag-or-branch> sh install.sh
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        -h|--help) show_help; exit 0 ;;
        -n|--dry-run) DRY_RUN=1; shift ;;
        --uninstall) UNINSTALL=1; shift ;;
        --purge) PURGE=1; shift ;;
        --install-dir)
            [ "$#" -ge 2 ] || die "--install-dir requires a directory argument."
            INSTALL_DIR="$2"; shift 2 ;;
        --bin-dir)
            [ "$#" -ge 2 ] || die "--bin-dir requires a directory argument."
            BIN_DIR="$2"; shift 2 ;;
        *) die "Unknown option: $1 (pass --help for usage)." ;;
    esac
done

[ "$PURGE" -eq 0 ] || [ "$UNINSTALL" -eq 1 ] || die "--purge requires --uninstall."

if [ "$UNINSTALL" -eq 1 ]; then
    say "================================================================="
    say "  Keelway v1.0.0 - Uninstall"
    say "================================================================="
    TARGETS="${BIN_DIR}/keelway ${INSTALL_DIR}"
    if [ "$PURGE" -eq 1 ] && [ "$DATA_DIR" != "$INSTALL_DIR" ]; then
        TARGETS="${TARGETS} ${DATA_DIR}"
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        say "[dry-run] Would remove: ${TARGETS}"
        if [ "$PURGE" -eq 0 ]; then
            say "[dry-run] Would preserve data directory: ${DATA_DIR} (use --purge to include)"
        fi
        exit 0
    fi
    rm -f "${BIN_DIR}/keelway"
    rm -rf "${INSTALL_DIR}"
    say "[+] Removed CLI symlink and runtime: ${INSTALL_DIR}"
    if [ "$PURGE" -eq 1 ]; then
        rm -rf "${DATA_DIR}"
        say "[+] Purged data directory: ${DATA_DIR}"
    else
        say "[+] Preserved data directory: ${DATA_DIR} (re-run with --purge to remove)"
    fi
    say "[+] Uninstall complete."
    exit 0
fi

say "================================================================="
say "  Keelway v1.0.0 - Unified Local-First AI Agent Platform"
say "================================================================="
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
say "[+] System detected: ${OS} (${ARCH})"

PYTHON="${KEELWAY_PYTHON:-}"
if [ -z "$PYTHON" ]; then
    for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
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
    RESOLVED_SOURCE="${KEELWAY_SOURCE_DIR} (local checkout)"
elif [ -n "${KEELWAY_PACKAGE:-}" ]; then
    RESOLVED_SOURCE="${KEELWAY_PACKAGE} (package)"
elif [ -n "${KEELWAY_GIT_URL:-}" ]; then
    RESOLVED_SOURCE="${KEELWAY_GIT_URL} (git clone)"
else
    die "No install source configured. Set one of:
    KEELWAY_SOURCE_DIR=/path/to/checkout   (local source tree)
    KEELWAY_PACKAGE=<pip spec>             (published package)
    KEELWAY_GIT_URL=<git url>              (public source mirror)"
fi
if [ "$DRY_RUN" -eq 1 ]; then
    say "[dry-run] Would create isolated venv: ${INSTALL_DIR}/.venv"
    say "[dry-run] Would install package:      ${RESOLVED_SOURCE}"
    say "[dry-run] Would link CLI binary:      ${BIN_DIR}/keelway"
    say "[dry-run] Zero filesystem writes performed."
    exit 0
fi

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
fi

ln -sf "${INSTALL_DIR}/.venv/bin/keelway" "${BIN_DIR}/keelway"
say "[+] Keelway v1.0.0 installed. Run 'keelway init && keelway dev' to launch your workspace."
