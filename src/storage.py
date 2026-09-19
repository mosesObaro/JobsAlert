"""
JobsAlert JSON Storage.
Atomic file writes and a fingerprint-keyed record store shared by the job and
income state managers.
"""

from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional


class StateFileError(RuntimeError):
    """Raised when a state file exists but cannot be parsed.

    The pipeline stops instead of silently starting from empty state, which would
    re-alert every posting ever seen.
    """


def write_text_atomic(path: Path, text: str) -> None:
    """Writes to a temporary sibling file, then atomically replaces the target."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def write_json_atomic(path: Path, data: Any, indent: int = 2) -> None:
    write_text_atomic(path, json.dumps(data, indent=indent, default=str))


def read_json(path: Path, default: Any, strict: bool = False) -> Any:
    """Reads JSON from `path`. Missing files return `default`.

    With strict=True an unreadable file raises StateFileError; otherwise it logs a
    warning and returns `default` (used for logs and caches, which are disposable).
    """
    path = Path(path)
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        if strict:
            raise StateFileError(
                f"Cannot read {path}: {exc}. Fix or remove the file; refusing to continue "
                "with empty state because that would re-send every alert."
            ) from exc
        print(f"[WARNING] Ignoring unreadable file {path}: {exc}")
        return default


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class JsonStateStore:
    """Fingerprint-keyed records persisted as one JSON object.

    Records carry `first_seen_at`, `last_seen_at`, `alerted` and `alerted_at`.
    Legacy records written with `first_seen` / `last_seen` keys are still honoured.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        data = read_json(self.path, {}, strict=True)
        if not isinstance(data, dict):
            raise StateFileError(f"{self.path} must contain a JSON object, found {type(data).__name__}")
        self._records: Dict[str, dict] = data

    # ------------------------------------------------------------------ access
    @property
    def records(self) -> Dict[str, dict]:
        return self._records

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[str]:
        return iter(self._records)

    def get(self, fingerprint: str) -> Optional[dict]:
        return self._records.get(fingerprint)

    def is_seen(self, fingerprint: str) -> bool:
        return fingerprint in self._records

    def is_alerted(self, fingerprint: str) -> bool:
        entry = self._records.get(fingerprint)
        return bool(entry and entry.get("alerted", False))

    # ---------------------------------------------------------------- mutation
    def touch(self, fingerprint: str, now: Optional[datetime] = None) -> None:
        """Marks a record as still present in a source (at most one write per day)."""
        entry = self._records.get(fingerprint)
        if entry is None:
            return
        now = now or utc_now()
        last = str(entry.get("last_seen_at") or entry.get("last_seen") or "")
        if last[:10] != now.date().isoformat():
            entry["last_seen_at"] = now.isoformat()

    def _upsert(self, fingerprint: str, fields: dict, alerted: bool, now: Optional[datetime] = None) -> dict:
        now_iso = (now or utc_now()).isoformat()
        entry = self._records.get(fingerprint)
        if entry is None:
            entry = {"fingerprint": fingerprint, "first_seen_at": now_iso, "alerted": False, "alerted_at": None}
            self._records[fingerprint] = entry
        entry.update(fields)
        entry["last_seen_at"] = now_iso
        if alerted and not entry.get("alerted"):
            entry["alerted"] = True
            entry["alerted_at"] = now_iso
        return entry

    def prune(self, retention_days: int, now: Optional[datetime] = None) -> int:
        """Removes records not seen in any source for `retention_days` days."""
        if retention_days <= 0:
            return 0
        cutoff = (now or utc_now()) - timedelta(days=retention_days)
        stale = []
        for fp, entry in self._records.items():
            seen = parse_timestamp(
                entry.get("last_seen_at") or entry.get("last_seen")
                or entry.get("first_seen_at") or entry.get("first_seen")
            )
            if seen is not None and seen < cutoff:
                stale.append(fp)
        for fp in stale:
            del self._records[fp]
        return len(stale)

    def clear(self, backup: bool = True) -> int:
        """Empties the store; the previous file is kept as a timestamped backup."""
        count = len(self._records)
        if backup and self.path.exists():
            stamp = utc_now().strftime("%Y%m%d%H%M%S")
            os.replace(self.path, self.path.with_name(f"{self.path.name}.{stamp}.bak"))
        self._records = {}
        self.save()
        return count

    def save(self) -> None:
        write_json_atomic(self.path, self._records)
