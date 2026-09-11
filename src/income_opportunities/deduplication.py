"""
Online Income Opportunities Deduplication & State Management Layer.
Provides deterministic SHA-256 fingerprinting and separate state persistence
in data/seen_income_opportunities.json to prevent namespace collision with traditional jobs.
"""

from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Set

from src.deduplication import canonicalize_url, normalize_string
from src.income_opportunities.models import OnlineIncomeOpportunity

DEFAULT_INCOME_STATE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "seen_income_opportunities.json"


def compute_opportunity_fingerprint(
    organization: str,
    title: str,
    category: str = "",
    reference_id: str = "",
    canonical_url: str = ""
) -> str:
    """
    Generates a deterministic SHA-256 fingerprint for an online income opportunity.
    Ensures that identical opportunities across aggregators yield the same fingerprint.
    """
    norm_org = normalize_string(organization)
    norm_title = normalize_string(title)
    norm_cat = normalize_string(category)

    norm_ref = reference_id.strip().lower()
    if not norm_ref and canonical_url:
        norm_ref = canonical_url.split("/")[-1].lower()

    seed = f"{norm_org}::{norm_title}::{norm_cat}::{norm_ref}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


class IncomeStateManager:
    """Manages seen and alerted status for online income opportunities."""

    def __init__(
        self,
        state_file: Optional[Path | str] = None,
        filepath: Optional[Path | str] = None,
        state_file_path: Optional[Path | str] = None,
    ):
        target = state_file or filepath or state_file_path or DEFAULT_INCOME_STATE_FILE
        self.state_file = Path(target)
        self._state: Dict[str, Dict] = self._load()

    def _load(self) -> Dict[str, Dict]:
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self) -> None:
        """Atomically persists state to JSON disk storage."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save income state: {e}")

    def is_seen(self, fingerprint: str) -> bool:
        """Returns True if the fingerprint exists in state."""
        return fingerprint in self._state

    def is_alerted(self, fingerprint: str) -> bool:
        """Returns True if the opportunity has already been sent to the user."""
        entry = self._state.get(fingerprint)
        return bool(entry and entry.get("alerted", False))

    def mark_alerted(self, fingerprint: str) -> None:
        """Flags an existing opportunity as alerted to prevent duplicate dispatch."""
        if fingerprint in self._state:
            self._state[fingerprint]["alerted"] = True
            self._state[fingerprint]["alerted_at"] = datetime.now(timezone.utc).isoformat()

    def is_dismissed(self, fingerprint: str) -> bool:
        """Returns True if the user manually dismissed this opportunity."""
        entry = self._state.get(fingerprint)
        return bool(entry and entry.get("dismissed", False))

    def dismiss_opportunity(self, fingerprint: str) -> None:
        """Marks an opportunity as manually dismissed by the user."""
        if fingerprint in self._state:
            self._state[fingerprint]["dismissed"] = True
        else:
            self._state[fingerprint] = {
                "fingerprint": fingerprint,
                "first_seen": datetime.now(timezone.utc).isoformat(),
                "dismissed": True,
            }
        self.save()

    def record_opportunity(
        self,
        opp: OnlineIncomeOpportunity,
        score: float,
        action: str,
        alerted: bool = False
    ) -> None:
        """Records or updates an income opportunity in the state registry."""
        fp = opp.fingerprint or compute_opportunity_fingerprint(
            opp.organization, opp.title, opp.category, opp.id, opp.url
        )
        now_iso = datetime.now(timezone.utc).isoformat()

        if fp not in self._state:
            self._state[fp] = {
                "fingerprint": fp,
                "title": opp.title,
                "organization": opp.organization,
                "category": opp.category,
                "url": opp.url,
                "first_seen": now_iso,
                "last_seen": now_iso,
                "score": score,
                "action": action,
                "alerted": alerted,
                "alerted_at": now_iso if alerted else None,
                "dismissed": False,
            }
        else:
            self._state[fp]["last_seen"] = now_iso
            self._state[fp]["score"] = score
            self._state[fp]["action"] = action
            if alerted and not self._state[fp].get("alerted", False):
                self._state[fp]["alerted"] = True
                self._state[fp]["alerted_at"] = now_iso

    def prune_older_than(self, days: int = 60) -> int:
        """Removes entries that haven't been seen in over `days` days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        to_delete = []

        for fp, meta in self._state.items():
            last_seen_str = meta.get("last_seen", meta.get("first_seen"))
            if last_seen_str:
                try:
                    last_seen_dt = datetime.fromisoformat(last_seen_str)
                    if last_seen_dt < cutoff:
                        to_delete.append(fp)
                except Exception:
                    pass

        for fp in to_delete:
            del self._state[fp]

        if to_delete:
            self.save()
        return len(to_delete)

    def get_all_records(self) -> Dict[str, Dict]:
        return self._state

    def clear(self) -> None:
        self._state = {}
        self.save()
