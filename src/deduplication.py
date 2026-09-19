"""
JobsAlert Deduplication & State Persistence Layer.
URL canonicalization, identity fingerprinting and the seen/alerted job registry.
"""

from __future__ import annotations
import hashlib
import re
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from src import paths
from src.models import JobPosting
from src.storage import JsonStateStore

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "gh_src", "source", "lever-origin", "fbclid", "gclid",
    "subid", "affiliate", "trk", "tracking", "referral", "src",
    "mc_cid", "mc_eid", "otm", "hsctatracking",
}


def canonicalize_url(raw_url: str) -> str:
    """
    Strips marketing, campaign, affiliate and tracking parameters from a job URL,
    lowercases scheme and host, sorts the remaining query parameters and drops fragments.
    """
    if not raw_url:
        return ""

    parsed = urlparse(raw_url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()

    query = sorted(
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=False)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    )
    path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
    return urlunparse((scheme, netloc, path, "", urlencode(query, doseq=True), ""))


def normalize_string(text: str) -> str:
    """Lowercases, strips common corporate suffixes and punctuation, and collapses whitespace."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\b(inc|ltd|llc|corp|corporation|technologies|tech|gmbh|co)\b", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def stable_hash(*parts: object, length: int = 16) -> str:
    """Deterministic short hash (unlike built-in hash(), which is salted per process)."""
    raw = "\x1f".join("" if p is None else str(p).strip().lower() for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length]


def compute_job_fingerprint(
    company: str,
    title: str,
    location_type: str = "",
    reference_id: str = "",
    canonical_url: str = ""
) -> str:
    """
    Deterministic SHA-256 identity of a posting from company, title, location scope
    and the source's reference id (or the last URL path segment when there is none).
    Reference ids are source-specific, so the same role cross-posted on two boards
    produces two fingerprints.
    """
    norm_ref = (reference_id or "").strip().lower()
    if not norm_ref and canonical_url:
        path_parts = [p for p in urlparse(canonical_url).path.split("/") if p]
        if path_parts:
            norm_ref = path_parts[-1].lower()

    seed = f"{normalize_string(company)}::{normalize_string(title)}::{normalize_string(location_type)}::{norm_ref}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def content_key(source: str, company: str, title: str, url: str) -> str:
    """Identity of a posting independent of its fingerprint (used to recognise legacy records)."""
    return f"{(source or '').lower()}|{normalize_string(company)}|{normalize_string(title)}|{canonicalize_url(url or '')}"


class StateManager(JsonStateStore):
    """Registry of previously seen and alerted job fingerprints (data/seen_jobs.json)."""

    def __init__(self, path: Optional[Path | str] = None):
        super().__init__(Path(path) if path else paths.data_file(paths.SEEN_JOBS))
        self._aliases: Optional[Dict[str, str]] = None

    def _alias_index(self) -> Dict[str, str]:
        if self._aliases is None:
            index: Dict[str, str] = {}
            for fp, entry in self.records.items():
                key = content_key(entry.get("source", ""), entry.get("company", ""), entry.get("title", ""), entry.get("canonical_url", ""))
                # Prefer an alerted record so an earlier delivery is never forgotten.
                if key not in index or (entry.get("alerted") and not self.records[index[key]].get("alerted")):
                    index[key] = fp
            self._aliases = index
        return self._aliases

    def find_equivalent(self, job: JobPosting) -> Optional[str]:
        """Fingerprint of an existing record for the same posting under a different fingerprint."""
        fp = self._alias_index().get(content_key(job.source, job.company, job.title, job.url))
        return fp if fp and fp != job.fingerprint else None

    def adopt(self, job: JobPosting, existing_fingerprint: str) -> None:
        """Re-keys knowledge about a posting under its current fingerprint (keeps alerted state)."""
        existing = self.records.get(existing_fingerprint) or {}
        entry = self._upsert(job.fingerprint, self._fields(job), alerted=bool(existing.get("alerted")))
        entry["first_seen_at"] = existing.get("first_seen_at", entry["first_seen_at"])
        entry["alerted_at"] = existing.get("alerted_at", entry.get("alerted_at"))
        for key in ("score", "action", "spec"):
            if key in existing:
                entry[key] = existing[key]

    @staticmethod
    def _fields(job: JobPosting) -> dict:
        return {
            "company": job.company,
            "title": job.title,
            "canonical_url": job.url,
            "source": job.source,
        }

    def record_job(
        self,
        job: JobPosting,
        score: float,
        action: str,
        alerted: bool = False,
        spec: Optional[str] = None,
    ) -> None:
        """Records a processed job with its best score; `alerted` never reverts to False."""
        fields = self._fields(job)
        fields.update({"score": score, "action": action})
        if spec:
            fields["spec"] = spec
        self._upsert(job.fingerprint, fields, alerted=alerted)
        if self._aliases is not None:
            self._aliases.setdefault(content_key(job.source, job.company, job.title, job.url), job.fingerprint)

    def get_seen_count(self) -> int:
        return len(self)
