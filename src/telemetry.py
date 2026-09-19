"""
JobsAlert Run Telemetry.
Append-only, size-capped run logs shared by the job and income pipelines.
"""

from __future__ import annotations
from pathlib import Path
from typing import List

from src.storage import read_json, write_json_atomic

MAX_LOG_ENTRIES = 50


def append_run_log(path: Path, entry: dict, keep: int = MAX_LOG_ENTRIES) -> None:
    logs = read_json(path, [])
    if not isinstance(logs, list):
        logs = []
    logs.insert(0, entry)
    write_json_atomic(path, logs[:keep])


def read_run_logs(path: Path) -> List[dict]:
    logs = read_json(path, [])
    return logs if isinstance(logs, list) else []
