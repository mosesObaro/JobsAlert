"""
RemoteOK Public API Collector.
Fetches verified remote opportunities from remoteok.com.
"""

from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import List
from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting


class RemoteOKCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="remoteok")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.remoteok.enabled:
            return []

        url = "https://remoteok.com/api"
        all_jobs: List[JobPosting] = []

        async with self.create_http_client(timeout=15.0) as client:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []
                items = resp.json()
                if not isinstance(items, list):
                    return []

                # Skip the first element if it's the metadata/legal disclaimer
                job_items = [i for i in items if isinstance(i, dict) and i.get("id") and i.get("position")]

                for item in job_items[:60]:
                    job_id = str(item.get("id", ""))
                    title = item.get("position", "").strip()
                    company = item.get("company", "").strip()
                    location = item.get("location", "Worldwide") or "Worldwide"
                    job_url = item.get("url", "")
                    if not job_url.startswith("http"):
                        job_url = f"https://remoteok.com/remote-jobs/{job_id}"

                    raw_desc = item.get("description", "")
                    clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                    clean_desc = " ".join(clean_desc.split())

                    salary_min = float(item.get("salary_min", 0)) or None
                    salary_max = float(item.get("salary_max", 0)) or None

                    posted_at = None
                    epoch = item.get("epoch")
                    if epoch:
                        try:
                            posted_at = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
                        except Exception:
                            pass

                    loc_lower = location.lower()
                    remote_scope = "Worldwide" if ("worldwide" in loc_lower or not location) else location

                    posting = JobPosting(
                        id=f"remoteok_{job_id}",
                        title=title,
                        company=company,
                        location=f"Remote ({location})",
                        is_remote=True,
                        remote_scope=remote_scope,
                        url=job_url,
                        raw_url=job_url,
                        description=clean_desc[:3000],
                        salary_min=salary_min,
                        salary_max=salary_max,
                        source="remoteok",
                        posted_at=posted_at,
                        tags=item.get("tags", [])
                    )
                    all_jobs.append(posting)
            except Exception as e:
                self.health.error_message = str(e)

        return all_jobs
