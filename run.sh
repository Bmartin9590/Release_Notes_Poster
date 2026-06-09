#!/usr/bin/env bash
set -euo pipefail

# --- Config ---
PY=python3
VENV_DIR=".venv"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT_DIR"

# --- Bootstrap venv if missing ---
if [ ! -d "$VENV_DIR" ]; then
  $PY -m venv "$VENV_DIR"
fi

# --- Activate venv ---
# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"

# --- Install/upgrade deps ---
python -m pip install --upgrade pip >/dev/null
if [ -f "requirements.txt" ]; then
  pip install -q -r requirements.txt
else
  pip install -q requests python-dotenv
fi

# --- Run your program ---
python Scripts/ReleaseNotesPoster.py "$@"
