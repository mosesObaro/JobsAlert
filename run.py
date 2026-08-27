#!/usr/bin/env python3
"""
JobsAlert Root Runner Script.
Automatically detects and uses the local .venv virtual environment if not already active.
Usage:
  python run.py --dry-run
  python run.py --send-email
  python run.py --server
"""

import os
import sys
from pathlib import Path

# Auto-activate local .venv if running from system/base python without dependencies
VENV_DIR = Path(__file__).resolve().parent / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"
if VENV_PYTHON.exists() and sys.executable != str(VENV_PYTHON):
    try:
        import uvicorn
        import fastapi
        import pydantic
    except ImportError:
        os.environ["VIRTUAL_ENV"] = str(VENV_DIR)
        os.environ["PATH"] = f"{VENV_DIR / 'bin'}:{os.environ.get('PATH', '')}"
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

from src.main import main

if __name__ == "__main__":
    main()
