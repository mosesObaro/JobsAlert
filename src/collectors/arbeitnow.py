"""
Arbeitnow API Collector.
Fetches European and global remote job postings from arbeitnow.com.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional

from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.feeds import strip_html
from src.models import JobPosting


class ArbeitnowCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="arbeitnow")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.arbeitnow.enabled

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.arbeitnow.enabled:
            return []

        async with self.create_http_client(timeout=12.0) as client:
            resp = await client.get("https://www.arbeitnow.com/api/job-board-api")
        if not self.accept(resp, "arbeitnow"):
            return []

        all_jobs: List[JobPosting] = []
        for item in resp.json().get("data", [])[:50]:
            slug = item.get("slug", "")
            location = item.get("location") or "Remote"
            is_remote = bool(item.get("remote", False) or "remote" in location.lower())
            job_url = item.get("url") or f"https://www.arbeitnow.com/view/{slug}"

            posted_at: Optional[datetime] = None
            if item.get("created_at"):
                try:
                    posted_at = datetime.fromtimestamp(int(item["created_at"]), tz=timezone.utc)
                except (TypeError, ValueError, OverflowError):
                    posted_at = None

            all_jobs.append(JobPosting(
                id=f"arbeitnow_{slug}",
                title=(item.get("title") or "").strip(),
                company=(item.get("company_name") or "").strip(),
                location=location,
                is_remote=is_remote,
                remote_scope="Worldwide" if "worldwide" in location.lower() else ("Remote" if is_remote else "On-Site"),
                url=job_url,
                raw_url=job_url,
                description=strip_html(item.get("description", ""))[:3000],
                source="arbeitnow",
                posted_at=posted_at,
                tags=item.get("tags") or [],
            ))
        return all_jobs
