"""
Hacker News 'Who is Hiring?' Collector.
Reads the latest monthly hiring thread(s) posted by the `whoishiring` account via the Algolia HN API.
"""

from __future__ import annotations
import re
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from src.collectors.base import BaseCollector, parse_iso_datetime
from src.config import AppConfig
from src.feeds import strip_html
from src.models import JobPosting
from src.money import parse_salary_text

ALGOLIA = "https://hn.algolia.com/api/v1"
SEEKING_WORK = re.compile(r"seeking\s+work", re.IGNORECASE)
MAX_PAGES_PER_THREAD = 5
# A monthly thread is always recent. This keeps a stale one from being read as
# current: the "Freelancer? Seeking freelancer?" thread stopped in February 2020,
# so matching it by title alone would inject years-old postings.
MAX_THREAD_AGE_DAYS = 120
HITS_PER_PAGE = 200


class HackerNewsCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="hackernews")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.hackernews.enabled

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.hackernews.enabled:
            return []
        thread_limit = max(1, config.sources.hackernews.limit_stories or 1)

        all_jobs: List[JobPosting] = []
        async with self.create_http_client(timeout=15.0) as client:
            # Newest first: the whoishiring account posts "Who is hiring?", "Who wants to be hired?"
            # and "Freelancer?" threads each month.
            resp = await client.get(f"{ALGOLIA}/search_by_date", params={"tags": "story,author_whoishiring", "hitsPerPage": 12})
            if not self.accept(resp, "hackernews/threads"):
                return []
            wanted = ["who is hiring"]
            if config.sources.hackernews.freelancer_threads:
                wanted.append("freelancer")
            # "Who wants to be hired?" is the job-seeker thread and is never wanted.
            threads = [
                h for h in resp.json().get("hits", [])
                if any(w in (h.get("title") or "").lower() for w in wanted)
                and "wants to be hired" not in (h.get("title") or "").lower()
            ]
            if not threads:
                self.note("hackernews: no hiring thread found")
                return []

            for kind in wanted:
                matching = [h for h in threads if kind in (h.get("title") or "").lower()]
                # Age is only checked on the threads actually read: older ones
                # further down the list are simply not wanted, not a problem.
                for thread in matching[:thread_limit]:
                    if not self._is_current(thread, kind):
                        continue
                    all_jobs.extend(await self._collect_thread(
                        client, str(thread.get("objectID")), freelancer="freelancer" in kind
                    ))
        return all_jobs

    def _is_current(self, thread: dict, kind: str) -> bool:
        created = parse_iso_datetime(thread.get("created_at"))
        if created is None:
            return True
        age_days = (datetime.now(timezone.utc) - created).days
        if age_days <= MAX_THREAD_AGE_DAYS:
            return True
        self.note(f"hackernews: newest '{kind}' thread is {age_days} days old, skipped")
        return False

    async def _collect_thread(self, client: httpx.AsyncClient, story_id: str, freelancer: bool = False) -> List[JobPosting]:
        jobs: List[JobPosting] = []
        page, pages = 0, 1
        while page < min(pages, MAX_PAGES_PER_THREAD):
            resp = await client.get(
                f"{ALGOLIA}/search",
                params={"tags": f"comment,story_{story_id}", "hitsPerPage": HITS_PER_PAGE, "page": page},
            )
            if not self.accept(resp, f"hackernews/story_{story_id}"):
                break
            data = resp.json()
            pages = data.get("nbPages", 1) or 1
            for item in data.get("hits", []):
                # Replies ("is this still open?") are not job posts; only top-level comments are.
                if str(item.get("parent_id")) != story_id:
                    continue
                job = self._parse_comment(item, freelancer=freelancer)
                if job:
                    jobs.append(job)
            page += 1
        return jobs

    @staticmethod
    def _parse_comment(item: dict, freelancer: bool = False) -> Optional[JobPosting]:
        comment_html = item.get("comment_text") or ""
        if not comment_html:
            return None
        # The freelancer thread mixes "SEEKING FREELANCER" (employers) with
        # "SEEKING WORK" (freelancers advertising themselves); only the first
        # is a job. The marker never appears in the "Who is hiring?" thread.
        if SEEKING_WORK.search(comment_html):
            return None
        lines = [strip_html(part) for part in re.split(r"<p>", comment_html)]
        lines = [line for line in lines if line]
        if not lines:
            return None

        # Common header: "Stripe | Senior Infrastructure Engineer | Remote (US/EU) | Full-time"
        parts = [p.strip() for p in lines[0].split("|")]
        if len(parts) >= 2:
            company, title = parts[0], parts[1]
            location = parts[2] if len(parts) >= 3 else "Remote"
        else:
            company, title, location = "Hacker News Startup", lines[0][:60], "Remote"

        full_text = " ".join(lines)
        full_lower = full_text.lower()
        loc_lower = location.lower()
        is_remote = "remote" in loc_lower or "remote" in full_lower or "anywhere" in loc_lower
        remote_scope = "Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else ("Remote" if is_remote else "On-Site")

        salary = None
        match = re.search(r"([$€£]\s?\d[\d,.]*\s?[kK]?\s*[-–]\s*[$€£]?\s?\d[\d,.]*\s?[kK]?)", full_text)
        if match:
            salary = parse_salary_text(match.group(1))

        posted_at = None
        if item.get("created_at_i"):
            try:
                posted_at = datetime.fromtimestamp(int(item["created_at_i"]), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                posted_at = None

        comment_id = item.get("objectID", "")
        url = f"https://news.ycombinator.com/item?id={comment_id}"
        return JobPosting(
            id=f"hn_{comment_id}",
            title=title[:100],
            company=company[:60],
            location=location[:100],
            is_remote=is_remote,
            remote_scope=remote_scope,
            url=url,
            raw_url=url,
            description=full_text[:3000],
            salary_min=salary.min if salary else None,
            salary_max=salary.max if salary else None,
            salary_currency=salary.currency if salary else "USD",
            salary_period=salary.period if salary else "yearly",
            source="hackernews",
            posted_at=posted_at,
            tags=["HN Freelancer", "Contract"] if freelancer else ["HN Who is Hiring", "Startup"],
        )
