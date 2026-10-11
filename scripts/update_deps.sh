#!/usr/bin/env bash
# ==============================================================================
# scripts/update_deps.sh — Unix (Linux & macOS) Auto-Updater Wrapper for J.A.R.V.I.S.
# ==============================================================================
# Ye shell script Linux aur macOS par auto_update.py ko safely execute karta hai.
# Virtual environment (.venv) ko auto-detect karta hai.
#
# Usage:
#     ./scripts/update_deps.sh              (Default Safe Update)
#     ./scripts/update_deps.sh --check      (Check outdated packages)
#     ./scripts/update_deps.sh --dry-run    (Simulation mode)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo "======================================================================"
echo "          * J.A.R.V.I.S. DEPENDENCY AUTO-UPDATER (UNIX) *"
echo "======================================================================"

# Python interpreter auto-detect (.venv prioritized)
PY_EXE=""
if [[ -f "${ROOT_DIR}/.venv/bin/python" ]]; then
    PY_EXE="${ROOT_DIR}/.venv/bin/python"
elif [[ -f "${ROOT_DIR}/venv/bin/python" ]]; then
    PY_EXE="${ROOT_DIR}/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PY_EXE="$(command -v python3)"
elif command -v python &>/dev/null; then
    PY_EXE="$(command -v python)"
else
    echo "[ERROR] Python interpreter nahi mila! Kripya Python3 ya .venv install karein." >&2
    exit 1
fi

echo "[*] Using Python: ${PY_EXE}"
echo "[*] Launching cross-platform updater..."
echo ""

"${PY_EXE}" "${SCRIPT_DIR}/auto_update.py" "$@"
EXIT_CODE=$?

echo ""
if [[ ${EXIT_CODE} -eq 0 ]]; then
    echo "[OK] Update cycle complete ho gaya bina kisi error ke."
else
    echo "[WARNING] Update process exit code: ${EXIT_CODE}"
fi

exit "${EXIT_CODE}"
