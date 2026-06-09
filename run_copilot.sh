#!/usr/bin/env bash
set -euo pipefail

PY=python3
VENV_DIR=".venv"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$ROOT_DIR"

if [ ! -d "$VENV_DIR" ]; then
  $PY -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
. "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip >/dev/null
pip install -q -r requirements.txt

python Scripts/ReleaseNotesCopilot.py "$@"
