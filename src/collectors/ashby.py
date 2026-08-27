"""
Ashby Public Job Board API Collector.
Fetches direct verified ATS postings from api.ashbyhq.com endpoints.
"""

from __future__ import annotations
from datetime import datetime
from typing import List
from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting


class AshbyCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="ashby")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.ashby.enabled:
            return []

        companies = config.sources.ashby.companies
        all_jobs: List[JobPosting] = []

        async with self.create_http_client(timeout=10.0) as client:
            for company_slug in companies:
                if not company_slug:
                    continue
                url = f"https://api.ashbyhq.com/posting-api/job-board/{company_slug.strip().lower()}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    jobs = data.get("jobs", [])

                    for item in jobs:
                        job_id = item.get("id", "")
                        title = item.get("title", "").strip()
                        location = item.get("location", "Remote") or "Remote"
                        is_remote = bool(item.get("isRemote", False) or "remote" in location.lower())
                        job_url = item.get("jobUrl", f"https://jobs.ashbyhq.com/{company_slug}/{job_id}")

                        # Extract compensation if provided
                        comp = item.get("compensation", {}) or {}
                        salary_min = None
                        salary_max = None
                        if comp.get("min"):
                            salary_min = float(comp["min"])
                        if comp.get("max"):
                            salary_max = float(comp["max"])

                        posted_at = None
                        if item.get("publishedAt"):
                            try:
                                posted_at = datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00"))
                            except Exception:
                                pass

                        loc_lower = location.lower()
                        remote_scope = "Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else ("Remote" if is_remote else "On-Site")

                        posting = JobPosting(
                            id=f"ashby_{company_slug}_{job_id}",
                            title=title,
                            company=company_slug.capitalize(),
                            location=location,
                            is_remote=is_remote,
                            remote_scope=remote_scope,
                            url=job_url,
                            raw_url=job_url,
                            description=f"{title} at {company_slug.capitalize()}. {location}",
                            salary_min=salary_min,
                            salary_max=salary_max,
                            source="ashby",
                            posted_at=posted_at,
                            tags=[company_slug]
                        )
                        all_jobs.append(posting)
                except Exception:
                    continue

        return all_jobs
