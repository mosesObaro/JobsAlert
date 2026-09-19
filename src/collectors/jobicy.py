"""
Jobicy Remote Jobs API Collector.
Fetches remote opportunities from jobicy.com.
"""

from __future__ import annotations
from typing import List

from src.collectors.base import BaseCollector, optional_float, parse_iso_datetime
from src.config import AppConfig
from src.feeds import strip_html
from src.models import JobPosting
from src.money import normalize_period

JOB_TYPES = {"full-time": "full_time", "part-time": "part_time", "contract": "contract", "internship": "internship", "freelance": "contract"}


class JobicyCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="jobicy")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.jobicy.enabled

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.jobicy.enabled:
            return []

        # The API rejects unknown `geo` values (it answered HTTP 400 to "geo=any"), so none is sent.
        async with self.create_http_client(timeout=12.0) as client:
            resp = await client.get("https://jobicy.com/api/v2/remote-jobs", params={"count": 50})
        if not self.accept(resp, "jobicy"):
            return []

        all_jobs: List[JobPosting] = []
        for item in resp.json().get("jobs", []):
            location = (item.get("jobGeo") or "Anywhere").strip()
            loc_lower = location.lower()
            job_level = item.get("jobLevel") or ""
            job_types = item.get("jobType") or []
            if isinstance(job_types, str):
                job_types = [job_types]
            employment_type = next((JOB_TYPES[t.lower()] for t in job_types if t and t.lower() in JOB_TYPES), "full_time")
            job_url = item.get("url", "")

            all_jobs.append(JobPosting(
                id=f"jobicy_{item.get('id', '')}",
                title=(item.get("jobTitle") or "").strip(),
                company=(item.get("companyName") or "").strip(),
                location=f"Remote ({location})",
                is_remote=True,
                remote_scope="Worldwide" if loc_lower in ("anywhere", "worldwide") else location,
                url=job_url,
                raw_url=job_url,
                description=strip_html(item.get("jobDescription", ""))[:3000],
                salary_min=optional_float(item.get("salaryMin") or item.get("annualSalaryMin")),
                salary_max=optional_float(item.get("salaryMax") or item.get("annualSalaryMax")),
                salary_currency=(item.get("salaryCurrency") or "USD").upper(),
                salary_period=normalize_period(item.get("salaryPeriod")) or "yearly",
                employment_type=employment_type,
                seniority=job_level.lower() or None,
                source="jobicy",
                posted_at=parse_iso_datetime(item.get("pubDate")),
                tags=[job_level] if job_level else [],
            ))
        return all_jobs
