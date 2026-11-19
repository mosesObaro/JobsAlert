"""
Workable Collector — employer job boards hosted on Workable.

Reads the public widget endpoint each Workable board exposes:

    https://apply.workable.com/api/v1/widget/accounts/{account}

Added because Phase 1 found Kuda's board here after its Greenhouse token
stopped answering. Verified live on 2026-11-19 across three Nigerian fintech
boards — kuda, fairmoney and renmoney — 102 unique postings between them, 94 of
them in Nigeria.

Two things this endpoint does that the collector has to handle:

* It repeats postings. renmoney answered with 100 entries covering 72 distinct
  jobs, fairmoney 59 covering 25. Entries are deduplicated on `shortcode`, which
  is Workable's own job id. Deduplicating on title would be wrong: Renmoney
  genuinely has two "Business Analyst" openings, posted a year apart, with
  different shortcodes.
* Descriptions are omitted unless `?details=true` is passed, which the same
  single request per board accepts, so they cost nothing extra and let skills be
  matched from body text rather than from the title alone.

What it does give is good structured data: the account's display name, city,
state and country, a `telecommuting` flag, an employment type and a publication
date, which is more than enough to place a role geographically.
"""

from __future__ import annotations
from typing import Dict, List, Optional

import httpx

from src.collectors.base import BaseCollector, gather_limited, parse_iso_datetime
from src.config import AppConfig
from src.feeds import strip_html
from src.models import JobPosting

ENDPOINT = "https://apply.workable.com/api/v1/widget/accounts/{}"

EMPLOYMENT_TYPES: Dict[str, str] = {
    "full-time": "full_time",
    "part-time": "part_time",
    "contract": "contract",
    "temporary": "contract",
    "internship": "internship",
}


def location_text(item: dict) -> str:
    """"Lagos, Nigeria" from the city, state and country the board gives."""
    city = (item.get("city") or "").strip()
    state = (item.get("state") or "").strip()
    country = (item.get("country") or "").strip()
    # State is dropped when it merely repeats the city ("Lagos, Lagos").
    parts = [p for p in (city, state if state and state != city else "", country) if p]
    return ", ".join(parts) if parts else "Unknown"


def employment_type(raw: Optional[str]) -> str:
    return EMPLOYMENT_TYPES.get((raw or "").strip().lower(), "full_time")


def to_posting(account: str, company: str, item: dict) -> Optional[JobPosting]:
    """One widget entry as a posting, or None without a title or link."""
    title = (item.get("title") or "").strip()
    url = (item.get("shortlink") or item.get("url") or item.get("application_url") or "").strip()
    shortcode = (item.get("shortcode") or "").strip()
    if not title or not url:
        return None

    location = location_text(item)
    is_remote = bool(item.get("telecommuting"))
    tags = [t for t in ((item.get("department") or "").strip(), (item.get("function") or "").strip()) if t]

    return JobPosting(
        id=f"workable_{account}_{shortcode or url.rsplit('/', 1)[-1]}",
        title=title,
        company=company or account.capitalize(),
        location=location,
        is_remote=is_remote,
        remote_scope=location if is_remote else "On-Site",
        url=url,
        raw_url=url,
        description=strip_html(item.get("description") or "")[:3000],
        employment_type=employment_type(item.get("employment_type")),
        source="workable",
        posted_at=parse_iso_datetime(item.get("published_on") or item.get("created_at")),
        tags=tags,
    )


class WorkableCollector(BaseCollector):
    """Collects postings from the Workable boards named in configuration."""

    def __init__(self):
        super().__init__(name="workable")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.workable.enabled and any(s.strip() for s in config.sources.workable.companies)

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.workable.enabled:
            return []
        accounts = [s.strip().lower() for s in config.sources.workable.companies if s and s.strip()]
        if not accounts:
            return []

        async with self.create_http_client(timeout=12.0) as client:
            results = await gather_limited((self._fetch_board(client, a) for a in accounts), limit=4)

        jobs: List[JobPosting] = []
        for account, result in zip(accounts, results):
            if isinstance(result, Exception):
                self.note(f"workable/{account}: {type(result).__name__}")
            else:
                jobs.extend(result)
        return jobs

    async def _fetch_board(self, client: httpx.AsyncClient, account: str) -> List[JobPosting]:
        # details=true adds the job description without costing another request.
        response = await client.get(ENDPOINT.format(account), params={"details": "true"})
        if not self.accept(response, f"workable/{account}"):
            return []
        payload = response.json()
        if not isinstance(payload, dict):
            self.note(f"workable/{account}: unexpected response shape")
            return []

        company = (payload.get("name") or "").strip()
        # The widget repeats entries, so the board's own job id decides identity.
        unique: Dict[str, dict] = {}
        for item in payload.get("jobs") or []:
            if not isinstance(item, dict):
                continue
            key = (item.get("shortcode") or item.get("shortlink") or item.get("title") or "").strip()
            unique.setdefault(key, item)

        postings = [to_posting(account, company, item) for item in unique.values()]
        return [p for p in postings if p is not None]
