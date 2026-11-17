#!/usr/bin/env bash
# Keelway Sovereign AI Platform — Zero-Friction Installer
set -euo pipefail

EXIT_USAGE=2
EXIT_PYTHON=3
EXIT_INSTALL=4

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." 2>/dev/null && pwd || pwd)"

DRY_RUN=0
JSON_MODE=0
UNINSTALL=0
PURGE=0
PREFIX="${KEELWAY_PREFIX:-${HOME}/.local}"
VENV_DIR="${KEELWAY_VENV:-${HOME}/.keelway/venv}"
DATA_DIR="${KEELWAY_DATA_DIR:-${HOME}/.keelway}"

print_help() {
    cat <<'EOF'
Usage: install.sh [OPTIONS]

Install the Keelway Sovereign AI Platform into an isolated Python >= 3.11
virtual environment and expose `keelway` on your binary prefix.

Options:
  --prefix <DIR>   Installation prefix; links binary to <DIR>/bin/keelway (default: ~/.local)
  --venv <DIR>     Target virtual environment path (default: ~/.keelway/venv)
  --dry-run        Print exact execution plan with zero filesystem writes or network calls
  --json           Emit deterministic machine-readable JSON to stdout
  --uninstall      Remove the venv and the linked binary. Preserves the data
                   directory (~/.keelway) — projects, vault, audit DBs.
  --purge          With --uninstall: also remove the data directory.
  -h, --help       Show this help text and exit 0

Exit Codes:
  0  Success (or --help / --dry-run completed)
  2  Invalid CLI flag or missing argument
  3  Python >= 3.11 runtime not found
  4  Virtualenv or package installation failure

Examples:
  ./scripts/install.sh --dry-run
  ./scripts/install.sh --dry-run --json
  ./scripts/install.sh --prefix "$HOME/.local" --venv "$HOME/.keelway/venv"
EOF
}

emit_error() {
    local code="$1" msg="$2"
    if [[ "$JSON_MODE" -eq 1 ]]; then
        printf '{"ok":false,"exit_code":%d,"error":"%s"}\n' "$code" "${msg//\"/\\\"}"
    else
        printf '[x] Error: %s\n' "$msg" >&2
    fi
    exit "$code"
}

