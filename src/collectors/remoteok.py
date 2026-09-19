"""
RemoteOK Public API Collector.
Fetches remote opportunities from remoteok.com.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional

from src.collectors.base import BaseCollector, optional_float
from src.config import AppConfig
from src.feeds import strip_html
from src.models import JobPosting


class RemoteOKCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="remoteok")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.remoteok.enabled

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.remoteok.enabled:
            return []

        async with self.create_http_client(timeout=15.0) as client:
            resp = await client.get("https://remoteok.com/api")
        if not self.accept(resp, "remoteok"):
            return []
        items = resp.json()
        if not isinstance(items, list):
            self.note("remoteok: unexpected response shape")
            return []

        all_jobs: List[JobPosting] = []
        # The first element is a legal notice, not a job.
        job_items = [i for i in items if isinstance(i, dict) and i.get("id") and i.get("position")]
        for item in job_items[:60]:
            job_id = str(item.get("id", ""))
            location = item.get("location") or "Worldwide"
            job_url = item.get("url", "")
            if not job_url.startswith("http"):
                job_url = f"https://remoteok.com/remote-jobs/{job_id}"

            posted_at: Optional[datetime] = None
            if item.get("epoch"):
                try:
                    posted_at = datetime.fromtimestamp(int(item["epoch"]), tz=timezone.utc)
                except (TypeError, ValueError, OverflowError):
                    posted_at = None

            all_jobs.append(JobPosting(
                id=f"remoteok_{job_id}",
                title=(item.get("position") or "").strip(),
                company=(item.get("company") or "").strip(),
                location=f"Remote ({location})",
                is_remote=True,
                remote_scope="Worldwide" if ("worldwide" in location.lower() or not location) else location,
                url=job_url,
                raw_url=job_url,
                description=strip_html(item.get("description", ""))[:3000],
                salary_min=optional_float(item.get("salary_min")),
                salary_max=optional_float(item.get("salary_max")),
                source="remoteok",
                posted_at=posted_at,
                tags=item.get("tags") or [],
            ))
        return all_jobs
