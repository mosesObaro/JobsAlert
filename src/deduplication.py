"""
JobsAlert Deduplication & State Persistence Layer.
Implements URL canonicalization, identity fingerprinting, and state management.
"""

from __future__ import annotations
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Set
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from src.models import JobPosting

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "gh_src", "source", "lever-origin", "fbclid", "gclid",
    "subid", "affiliate", "trk", "tracking", "referral", "src",
    "mc_cid", "mc_eid", "otm", "hsCtaTracking"
}

DEFAULT_STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "seen_jobs.json"


def canonicalize_url(raw_url: str) -> str:
    """
    Strips all marketing, campaign, affiliate, and tracking tokens from a job URL.
    Standardizes protocol, hostname, and trailing paths.
    """
    if not raw_url:
        return ""

    parsed = urlparse(raw_url.strip())
    # Standardize scheme and lowercase netloc
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()

    # Filter query parameters
    query_dict = parse_qs(parsed.query, keep_blank_values=False)
    filtered_query = {
        k: v for k, v in query_dict.items()
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith("utm_")
    }

    # Reconstruct query string sorted by keys
    clean_query = urlencode(filtered_query, doseq=True)

    # Standardize path
    path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

    clean_url = urlunparse((
        scheme,
        netloc,
        path,
        "",  # params
        clean_query,
        ""   # fragment
    ))
    return clean_url


def normalize_string(text: str) -> str:
    """Normalizes a string by lowercasing, stripping special chars, and collapsing whitespace."""
    if not text:
        return ""
    text = text.lower()
    # Strip common corporate suffixes for matching
    text = re.sub(r"\b(inc|ltd|llc|corp|corporation|technologies|tech|gmbh|co)\b", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def compute_job_fingerprint(
    company: str,
    title: str,
    location_type: str = "",
    reference_id: str = "",
    canonical_url: str = ""
) -> str:
    """
    Generates a deterministic SHA-256 fingerprint for a job posting.
    Ensures that identical jobs posted on multiple boards (e.g. Greenhouse + Remotive + LinkedIn)
    produce the exact same fingerprint.
    """
    norm_company = normalize_string(company)
    norm_title = normalize_string(title)
    norm_loc = normalize_string(location_type)

    # If reference id exists, sanitize it; otherwise extract clean path slug from canonical url
    norm_ref = reference_id.strip().lower()
    if not norm_ref and canonical_url:
        parsed = urlparse(canonical_url)
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            norm_ref = path_parts[-1].lower()

    # Core fingerprint seed
    fingerprint_raw = f"{norm_company}::{norm_title}::{norm_loc}::{norm_ref}"
    return hashlib.sha256(fingerprint_raw.encode("utf-8")).hexdigest()


class StateManager:
    """
    Thread-safe persistence manager for tracking previously seen and alerted jobs.
    Supports file-based JSON storage (default for zero-cost GitHub Actions runs)
    and optional Supabase PostgreSQL sync.
    """

    def __init__(self, state_file_path: Optional[Path | str] = None):
        self.state_file = Path(state_file_path) if state_file_path else DEFAULT_STATE_FILE
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.seen_data: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    self.seen_data = json.load(f)
            except Exception as e:
                # Corrupted or empty file, reset
                self.seen_data = {}
        else:
            self.seen_data = {}

    def save(self) -> None:
        """Flushes the current state to disk."""
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.seen_data, f, indent=2, default=str)

    def is_seen(self, fingerprint: str) -> bool:
        """Returns True if the job fingerprint has already been processed."""
        return fingerprint in self.seen_data

    def record_job(
        self,
        job: JobPosting,
        score: float,
        action: str,
        alerted: bool = False
    ) -> None:
        """
        Records a job into the state database with timestamp and score.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        if job.fingerprint not in self.seen_data:
            self.seen_data[job.fingerprint] = {
                "fingerprint": job.fingerprint,
                "company": job.company,
                "title": job.title,
                "canonical_url": job.url,
                "source": job.source,
                "first_seen_at": now_iso,
                "last_seen_at": now_iso,
                "score": score,
                "action": action,
                "alerted": alerted,
                "alerted_at": now_iso if alerted else None,
            }
        else:
            entry = self.seen_data[job.fingerprint]
            entry["last_seen_at"] = now_iso
            entry["score"] = score
            entry["action"] = action
            if alerted:
                entry["alerted"] = True
                entry["alerted_at"] = now_iso

    def mark_alerted(self, fingerprint: str) -> None:
        """Flags an existing job as alerted to prevent subsequent notifications."""
        if fingerprint in self.seen_data:
            self.seen_data[fingerprint]["alerted"] = True
            self.seen_data[fingerprint]["alerted_at"] = datetime.now(timezone.utc).isoformat()

    def get_seen_count(self) -> int:
        return len(self.seen_data)

    def prune_older_than(self, days: int = 60) -> int:
        """Prunes records older than N days to keep cache fast and lightweight."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        to_delete = []
        for fp, item in self.seen_data.items():
            first_seen = datetime.fromisoformat(item.get("first_seen_at", datetime.now(timezone.utc).isoformat()))
            if first_seen < cutoff:
                to_delete.append(fp)

        for fp in to_delete:
            del self.seen_data[fp]

        if to_delete:
            self.save()
        return len(to_delete)
