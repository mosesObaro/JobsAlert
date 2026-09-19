"""
JobsAlert Twitter / X Job Opportunity Collector.
Scouts hiring posts from monitored accounts and search queries through Twitter's public
syndication endpoint and public Nitter RSS mirrors. Both are unofficial and often
unavailable, so an empty result is common and reported as degraded health.
"""

from __future__ import annotations
import asyncio
import json
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Set, Tuple

import httpx

from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.deduplication import stable_hash
from src.feeds import parse_feed, strip_html
from src.models import JobPosting

PUBLIC_NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://xcancel.com",
    "https://nitter.privacydev.net",
]

SYNDICATION_URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name/{screen_name}"

HIRING_KEYWORDS = ["hiring", "job", "vacancy", "intern", "engineer", "accountant", "developer", "looking for",
                   "recruiter", "recruitment", "talent", "people ops"]


def _has_hiring_intent(text: str) -> bool:
    lower = text.lower()
    return any(re.search(r"(?<![a-z])" + re.escape(k), lower) for k in HIRING_KEYWORDS)


class TwitterCollector(BaseCollector):
    """Scouts Twitter/X for job opportunities from search queries and monitored accounts."""

    def __init__(self):
        super().__init__(name="twitter")

    def is_enabled(self, config: AppConfig) -> bool:
        return bool(config.sources.twitter and config.sources.twitter.enabled)

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not self.is_enabled(config):
            return []
        twitter_cfg = config.sources.twitter
        all_jobs: List[JobPosting] = []
        seen_tweet_ids: Set[str] = set()

        async with self.create_http_client(timeout=10.0, accept="*/*") as client:
            account_tasks = [
                self._fetch_account_tweets(client, account, twitter_cfg.max_tweets)
                for account in (twitter_cfg.monitored_accounts or [])
            ]
            search_tasks = [
                self._fetch_search_query_tweets(client, query, twitter_cfg.max_tweets)
                for query in (twitter_cfg.search_queries or [])
            ]
            results = await asyncio.gather(*(account_tasks + search_tasks), return_exceptions=True)

        for batch in results:
            if isinstance(batch, Exception) or not batch:
                continue
            for job in batch:
                if job.id not in seen_tweet_ids:
                    seen_tweet_ids.add(job.id)
                    all_jobs.append(job)

        return all_jobs[: twitter_cfg.max_tweets * 3]

    async def _fetch_account_tweets(self, client: httpx.AsyncClient, account: str, max_count: int) -> List[JobPosting]:
        """Recent hiring tweets from one handle: syndication endpoint first, then Nitter RSS."""
        handle = account.replace("@", "").strip()
        if not handle:
            return []

        try:
            resp = await client.get(SYNDICATION_URL.format(screen_name=handle))
            if resp.status_code == 200:
                jobs = self._parse_syndication_html(resp.text, handle)
                if jobs:
                    return jobs[:max_count]
        except httpx.HTTPError:
            pass

        for base in PUBLIC_NITTER_INSTANCES:
            try:
                resp = await client.get(f"{base}/{handle}/rss")
                if resp.status_code == 200:
                    jobs = self._parse_nitter_rss(resp.text, default_company=handle)
                    if jobs:
                        return jobs[:max_count]
            except httpx.HTTPError:
                continue
        self.note(f"twitter/@{handle}: no source reachable")
        return []

    async def _fetch_search_query_tweets(self, client: httpx.AsyncClient, query: str, max_count: int) -> List[JobPosting]:
        """Searches for a hiring query or hashtag via Nitter RSS."""
        encoded_query = urllib.parse.quote_plus(query)
        for base in PUBLIC_NITTER_INSTANCES:
            try:
                resp = await client.get(f"{base}/search/rss?f=tweets&q={encoded_query}")
                if resp.status_code == 200:
                    jobs = self._parse_nitter_rss(resp.text, default_company="Twitter Community")
                    if jobs:
                        return jobs[:max_count]
            except httpx.HTTPError:
                continue
        return []

    def _parse_nitter_rss(self, rss_xml: str, default_company: str = "Twitter") -> List[JobPosting]:
        """Parses tweets from a Nitter RSS feed."""
        try:
            items = parse_feed(rss_xml)
        except ET.ParseError:
            return []

        postings: List[JobPosting] = []
        for item in items:
            text_content = strip_html(item.summary) or item.title.strip()
            if not text_content or not _has_hiring_intent(text_content):
                continue

            tweet_url = item.link.strip()
            clean_tweet_url = re.sub(r"https?://[^/]+/", "https://x.com/", tweet_url)
            match = re.search(r"/status/(\d+)", tweet_url)
            tweet_id = match.group(1) if match else stable_hash(tweet_url or text_content)

            title, company = self._extract_title_and_company(text_content, default_company)
            # Links are taken from the tweet text, not the feed's HTML (which links to the mirror).
            embedded = self._extract_urls(text_content)
            target_url = embedded[0] if embedded else clean_tweet_url
            lower_text = text_content.lower()
            is_remote = any(r in lower_text for r in ["remote", "worldwide", "anywhere", "wfh", "work from home"])
            scope = "Worldwide" if "worldwide" in lower_text else ("Remote" if is_remote else "Unspecified")

            postings.append(JobPosting(
                id=f"twitter_{tweet_id}",
                title=title,
                company=company,
                location="Worldwide Remote" if scope == "Worldwide" else scope,
                is_remote=is_remote,
                remote_scope=scope,
                url=target_url,
                raw_url=target_url,
                description=text_content[:2500],
                source="twitter",
                posted_at=item.published or datetime.now(timezone.utc),
                tags=["Twitter / X", default_company, "#hiring"],
            ))
        return postings

    def _parse_syndication_html(self, html_text: str, author_handle: str) -> List[JobPosting]:
        """Extracts tweets from Twitter's public syndication profile payload."""
        match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_text, re.DOTALL)
        if not match:
            return []
        try:
            data = json.loads(match.group(1))
        except ValueError:
            return []

        postings: List[JobPosting] = []
        entries = data.get("props", {}).get("pageProps", {}).get("timeline", {}).get("entries", [])
        for entry in entries:
            content = entry.get("content", {}).get("tweet", {})
            text = content.get("full_text", "") if content else ""
            tweet_id = str(content.get("id_str", "")) if content else ""
            if not text or not tweet_id or not _has_hiring_intent(text):
                continue

            title, company = self._extract_title_and_company(text, author_handle)
            embedded = self._extract_urls(text)
            app_url = embedded[0] if embedded else f"https://x.com/{author_handle}/status/{tweet_id}"
            lower_text = text.lower()
            is_remote = any(r in lower_text for r in ["remote", "worldwide", "wfh", "anywhere"])
            postings.append(JobPosting(
                id=f"twitter_{tweet_id}",
                title=title,
                company=company,
                location="Remote" if is_remote else "Unspecified",
                is_remote=is_remote,
                remote_scope="Remote" if is_remote else "Unspecified",
                url=app_url,
                raw_url=app_url,
                description=text[:2500],
                source="twitter",
                posted_at=datetime.now(timezone.utc),
                tags=["Twitter / X", f"@{author_handle}", "#hiring"],
            ))
        return postings

    def _extract_title_and_company(self, text: str, default_company: str) -> Tuple[str, str]:
        """Heuristically extracts the job title and hiring company from tweet text."""
        clean_text = " ".join(strip_html(text).split())
        company = default_company
        title = "Hiring Announcement"

        hiring_patterns = [
            r"(?:we(?:'re| are)? hiring|looking for|opening for)\s+(?:a|an)?\s*([A-Za-z0-9\s\/\-\+]{4,45}?)(?:\s+at\s+([A-Za-z0-9\s]{2,30}))?(?:[.,!|\n]|$)",
            r"([A-Za-z0-9\s\/\-\+]{4,40})\s+(?:role|position|job)\s+(?:at|with)\s+([A-Za-z0-9\s]{2,30})",
            r"(?:hiring|wanted):\s*([A-Za-z0-9\s\/\-\+]{4,45})",
        ]
        for pattern in hiring_patterns:
            m = re.search(pattern, clean_text, re.IGNORECASE)
            if m:
                role = m.group(1).strip()
                if len(role) > 3 and not role.lower().startswith("http"):
                    title = role.title()
                if len(m.groups()) >= 2 and m.group(2) and len(m.group(2).strip()) > 2:
                    company = m.group(2).strip()
                break

        if title == "Hiring Announcement":
            first_line = clean_text.split(".")[0][:60]
            if len(first_line) > 5:
                title = first_line
        return title, company

    def _extract_urls(self, text: str) -> List[str]:
        """Embedded http(s) links (e.g. t.co or direct application links), excluding media."""
        urls = []
        for url in re.findall(r"https?://[^\s<>\"'{}|\\^`]+", text):
            url = url.rstrip(".,;!?)")
            if "pic.twitter.com" not in url and "pic.x.com" not in url:
                urls.append(url)
        return urls
