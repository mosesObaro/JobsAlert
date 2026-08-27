"""
Custom / Manual Job Collector.
Allows candidates to enter one-off jobs (from LinkedIn, referrals, Twitter/X, cold emails)
to be deduplicated, scored, and included in email alerts and the web dashboard.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting

CUSTOM_JOBS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "custom_jobs.json"


class CustomJobCollector(BaseCollector):
    """Loads manually entered jobs from data/custom_jobs.json."""

    def __init__(self):
        super().__init__(name="custom")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        all_jobs: List[JobPosting] = []

        if not CUSTOM_JOBS_FILE.exists():
            return []

        try:
            with open(CUSTOM_JOBS_FILE, "r", encoding="utf-8") as f:
                raw_items = json.load(f)

            if not isinstance(raw_items, list):
                return []

            for idx, item in enumerate(raw_items):
                title = item.get("title", "").strip()
                company = item.get("company", "Custom Employer").strip()
                location = item.get("location", "Remote")
                is_remote = bool(item.get("is_remote", True) or "remote" in location.lower())
                job_url = item.get("url", f"https://example.com/custom-job-{idx}")
                desc = item.get("description", "")
                s_min = float(item.get("salary_min", 0)) or None
                s_max = float(item.get("salary_max", 0)) or None

                posting = JobPosting(
                    id=f"custom_{idx}_{abs(hash(job_url or title))}",
                    title=title,
                    company=company,
                    location=location,
                    is_remote=is_remote,
                    remote_scope="Worldwide" if "worldwide" in location.lower() else ("Remote" if is_remote else "On-Site"),
                    url=job_url,
                    raw_url=job_url,
                    description=desc[:3000],
                    salary_min=s_min,
                    salary_max=s_max,
                    source="custom",
                    posted_at=datetime.now(timezone.utc),
                    tags=["Manual / Referral", company]
                )
                all_jobs.append(posting)
        except Exception as e:
            self.health.error_message = str(e)

        return all_jobs


def add_custom_job(
    title: str,
    company: str,
    location: str = "Remote",
    url: str = "",
    description: str = "",
    salary_min: float | None = None,
    salary_max: float | None = None,
) -> dict:
    """Helper to append a custom job to data/custom_jobs.json."""
    CUSTOM_JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    jobs = []
    if CUSTOM_JOBS_FILE.exists():
        try:
            with open(CUSTOM_JOBS_FILE, "r", encoding="utf-8") as f:
                jobs = json.load(f)
        except Exception:
            jobs = []

    new_entry = {
        "title": title,
        "company": company,
        "location": location,
        "url": url or f"https://example.com/jobs/{company.lower()}-{abs(hash(title))}",
        "description": description,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    jobs.insert(0, new_entry)

    with open(CUSTOM_JOBS_FILE, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)

    return new_entry
