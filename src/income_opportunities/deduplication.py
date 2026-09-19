"""
Online Income Opportunities Deduplication & State Management.
Deterministic fingerprints and a separate seen/alerted/dismissed registry in
data/seen_income_opportunities.json (kept apart from job state).
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Dict, Optional

from src import paths
from src.deduplication import content_key, normalize_string
from src.income_opportunities.models import OnlineIncomeOpportunity
from src.storage import JsonStateStore


def compute_opportunity_fingerprint(
    organization: str,
    title: str,
    category: str = "",
    reference_id: str = "",
    canonical_url: str = ""
) -> str:
    """Deterministic SHA-256 identity of an income opportunity."""
    norm_ref = (reference_id or "").strip().lower()
    if not norm_ref and canonical_url:
        norm_ref = canonical_url.rstrip("/").split("/")[-1].lower()
    seed = f"{normalize_string(organization)}::{normalize_string(title)}::{normalize_string(category)}::{norm_ref}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


class IncomeStateManager(JsonStateStore):
    """Registry of seen, alerted and dismissed income opportunities."""

    def __init__(self, path: Optional[Path | str] = None):
        super().__init__(Path(path) if path else paths.data_file(paths.SEEN_INCOME))
        self._aliases: Optional[Dict[str, str]] = None

    @staticmethod
    def _key(opp: OnlineIncomeOpportunity) -> str:
        # Source is left out: records written before it was stored must still match.
        return content_key("", opp.organization, opp.title, opp.url)

    def _alias_index(self) -> Dict[str, str]:
        if self._aliases is None:
            index: Dict[str, str] = {}
            for fp, entry in self.records.items():
                key = content_key("", entry.get("organization", ""), entry.get("title", ""), entry.get("url", ""))
                if key not in index or (entry.get("alerted") and not self.records[index[key]].get("alerted")):
                    index[key] = fp
            self._aliases = index
        return self._aliases

    def find_equivalent(self, opp: OnlineIncomeOpportunity) -> Optional[str]:
        fp = self._alias_index().get(self._key(opp))
        return fp if fp and fp != opp.fingerprint else None

    def adopt(self, opp: OnlineIncomeOpportunity, existing_fingerprint: str) -> None:
        existing = self.records.get(existing_fingerprint) or {}
        entry = self._upsert(opp.fingerprint, self._fields(opp), alerted=bool(existing.get("alerted")))
        entry["first_seen_at"] = existing.get("first_seen_at") or existing.get("first_seen") or entry["first_seen_at"]
        entry["alerted_at"] = existing.get("alerted_at", entry.get("alerted_at"))
        if existing.get("dismissed"):
            entry["dismissed"] = True

    @staticmethod
    def _fields(opp: OnlineIncomeOpportunity) -> dict:
        return {
            "title": opp.title,
            "organization": opp.organization,
            "category": opp.category,
            "url": opp.url,
            "source": opp.source,
        }

    def is_dismissed(self, fingerprint: str) -> bool:
        entry = self.get(fingerprint)
        return bool(entry and entry.get("dismissed", False))

    def dismiss_opportunity(self, fingerprint: str) -> None:
        """Hides an opportunity from future digests and saves immediately."""
        entry = self._upsert(fingerprint, {}, alerted=False)
        entry["dismissed"] = True
        self.save()

    def record_opportunity(
        self,
        opp: OnlineIncomeOpportunity,
        score: float,
        action: str,
        alerted: bool = False
    ) -> None:
        """Records a processed opportunity; `alerted` never reverts to False."""
        if not opp.fingerprint:
            opp.fingerprint = compute_opportunity_fingerprint(opp.organization, opp.title, opp.category, opp.id, opp.url)
        fields = self._fields(opp)
        fields.update({"score": score, "action": action})
        entry = self._upsert(opp.fingerprint, fields, alerted=alerted)
        entry.setdefault("dismissed", False)
        if self._aliases is not None:
            self._aliases.setdefault(self._key(opp), opp.fingerprint)

    def get_all_records(self) -> Dict[str, Dict]:
        return self.records
