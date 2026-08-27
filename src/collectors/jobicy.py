"""
Jobicy Remote Jobs API Collector.
Fetches verified remote opportunities from jobicy.com.
"""

from __future__ import annotations
import re
from datetime import datetime
from typing import List
from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting


class JobicyCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="jobicy")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.jobicy.enabled:
            return []

        url = "https://jobicy.com/api/v2/remote-jobs?count=50&geo=any"
        all_jobs: List[JobPosting] = []

        async with self.create_http_client(timeout=12.0) as client:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                items = data.get("jobs", [])

                for item in items:
                    job_id = str(item.get("id", ""))
                    title = item.get("jobTitle", "").strip()
                    company = item.get("companyName", "").strip()
                    location = item.get("jobGeo", "Worldwide") or "Worldwide"
                    job_url = item.get("url", "")
                    job_level = item.get("jobLevel", "")

                    raw_desc = item.get("jobDescription", "")
                    clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                    clean_desc = " ".join(clean_desc.split())

                    salary_min = float(item.get("annualSalaryMin", 0)) or None
                    salary_max = float(item.get("annualSalaryMax", 0)) or None

                    posted_at = None
                    if item.get("pubDate"):
                        try:
                            # Format often like "2026-08-20 14:00:00"
                            posted_at = datetime.fromisoformat(item["pubDate"])
                        except Exception:
                            pass

                    loc_lower = location.lower()
                    remote_scope = "Worldwide" if ("worldwide" in loc_lower or "any" in loc_lower) else location

                    posting = JobPosting(
                        id=f"jobicy_{job_id}",
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
                        seniority=job_level.lower() if job_level else None,
                        source="jobicy",
                        posted_at=posted_at,
                        tags=[job_level] if job_level else []
                    )
                    all_jobs.append(posting)
            except Exception as e:
                self.health.error_message = str(e)

        return all_jobs
