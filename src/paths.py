"""
JobsAlert filesystem locations.

Paths are resolved on every call (not at import time) so tests and CI can redirect
them with environment variables:

- JOBSALERT_DATA_DIR       runtime state, logs, caches and custom entries (default: ./data)
- JOBSALERT_CONFIG         active configuration file (default: ./config/jobs.yaml)
- JOBSALERT_PROFILES_DIR   saved profile presets (default: ./config/profiles)
- JOBSALERT_INCOME_CATALOG curated income platform catalogue (default: ./config/income_catalog.yaml)
"""

from __future__ import annotations
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# File names inside data_dir()
SEEN_JOBS = "seen_jobs.json"
SEEN_INCOME = "seen_income_opportunities.json"
RUN_LOGS = "run_logs.json"
INCOME_RUN_LOGS = "income_run_logs.json"
LINK_CACHE = "verified_links_cache.json"
EMAIL_PREVIEW = "latest_email_preview.html"
CUSTOM_JOBS = "custom_jobs.json"
CUSTOM_INCOME = "custom_income_opportunities.json"
LAST_RESULTS = "last_run_results.json"


def data_dir() -> Path:
    return Path(os.getenv("JOBSALERT_DATA_DIR") or PROJECT_ROOT / "data")


def data_file(name: str) -> Path:
    return data_dir() / name


def config_path() -> Path:
    return Path(os.getenv("JOBSALERT_CONFIG") or PROJECT_ROOT / "config" / "jobs.yaml")


def profiles_dir() -> Path:
    return Path(os.getenv("JOBSALERT_PROFILES_DIR") or PROJECT_ROOT / "config" / "profiles")


def income_catalog_path() -> Path:
    return Path(os.getenv("JOBSALERT_INCOME_CATALOG") or PROJECT_ROOT / "config" / "income_catalog.yaml")


def web_dist_dir() -> Path:
    return PROJECT_ROOT / "web" / "dist"
