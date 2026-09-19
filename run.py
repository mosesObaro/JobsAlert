#!/usr/bin/env python3
"""
JobsAlert Root Runner Script.
Automatically detects and uses the local .venv virtual environment if not already active.
Usage:
  python run.py --dry-run
  python run.py --send-email
  python run.py --server
Exit codes: 0 success, 1 undelivered alerts (retried next run), 2 unreadable config or state.
"""

import importlib.util
import os
import sys
from pathlib import Path

# Re-launch inside the local .venv when the current interpreter lacks the dependencies.
VENV_DIR = Path(__file__).resolve().parent / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"
if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
    if not all(importlib.util.find_spec(name) for name in ("uvicorn", "fastapi", "pydantic")):
        os.environ["VIRTUAL_ENV"] = str(VENV_DIR)
        os.environ["PATH"] = f"{VENV_DIR / 'bin'}:{os.environ.get('PATH', '')}"
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

from src.main import main

if __name__ == "__main__":
    sys.exit(main())
