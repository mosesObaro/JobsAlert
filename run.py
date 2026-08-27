#!/usr/bin/env python3
"""
JobsAlert Root Runner Script.
Usage:
  python run.py --dry-run
  python run.py --send-email
  python run.py --server
"""

import sys
from src.main import main

if __name__ == "__main__":
    main()
