"""
Remotive Remote Jobs API Collector.
Fetches curated remote listings from remotive.com.
"""

from __future__ import annotations
from typing import List, Optional, Tuple

from src.collectors.base import BaseCollector, parse_iso_datetime
from src.config import AppConfig
from src.feeds import strip_html
from src.models import JobPosting
from src.money import parse_salary_text


def parse_salary_string(salary_str: str) -> Tuple[Optional[float], Optional[float]]:
    """Parses '$120k - $160k' or '110,000 - 140,000 USD' into (min, max)."""
    info = parse_salary_text(salary_str)
    return info.min, info.max


class RemotiveCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="remotive")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.remotive.enabled

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.remotive.enabled:
            return []
        categories = config.sources.remotive.categories or ["software-dev", "hr", "data"]
        all_jobs: List[JobPosting] = []
        seen_job_ids = set()

        async with self.create_http_client(timeout=12.0) as client:
            for category in categories:
                try:
                    resp = await client.get("https://remotive.com/api/remote-jobs", params={"category": category, "limit": 50})
                except Exception as exc:
                    self.note(f"remotive/{category}: {type(exc).__name__}")
                    continue
                if not self.accept(resp, f"remotive/{category}"):
                    continue

                for item in resp.json().get("jobs", []):
                    job_id = str(item.get("id", ""))
                    if job_id in seen_job_ids:
                        continue
                    seen_job_ids.add(job_id)

                    location = item.get("candidate_required_location") or "Worldwide"
                    loc_lower = location.lower()
                    salary = parse_salary_text(item.get("salary") or "")
                    job_url = item.get("url", "")
                    all_jobs.append(JobPosting(
                        id=f"remotive_{job_id}",
                        title=(item.get("title") or "").strip(),
                        company=(item.get("company_name") or "").strip(),
                        location=f"Remote ({location})",
                        is_remote=True,
                        remote_scope="Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else location,
                        url=job_url,
                        raw_url=job_url,
                        description=strip_html(item.get("description", ""))[:3000],
                        salary_min=salary.min,
                        salary_max=salary.max,
                        salary_currency=salary.currency,
                        salary_period=salary.period,
                        source="remotive",
                        posted_at=parse_iso_datetime(item.get("publication_date")),
                        tags=item.get("tags") or [],
                    ))
        return all_jobs
