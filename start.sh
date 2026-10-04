#!/usr/bin/env bash
set -e

echo "==================================================="
echo "  Personal AI Accountability Coach via Telegram"
echo "==================================================="
echo ""

# 1. Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 2. Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 is not installed or not in PATH!"
    echo "Please install Python 3.11 or higher."
    exit 1
fi

# 3. Check .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "[INFO] .env not found. Creating .env from .env.example..."
        cp .env.example .env
        echo "[WARNING] Please edit .env with your credentials:"
        echo "  - TELEGRAM_BOT_TOKEN"
        echo "  - GEMINI_API_KEY"
        echo "  - ALLOWED_CHAT_ID"
        echo ""
    else
        echo "[ERROR] Neither .env nor .env.example found!"
        exit 1
    fi
fi

# 4. Setup Virtual Environment
if [ ! -d ".venv" ]; then
    echo "[INFO] Creating Python virtual environment in .venv..."
    python3 -m venv .venv
fi

# 5. Activate virtual environment
source .venv/bin/activate

# 6. Install or update dependencies
echo "[INFO] Checking dependencies in requirements.txt..."
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt

# 7. Ensure data directory exists
mkdir -p data

# 8. Launch Bot
echo "[INFO] Starting Personal AI Accountability Coach..."
echo "Press Ctrl+C to stop the bot."
echo ""
export PYTHONPATH="$SCRIPT_DIR:${PYTHONPATH:-}"
exec python src/main.py
