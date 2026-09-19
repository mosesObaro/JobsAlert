"""
Custom / Manual Job Collector.
One-off jobs entered by hand (LinkedIn, referrals, Twitter/X, cold emails) in
data/custom_jobs.json, scored and alerted like any other source.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from src import paths
from src.collectors.base import BaseCollector, optional_float
from src.config import AppConfig
from src.deduplication import stable_hash
from src.models import JobPosting
from src.storage import read_json, write_json_atomic


def custom_jobs_file():
    return paths.data_file(paths.CUSTOM_JOBS)


def load_custom_jobs() -> List[dict]:
    items = read_json(custom_jobs_file(), [])
    return items if isinstance(items, list) else []


def custom_job_id(entry: dict) -> str:
    """Stable id: the one stored at creation, else derived from the entry's content."""
    return str(entry.get("id") or stable_hash(entry.get("url"), entry.get("company"), entry.get("title")))


class CustomJobCollector(BaseCollector):
    """Loads manually entered jobs from data/custom_jobs.json."""

    expects_results = False  # an empty custom list is normal

    def __init__(self):
        super().__init__(name="custom")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        all_jobs: List[JobPosting] = []
        for position, item in enumerate(load_custom_jobs()):
            try:
                all_jobs.append(self._to_posting(item))
            except Exception as exc:  # one malformed entry must not hide the others
                self.note(f"custom entry #{position + 1}: {type(exc).__name__}: {exc}")
        return all_jobs

    @staticmethod
    def _to_posting(item: dict) -> JobPosting:
        title = (item.get("title") or "").strip()
        company = (item.get("company") or "Custom Employer").strip()
        if not title:
            raise ValueError("missing title")
        location = item.get("location") or "Remote"
        is_remote = bool(item.get("is_remote", True) or "remote" in location.lower())
        job_url = (item.get("url") or "").strip()
        return JobPosting(
            id=f"custom_{custom_job_id(item)}",
            title=title,
            company=company,
            location=location,
            is_remote=is_remote,
            remote_scope="Worldwide" if "worldwide" in location.lower() else ("Remote" if is_remote else "On-Site"),
            url=job_url,
            raw_url=job_url,
            description=(item.get("description") or "")[:3000],
            salary_min=optional_float(item.get("salary_min")),
            salary_max=optional_float(item.get("salary_max")),
            salary_currency=(item.get("salary_currency") or "USD").upper(),
            salary_period=item.get("salary_period") or "yearly",
            source="custom",
            posted_at=datetime.now(timezone.utc),
            tags=["Manual / Referral", company],
        )


def add_custom_job(
    title: str,
    company: str,
    location: str = "Remote",
    url: str = "",
    description: str = "",
    salary_min: Optional[float] = None,
    salary_max: Optional[float] = None,
    salary_currency: str = "USD",
    salary_period: str = "yearly",
) -> dict:
    """Adds a custom job to data/custom_jobs.json (newest first) and returns the stored entry."""
    jobs = load_custom_jobs()
    new_entry: dict[str, Any] = {
        "id": uuid.uuid4().hex[:16],
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "description": description,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_currency": (salary_currency or "USD").upper(),
        "salary_period": salary_period or "yearly",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    jobs.insert(0, new_entry)
    write_json_atomic(custom_jobs_file(), jobs)
    return new_entry


def delete_custom_job(entry_id: str) -> Optional[dict]:
    """Removes the custom job with this id; returns it, or None when not found."""
    jobs = load_custom_jobs()
    for position, entry in enumerate(jobs):
        if custom_job_id(entry) == entry_id:
            removed = jobs.pop(position)
            write_json_atomic(custom_jobs_file(), jobs)
            return removed
    return None
