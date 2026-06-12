#!/usr/bin/env python3
"""Cross-platform launcher for the original ReleaseNotesPoster flow."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
POSTER = ROOT / "Scripts" / "ReleaseNotesPoster.py"


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(command: list[str], quiet: bool = False) -> None:
    stdout = subprocess.DEVNULL if quiet else None
    subprocess.check_call(command, cwd=str(ROOT), stdout=stdout)


def ensure_venv() -> Path:
    python = venv_python()
    if not python.exists():
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
    return python


def dependencies_missing(python: Path) -> bool:
    probe = "import requests; import dotenv"
    result = subprocess.run(
        [str(python), "-c", probe],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode != 0


def install_dependencies(python: Path) -> None:
    if not dependencies_missing(python):
        return

    if REQUIREMENTS.exists():
        run([str(python), "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS)])
    else:
        run([str(python), "-m", "pip", "install", "-q", "requests", "python-dotenv"])


def main() -> int:
    if sys.argv[1:] and sys.argv[1] in {"-h", "--help"}:
        print("Usage: python run_poster.py RELEASE [YYYY-MM-DD]")
        print("Example: python run_poster.py WMS_10.00_2026 2026-06-05")
        return 0

    python = ensure_venv()
    install_dependencies(python)
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    return subprocess.call([str(python), str(POSTER), *sys.argv[1:]], cwd=str(ROOT), env=env)


if __name__ == "__main__":
    raise SystemExit(main())