for _arg in "$@"; do [[ "$_arg" == "--json" ]] && JSON_MODE=1; done
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) print_help; exit 0 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --json) JSON_MODE=1; shift ;;
        --uninstall) UNINSTALL=1; shift ;;
        --purge) PURGE=1; shift ;;
        --prefix)
            [[ $# -ge 2 && -n "${2:-}" ]] || emit_error "$EXIT_USAGE" "--prefix requires a directory argument"
            PREFIX="$2"; shift 2 ;;
        --venv)
            [[ $# -ge 2 && -n "${2:-}" ]] || emit_error "$EXIT_USAGE" "--venv requires a directory argument"
            VENV_DIR="$2"; shift 2 ;;
        *)
            emit_error "$EXIT_USAGE" "Unknown option: $1 (pass --help for usage)" ;;
    esac
done

PYTHON_BIN="${KEELWAY_PYTHON:-}"
if [[ -n "$PYTHON_BIN" ]]; then
    command -v "$PYTHON_BIN" >/dev/null 2>&1 || [[ -x "$PYTHON_BIN" ]] || emit_error "$EXIT_PYTHON" "KEELWAY_PYTHON not executable: $PYTHON_BIN"
    "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null || emit_error "$EXIT_PYTHON" "Python >= 3.11 required: $PYTHON_BIN"
else
    for candidate in python3.13 python3.12 python3.11 python3; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
            PYTHON_BIN="$(command -v "$candidate")"
            break
        fi
    done
fi
[[ -n "$PYTHON_BIN" ]] || emit_error "$EXIT_PYTHON" "Python >= 3.11 is required. Install Python 3.11+ or set KEELWAY_PYTHON."

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
BIN_DIR="${PREFIX%/}/bin"
TARGET_BIN="${BIN_DIR}/keelway"

[[ "$PURGE" -eq 0 || "$UNINSTALL" -eq 1 ]] || emit_error "$EXIT_USAGE" "--purge requires --uninstall"
if [[ "$UNINSTALL" -eq 1 ]]; then
    TARGETS=("$TARGET_BIN" "$VENV_DIR")
    if [[ "$PURGE" -eq 1 && "$DATA_DIR" != "$VENV_DIR" ]]; then
        TARGETS+=("$DATA_DIR")
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
        if [[ "$JSON_MODE" -eq 1 ]]; then
            printf '{"ok":true,"status":"planned","dry_run":true,"action":"uninstall","removes":["%s"],"preserves":"%s"}\n' \
                "${TARGETS[*]// /\",\"}" "$([[ "$PURGE" -eq 1 ]] && echo "" || echo "$DATA_DIR")"
        else
            printf '[dry-run] Would remove: %s\n' "${TARGETS[*]}"
            [[ "$PURGE" -eq 0 ]] && printf '[dry-run] Would preserve data directory: %s (use --purge to include)\n' "$DATA_DIR"
        fi
        exit 0
    fi
    rm -f "$TARGET_BIN"
    rm -rf "$VENV_DIR"
    if [[ "$PURGE" -eq 1 ]]; then
        rm -rf "$DATA_DIR"
        PRESERVED=""
    else
        PRESERVED="$DATA_DIR"
    fi
    if [[ "$JSON_MODE" -eq 1 ]]; then
        printf '{"ok":true,"status":"uninstalled","removed_venv":"%s","removed_binary":"%s","preserved_data_dir":"%s"}\n' \
            "$VENV_DIR" "$TARGET_BIN" "$PRESERVED"
    else
        printf '[+] Removed %s and %s\n' "$TARGET_BIN" "$VENV_DIR"
        [[ "$PURGE" -eq 1 ]] \
            && printf '[+] Purged data directory: %s\n' "$DATA_DIR" \
            || printf '[+] Preserved data directory: %s (re-run with --purge to remove)\n' "$DATA_DIR"
    fi
    exit 0
fi
if [[ -n "${KEELWAY_PACKAGE:-}" ]]; then
    PACKAGE_SOURCE="$KEELWAY_PACKAGE"
elif [[ -f "${REPO_ROOT}/pyproject.toml" ]]; then
    PACKAGE_SOURCE="$REPO_ROOT"
else
    PACKAGE_SOURCE="keelway"
fi

emit_json() {
    "$PYTHON_BIN" - "$1" "$DRY_RUN" "$PYTHON_BIN" "$PYTHON_VERSION" "$VENV_DIR" "$PREFIX" "$BIN_DIR" "$TARGET_BIN" "$PACKAGE_SOURCE" <<'PY'
import json, sys
status, dry_run, py_bin, py_ver, venv_dir, prefix, bin_dir, target_bin, pkg_src = sys.argv[1:10]
print(json.dumps({
    "ok": True, "status": status, "dry_run": dry_run == "1",
    "python_executable": py_bin, "python_version": py_ver,
    "venv_dir": venv_dir, "prefix": prefix, "bin_dir": bin_dir,
    "binary_path": target_bin, "package_source": pkg_src,
    "steps": [
        f"{py_bin} -m venv {venv_dir}",
        f"{venv_dir}/bin/python -m pip install --upgrade pip",
        f"{venv_dir}/bin/python -m pip install {pkg_src}",
        f"ln -sf {venv_dir}/bin/keelway {target_bin}",
    ],
    "quickstart": ["keelway doctor", "keelway dev"],
}))
PY
}

if [[ "$DRY_RUN" -eq 1 ]]; then
    if [[ "$JSON_MODE" -eq 1 ]]; then
        emit_json "planned"
    else
        printf '[dry-run] Keelway installation plan (zero writes, zero network calls):\n'
        printf '  python  : %s (%s)\n  venv    : %s\n  binary  : %s\n  source  : %s\n' "$PYTHON_BIN" "$PYTHON_VERSION" "$VENV_DIR" "$TARGET_BIN" "$PACKAGE_SOURCE"
        printf '  next    : keelway doctor && keelway dev\n'
    fi
    exit 0
fi

mkdir -p "$BIN_DIR" "$(dirname "$VENV_DIR")" || emit_error "$EXIT_INSTALL" "Failed to create installation directories"
"$PYTHON_BIN" -m venv "$VENV_DIR" || emit_error "$EXIT_INSTALL" "Failed to create virtual environment at $VENV_DIR"
"${VENV_DIR}/bin/python" -m pip install --quiet --upgrade pip || emit_error "$EXIT_INSTALL" "Failed to upgrade pip in $VENV_DIR"
"${VENV_DIR}/bin/python" -m pip install --quiet "$PACKAGE_SOURCE" || emit_error "$EXIT_INSTALL" "Failed to install $PACKAGE_SOURCE"
ln -sf "${VENV_DIR}/bin/keelway" "$TARGET_BIN"

if [[ "$JSON_MODE" -eq 1 ]]; then
    emit_json "installed"
else
    printf '[+] Installed Keelway into %s -> %s\n' "$VENV_DIR" "$TARGET_BIN"
    printf '[+] Quickstart: run `keelway doctor` then `keelway dev` to launch Studio & /app.\n'
fi
