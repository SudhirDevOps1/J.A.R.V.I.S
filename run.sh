#!/usr/bin/env bash
# ==============================================================================
# J.A.R.V.I.S. Autonomous Assistant Launcher for Linux and macOS
# 1-Click Execution: Verifies Python, auto-installs requirements, and starts J.A.R.V.I.S.
# ==============================================================================

set -e
cd "$(dirname "$0")"

echo "======================================================================"
echo "         * SUDHIRDEVOPS1 AI ASSISTANT (J.A.R.V.I.S. MARK LIII) *"
echo "======================================================================"
echo ""

# 1. Check Python3 Availability
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 not found! Please install Python 3.10+."
    exit 1
fi

# 2. Check / Activate Virtual Environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# 3. Check and Auto-Install Dependencies on First Run
echo "[*] Checking libraries & system dependencies..."
if ! python3 -c "import google.genai, requests, sounddevice, edge_tts, PIL, psutil, tinydb, rank_bm25, thefuzz, sklearn" &> /dev/null; then
    echo "[*] First-run setup: Installing missing dependencies from requirements.txt..."
    python3 -m pip install -r requirements.txt || echo "[!] Warning: Some packages had installation warnings."
    echo "[OK] Dependencies ready!"
    echo ""
fi

# 4. Run Preflight Check (downloads Piper models, SFX, config verification)
echo "[*] Running automated pre-flight checks..."
python3 scripts/preflight_check.py

# 5. Launch Assistant
echo "[*] Starting J.A.R.V.I.S. neural interface..."
echo ""
python3 main.py
