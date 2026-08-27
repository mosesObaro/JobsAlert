"""
Arbeitnow API Collector.
Fetches verified remote & European technical job postings from arbeitnow.com.
"""

from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import List
from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting


class ArbeitnowCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="arbeitnow")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.arbeitnow.enabled:
            return []

        url = "https://www.arbeitnow.com/api/job-board-api"
        all_jobs: List[JobPosting] = []

        async with self.create_http_client(timeout=12.0) as client:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                items = data.get("data", [])

                for item in items[:50]:
                    slug = item.get("slug", "")
                    title = item.get("title", "").strip()
                    company = item.get("company_name", "").strip()
                    location = item.get("location", "Remote") or "Remote"
                    is_remote = bool(item.get("remote", False) or "remote" in location.lower())
                    job_url = item.get("url", f"https://www.arbeitnow.com/view/{slug}")

                    raw_desc = item.get("description", "")
                    clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                    clean_desc = " ".join(clean_desc.split())

                    posted_at = None
                    created_at = item.get("created_at")
                    if created_at:
                        try:
                            posted_at = datetime.fromtimestamp(int(created_at), tz=timezone.utc)
                        except Exception:
                            pass

                    loc_lower = location.lower()
                    remote_scope = "Worldwide" if ("worldwide" in loc_lower or not location) else ("Remote" if is_remote else "On-Site")

                    posting = JobPosting(
                        id=f"arbeitnow_{slug}",
                        title=title,
                        company=company,
                        location=location,
                        is_remote=is_remote,
                        remote_scope=remote_scope,
                        url=job_url,
                        raw_url=job_url,
                        description=clean_desc[:3000],
                        source="arbeitnow",
                        posted_at=posted_at,
                        tags=item.get("tags", [])
                    )
                    all_jobs.append(posting)
            except Exception as e:
                self.health.error_message = str(e)

        return all_jobs
