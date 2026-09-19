"""
Lever Public Postings API Collector.
Fetches direct ATS job postings from api.lever.co.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from src.collectors.base import BaseCollector, gather_limited, optional_float
from src.config import AppConfig
from src.models import JobPosting
from src.money import normalize_period


class LeverCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="lever")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.lever.enabled and any(s.strip() for s in config.sources.lever.companies)

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.lever.enabled:
            return []
        slugs = [s.strip().lower() for s in config.sources.lever.companies if s and s.strip()]
        async with self.create_http_client(timeout=10.0) as client:
            results = await gather_limited((self._fetch_company(client, slug) for slug in slugs), limit=4)

        jobs: List[JobPosting] = []
        for slug, result in zip(slugs, results):
            if isinstance(result, Exception):
                self.note(f"lever/{slug}: {type(result).__name__}")
            else:
                jobs.extend(result)
        return jobs

    async def _fetch_company(self, client: httpx.AsyncClient, slug: str) -> List[JobPosting]:
        resp = await client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
        if not self.accept(resp, f"lever/{slug}"):
            return []
        postings = resp.json()
        if not isinstance(postings, list):
            self.note(f"lever/{slug}: unexpected response shape")
            return []

        jobs: List[JobPosting] = []
        for item in postings:
            categories = item.get("categories") or {}
            location = categories.get("location") or "Remote"
            team = categories.get("team", "")
            commitment = categories.get("commitment") or "Full-time"
            loc_lower = location.lower()
            is_remote = "remote" in loc_lower or "anywhere" in loc_lower or "worldwide" in loc_lower
            remote_scope = "Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else ("Remote" if is_remote else "On-Site")

            posted_at: Optional[datetime] = None
            if item.get("createdAt"):
                try:
                    posted_at = datetime.fromtimestamp(item["createdAt"] / 1000.0, tz=timezone.utc)
                except (TypeError, ValueError, OverflowError):
                    posted_at = None

            salary = item.get("salaryRange") or {}
            hosted_url = item.get("hostedUrl", "")
            jobs.append(JobPosting(
                id=f"lever_{slug}_{item.get('id', '')}",
                title=(item.get("text") or "").strip(),
                company=slug.capitalize(),
                location=location,
                is_remote=is_remote,
                remote_scope=remote_scope,
                url=hosted_url,
                raw_url=hosted_url,
                description=(item.get("descriptionPlain") or item.get("additionalPlain") or "")[:3000],
                salary_min=optional_float(salary.get("min")),
                salary_max=optional_float(salary.get("max")),
                salary_currency=(salary.get("currency") or "USD").upper(),
                salary_period=normalize_period(salary.get("interval")) or "yearly",
                employment_type="full_time" if "full" in commitment.lower() else "contract",
                source="lever",
                posted_at=posted_at,
                tags=[team] if team else [],
            ))
        return jobs
