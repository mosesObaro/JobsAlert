"""
Greenhouse Public Boards API Collector.
Fetches direct ATS job postings from boards-api.greenhouse.io.
"""

from __future__ import annotations
import html
from typing import List

import httpx

from src.collectors.base import BaseCollector, gather_limited, parse_iso_datetime
from src.config import AppConfig
from src.feeds import strip_html
from src.models import JobPosting


def clean_html(raw_html: str) -> str:
    """Plain text from Greenhouse's entity-encoded HTML job content."""
    return strip_html(html.unescape(raw_html or ""))


class GreenhouseCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="greenhouse")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.greenhouse.enabled and any(s.strip() for s in config.sources.greenhouse.companies)

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.greenhouse.enabled:
            return []
        slugs = [s.strip().lower() for s in config.sources.greenhouse.companies if s and s.strip()]
        async with self.create_http_client(timeout=10.0) as client:
            results = await gather_limited((self._fetch_board(client, slug) for slug in slugs), limit=4)

        jobs: List[JobPosting] = []
        for slug, result in zip(slugs, results):
            if isinstance(result, Exception):
                self.note(f"greenhouse/{slug}: {type(result).__name__}")
            else:
                jobs.extend(result)
        return jobs

    async def _fetch_board(self, client: httpx.AsyncClient, slug: str) -> List[JobPosting]:
        resp = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
        if not self.accept(resp, f"greenhouse/{slug}"):
            return []

        jobs: List[JobPosting] = []
        for item in resp.json().get("jobs", []):
            location_obj = item.get("location") or {}
            location_name = (location_obj.get("name") if isinstance(location_obj, dict) else str(location_obj)) or "Remote"
            loc_lower = location_name.lower()
            is_remote = "remote" in loc_lower or "anywhere" in loc_lower or "worldwide" in loc_lower
            remote_scope = "Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else ("Remote" if is_remote else "On-Site")
            url = item.get("absolute_url", "")
            jobs.append(JobPosting(
                id=f"gh_{slug}_{item.get('id', '')}",
                title=(item.get("title") or "").strip(),
                company=slug.capitalize(),
                location=location_name,
                is_remote=is_remote,
                remote_scope=remote_scope,
                url=url,
                raw_url=url,
                description=clean_html(item.get("content", ""))[:3000],
                source="greenhouse",
                # first_published is the posting date; updated_at changes on every edit.
                posted_at=parse_iso_datetime(item.get("first_published") or item.get("updated_at")),
                tags=[slug],
            ))
        return jobs
