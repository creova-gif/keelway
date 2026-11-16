#!/bin/sh
# KEEL-REL-049 — Clean-environment install verification.
# Builds a fresh venv, editable-installs the repo, runs `keelway doctor --json`,
# and asserts overall_status == HEALTHY. Exits non-zero on any failure.
# Usage: ./scripts/verify_install.sh [--keep]

set -eu

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
WORK_DIR="$(mktemp -d /tmp/keelway-install-verify.XXXXXX)"
KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

cleanup() {
    if [ "$KEEP" -eq 0 ]; then rm -rf "$WORK_DIR"; fi
}
trap cleanup EXIT

PYTHON="${KEELWAY_PYTHON:-python3}"
"$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
    || { echo "[x] Python 3.11+ required"; exit 1; }

echo "[+] venv: $WORK_DIR/venv"
"$PYTHON" -m venv "$WORK_DIR/venv"
VENV_PY="$WORK_DIR/venv/bin/python"
"$VENV_PY" -m pip install --quiet --upgrade pip

echo "[+] editable install from $REPO_ROOT"
"$VENV_PY" -m pip install --quiet -e "$REPO_ROOT"

echo "[+] keelway doctor --json"
"$WORK_DIR/venv/bin/keelway" doctor --json > "$WORK_DIR/doctor.json"
STATUS="$("$VENV_PY" -c 'import json,sys; print(json.load(open(sys.argv[1]))["overall_status"])' "$WORK_DIR/doctor.json")"
echo "[+] doctor overall_status: $STATUS"
[ "$STATUS" = "HEALTHY" ] || { echo "[x] doctor not HEALTHY"; cat "$WORK_DIR/doctor.json"; exit 1; }

echo "[+] smoke: keelway harness agents detect"
"$WORK_DIR/venv/bin/keelway" harness agents detect --json > "$WORK_DIR/agents.json"
"$VENV_PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); assert len(d["agents"])>=2' "$WORK_DIR/agents.json"

echo "[OK] clean install verified: venv -> editable install -> doctor HEALTHY -> agents detect"
