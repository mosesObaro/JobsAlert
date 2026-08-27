"""
Greenhouse Public Boards API Collector.
Fetches verified direct ATS job postings from greenhouse.io endpoints.
"""

from __future__ import annotations
import re
from datetime import datetime
from typing import List
from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting


def clean_html(raw_html: str) -> str:
    """Strips HTML tags to create clean plain text description."""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", " ", raw_html)
    return " ".join(clean.split())


class GreenhouseCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="greenhouse")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.greenhouse.enabled:
            return []

        companies = config.sources.greenhouse.companies
        all_jobs: List[JobPosting] = []

        async with self.create_http_client(timeout=10.0) as client:
            for company_slug in companies:
                if not company_slug:
                    continue
                url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug.strip().lower()}/jobs?content=true"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    data = resp.json()
                    raw_jobs = data.get("jobs", [])

                    for item in raw_jobs:
                        job_id = str(item.get("id", ""))
                        title = item.get("title", "").strip()
                        location_obj = item.get("location", {})
                        location_name = location_obj.get("name", "Remote") if isinstance(location_obj, dict) else str(location_obj)
                        raw_content = item.get("content", "")
                        clean_desc = clean_html(raw_content)
                        abs_url = item.get("absolute_url", "")

                        # Determine remote status
                        loc_lower = location_name.lower()
                        is_remote = "remote" in loc_lower or "anywhere" in loc_lower or "worldwide" in loc_lower
                        remote_scope = "Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else ("Remote" if is_remote else "On-Site")

                        # Parse updated date
                        posted_at = None
                        if item.get("updated_at"):
                            try:
                                posted_at = datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
                            except Exception:
                                pass

                        posting = JobPosting(
                            id=f"gh_{company_slug}_{job_id}",
                            title=title,
                            company=company_slug.capitalize(),
                            location=location_name,
                            is_remote=is_remote,
                            remote_scope=remote_scope,
                            url=abs_url,
                            raw_url=abs_url,
                            description=clean_desc[:3000],
                            source="greenhouse",
                            posted_at=posted_at,
                            tags=[company_slug]
                        )
                        all_jobs.append(posting)
                except Exception:
                    # Continue with other companies gracefully
                    continue

        return all_jobs
