"""
LinkedIn Guest Jobs Collector.

Reads the endpoint behind the logged-out job search results list
(`/jobs-guest/jobs/api/seeMoreJobPostings/search`), which answers with a
fragment of job-card HTML rather than JSON.

Measured against the live endpoint on 2026-10-23, and the reason this collector
stays deliberately small:
  * It is undocumented, and LinkedIn's User Agreement forbids automated access.
    Requests are therefore few and paced: a low page cap, searches run one after
    another, and a delay between pages.
  * It rate-limits quickly. Roughly 15 requests over a few minutes drew HTTP 429,
    and `start=80` answered 429 while `start=0`, `20` and `40` succeeded. A 429
    ends that search and marks the source degraded rather than failing the run.
  * The card markup is not a published API and can change without notice, so
    parsing is defensive: a card without a title or link is skipped, and a search
    that returns no cards simply contributes nothing.
"""

from __future__ import annotations
import asyncio
import html
import re
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from src.collectors.base import BaseCollector, parse_iso_datetime
from src.config import AppConfig, LinkedInConfig, LinkedInSearchConfig
from src.feeds import strip_html
from src.models import JobPosting
from src.money import parse_salary_text

ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

# The endpoint returns ten cards per page and 429s on deep pagination.
PAGE_SIZE = 10
MAX_PAGES = 3

# f_JT codes, as used by the public job search UI. "C" is Contract.
JOB_TYPE_TO_EMPLOYMENT: Dict[str, str] = {
    "F": "full_time",
    "P": "part_time",
    "C": "contract",
    "T": "contract",  # Temporary
    "I": "internship",
}

# Per-click tracking carried by the card links. These stay local to this module
# rather than joining src.deduplication.TRACKING_PARAMS: widening the shared set
# would change canonical URLs, and therefore fingerprints, for postings every
# other source has already recorded.
TRACKING_PARAMS = {
    "refid", "trackingid", "position", "pagenum", "trk", "trkinfo",
    "originalsubdomain", "ebp", "licu", "lici",
}

_CARD_ID = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
_LIST_ITEM = re.compile(r"<li\b[^>]*>", re.IGNORECASE)
_FULL_LINK = re.compile(r'<a[^>]*base-card__full-link[^>]*href="([^"]+)"', re.IGNORECASE)
# Roughly one card in ten omits the classed anchor and wraps the whole card in a
# bare link instead, so any anchor pointing at a posting will do.
_JOB_LINK = re.compile(r'<a[^>]*href="([^"]*/jobs/view/[^"]*)"', re.IGNORECASE)
_TITLE = re.compile(r'class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</h3>', re.IGNORECASE | re.DOTALL)
_COMPANY = re.compile(r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>(.*?)</h4>', re.IGNORECASE | re.DOTALL)
_LOCATION = re.compile(r'class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</span>', re.IGNORECASE | re.DOTALL)
# Not present in any sampled response; parsed when LinkedIn does include it.
_SALARY = re.compile(r'class="[^"]*salary-info[^"]*"[^>]*>(.*?)</span>', re.IGNORECASE | re.DOTALL)
_POSTED = re.compile(r'<time[^>]*datetime="([^"]+)"', re.IGNORECASE)


def strip_tracking(raw_url: str) -> str:
    """Drops LinkedIn's per-click tracking parameters from a card link."""
    if not raw_url:
        return ""
    parsed = urlparse(html.unescape(raw_url.strip()))
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() not in TRACKING_PARAMS
    ]
    return urlunparse((
        parsed.scheme.lower() or "https",
        parsed.netloc.lower(),
        parsed.path,
        "",
        urlencode(query, doseq=True),
        "",
    ))


def canonical_job_url(job_id: str) -> str:
    """The stable public URL for a posting.

    Card links arrive on a country subdomain (`ng.linkedin.com`) with a slug that
    varies per listing, which would split one posting across several fingerprints.
    This id-only form is the same for every run and answers 200 to a logged-out
    request, so the link verifier can check it.
    """
    return f"https://www.linkedin.com/jobs/view/{job_id}"


def _first(pattern: re.Pattern, card: str) -> str:
    match = pattern.search(card)
    return strip_html(match.group(1)) if match else ""


def split_cards(markup: str) -> List[Tuple[str, str]]:
    """Splits the returned fragment into (job id, card markup) pairs.

    Splitting on the list item rather than on the urn attribute keeps the
    wrapping anchor that some cards carry ahead of it.
    """
    cards: List[Tuple[str, str]] = []
    for chunk in _LIST_ITEM.split(markup or ""):
        found = _CARD_ID.search(chunk)
        if found:
            cards.append((found.group(1), chunk))
    return cards


