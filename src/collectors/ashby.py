"""
Ashby Public Job Board API Collector.
Fetches direct ATS postings, descriptions and salary ranges from api.ashbyhq.com.
"""

from __future__ import annotations
from typing import List, Optional, Tuple

import httpx

from src.collectors.base import BaseCollector, gather_limited, optional_float, parse_iso_datetime
from src.config import AppConfig
from src.models import JobPosting
from src.money import normalize_period

EMPLOYMENT_TYPES = {"fulltime": "full_time", "parttime": "part_time", "contract": "contract", "intern": "internship", "temporary": "contract"}


def parse_ashby_salary(compensation: Optional[dict]) -> Tuple[Optional[float], Optional[float], str, str]:
    """(min, max, currency, period) from Ashby's compensation.summaryComponents."""
    for component in (compensation or {}).get("summaryComponents") or []:
        if (component.get("compensationType") or "").lower() == "salary":
            return (
                optional_float(component.get("minValue")),
                optional_float(component.get("maxValue")),
                (component.get("currencyCode") or "USD").upper(),
                normalize_period(component.get("interval")) or "yearly",
            )
    return None, None, "USD", "yearly"


class AshbyCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="ashby")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.ashby.enabled and any(s.strip() for s in config.sources.ashby.companies)

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.ashby.enabled:
            return []
        slugs = [s.strip().lower() for s in config.sources.ashby.companies if s and s.strip()]
        async with self.create_http_client(timeout=10.0) as client:
            results = await gather_limited((self._fetch_board(client, slug) for slug in slugs), limit=4)

        jobs: List[JobPosting] = []
        for slug, result in zip(slugs, results):
            if isinstance(result, Exception):
                self.note(f"ashby/{slug}: {type(result).__name__}")
            else:
                jobs.extend(result)
        return jobs

    async def _fetch_board(self, client: httpx.AsyncClient, company_slug: str) -> List[JobPosting]:
        resp = await client.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{company_slug}",
            params={"includeCompensation": "true"},
        )
        if not self.accept(resp, f"ashby/{company_slug}"):
            return []

        jobs: List[JobPosting] = []
        for item in resp.json().get("jobs", []):
            if item.get("isListed") is False:
                continue
            job_id = item.get("id", "")
            title = (item.get("title") or "").strip()
            location = item.get("location") or "Remote"
            is_remote = bool(item.get("isRemote", False) or "remote" in location.lower())
            loc_lower = location.lower()
            remote_scope = "Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else ("Remote" if is_remote else "On-Site")
            job_url = item.get("jobUrl") or f"https://jobs.ashbyhq.com/{company_slug}/{job_id}"
            salary_min, salary_max, currency, period = parse_ashby_salary(item.get("compensation"))
            description = item.get("descriptionPlain") or f"{title} at {company_slug.capitalize()}. {location}"

            jobs.append(JobPosting(
                id=f"ashby_{company_slug}_{job_id}",
                title=title,
                company=company_slug.capitalize(),
                location=location,
                is_remote=is_remote,
                remote_scope=remote_scope,
                url=job_url,
                raw_url=job_url,
                description=description[:3000],
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=currency,
                salary_period=period,
                employment_type=EMPLOYMENT_TYPES.get((item.get("employmentType") or "").lower(), "full_time"),
                source="ashby",
                posted_at=parse_iso_datetime(item.get("publishedAt")),
                tags=[company_slug],
            ))
        return jobs