def parse_card(
    job_id: str,
    card: str,
    employment_type: str,
    remote_filtered: bool = False,
) -> Optional[JobPosting]:
    """Turns one job card into a posting, or None when it has no readable title.

    The apply link is optional: `url` is derived from the posting id, so a card
    whose anchor cannot be found still yields a usable posting.

    `remote_filtered` says the search asked LinkedIn for remote roles only
    (f_WT=2). Cards name the hiring office rather than the work arrangement, so
    a remote role still reads "Charlotte, NC"; trusting the filter we asked for
    is more accurate than looking for "remote" in that text.
    """
    title = _first(_TITLE, card)
    if not title:
        return None
    link = _FULL_LINK.search(card) or _JOB_LINK.search(card)

    location = _first(_LOCATION, card) or "Unknown"
    is_remote = remote_filtered or "remote" in location.lower()
    salary = parse_salary_text(_first(_SALARY, card))
    posted = _POSTED.search(card)

    return JobPosting(
        id=f"linkedin_{job_id}",
        title=title,
        company=_first(_COMPANY, card) or "Unknown",
        location=location,
        is_remote=is_remote,
        # Cards carry no remote scope of their own, so the location stands in:
        # for a remote-filtered result it reads as "remote, based there".
        remote_scope=location if is_remote else "Unspecified",
        url=canonical_job_url(job_id),
        raw_url=strip_tracking(link.group(1)) if link else None,
        salary_min=salary.min,
        salary_max=salary.max,
        salary_currency=salary.currency,
        salary_period=salary.period,
        employment_type=employment_type,
        source="linkedin",
        # `datetime` is a plain date, which parse_iso_datetime reads as UTC midnight.
        posted_at=parse_iso_datetime(posted.group(1)) if posted else None,
    )


class LinkedInCollector(BaseCollector):
    """Collects contract (or otherwise filtered) postings from LinkedIn's guest search."""

    # A narrow search over a short window legitimately returns nothing, so an
    # empty run is not by itself a sign of trouble.
    expects_results = False

    def __init__(self):
        super().__init__(name="linkedin")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.linkedin.enabled

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        settings = config.sources.linkedin
        if not settings.enabled:
            return []

        jobs: List[JobPosting] = []
        seen: Set[str] = set()
        # Browsers reach this endpoint from the job search page; it answers to a
        # plain client too, and the default collector agent identifies the tool.
        async with self.create_http_client(timeout=15.0, accept="text/html, */*") as client:
            for index, search in enumerate(settings.searches):
                label = search.name or search.keywords or f"search {index + 1}"
                if not search.keywords.strip():
                    self.note(f"linkedin/{label}: no keywords configured")
                    continue
                if index:
                    await self._pause(settings)
                jobs.extend(await self._run_search(client, settings, search, label, seen))
        return jobs

    async def _pause(self, settings: LinkedInConfig) -> None:
        if settings.request_delay_seconds > 0:
            await asyncio.sleep(settings.request_delay_seconds)

    async def _run_search(
        self,
        client: httpx.AsyncClient,
        settings: LinkedInConfig,
        search: LinkedInSearchConfig,
        label: str,
        seen: Set[str],
    ) -> List[JobPosting]:
        employment_type = JOB_TYPE_TO_EMPLOYMENT.get(search.job_type.upper(), "full_time")
        pages = min(MAX_PAGES, max(1, -(-search.max_results // PAGE_SIZE)))
        collected: List[JobPosting] = []

        for page in range(pages):
            if page:
                await self._pause(settings)
            response = await client.get(ENDPOINT, params=self._params(search, page * PAGE_SIZE))
            # A 429 means this search is done for now; whatever it already
            # returned is kept and the source is reported degraded.
            if not self.accept(response, f"linkedin/{label}"):
                break

            cards = split_cards(response.text)
            if not cards:
                break

            for job_id, card in cards:
                if job_id in seen:
                    continue
                posting = parse_card(job_id, card, employment_type, search.remote_only)
                if posting is None:
                    self.note(f"linkedin/{label}: unreadable card {job_id}")
                    continue
                seen.add(job_id)
                collected.append(posting)
                if len(collected) >= search.max_results:
                    return collected

            if len(cards) < PAGE_SIZE:
                break
        return collected

    def _params(self, search: LinkedInSearchConfig, start: int) -> Dict[str, str]:
        params = {
            "keywords": search.keywords,
            "location": search.location,
            "f_JT": search.job_type.upper(),
            "start": str(start),
        }
        if search.time_posted:
            params["f_TPR"] = search.time_posted
        if search.remote_only:
            params["f_WT"] = "2"  # Remote
        return params
