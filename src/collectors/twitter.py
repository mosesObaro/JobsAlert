"""
JobsAlert Twitter / X Job Opportunity Collector.
Continuously scouts Twitter/X for job postings, hiring announcements, and career alerts
across target hashtags, search queries, and recruiter/company accounts using resilient public discovery.
"""

from __future__ import annotations
import asyncio
import json
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
import xml.etree.ElementTree as ET
import httpx

from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting

PUBLIC_NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://xcancel.com",
    "https://nitter.privacydev.net",
]

SYNDICATION_URL = "https://syndication.twitter.com/srv/timeline-profile/screen-name/{screen_name}"


class TwitterCollector(BaseCollector):
    """Scouts Twitter/X for job opportunities from search queries and monitored accounts."""

    def __init__(self):
        super().__init__(name="twitter")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        twitter_cfg = config.sources.twitter
        if not twitter_cfg or not twitter_cfg.enabled:
            return []

        all_jobs: List[JobPosting] = []
        seen_tweet_ids: Set[str] = set()

        async with self.create_http_client(timeout=10.0) as client:
            # 1. Collect from monitored recruiter / tech accounts
            account_tasks = [
                self._fetch_account_tweets(client, account, twitter_cfg.max_tweets)
                for account in (twitter_cfg.monitored_accounts or [])
            ]

            # 2. Collect from search queries and hashtags
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

    async def _fetch_account_tweets(
        self, client: httpx.AsyncClient, account: str, max_count: int
    ) -> List[JobPosting]:
        """Fetches recent tweets from a specific Twitter user handle."""
        clean_handle = account.replace("@", "").strip()
        if not clean_handle:
            return []

        # Strategy A: Public Syndication API
        try:
            url = SYNDICATION_URL.format(screen_name=clean_handle)
            resp = await client.get(url)
            if resp.status_code == 200:
                jobs = self._parse_syndication_html(resp.text, clean_handle)
                if jobs:
                    return jobs[:max_count]
        except Exception:
            pass

        # Strategy B: Nitter RSS fallback
        for nitter_base in PUBLIC_NITTER_INSTANCES:
            try:
                rss_url = f"{nitter_base}/{clean_handle}/rss"
                resp = await client.get(rss_url)
                if resp.status_code == 200:
                    jobs = self._parse_nitter_rss(resp.text, default_company=clean_handle)
                    if jobs:
                        return jobs[:max_count]
            except Exception:
                continue

        return []

    async def _fetch_search_query_tweets(
        self, client: httpx.AsyncClient, query: str, max_count: int
    ) -> List[JobPosting]:
        """Searches Twitter for a hiring query or hashtag via Nitter RSS."""
        encoded_query = urllib.parse.quote_plus(query)
        for nitter_base in PUBLIC_NITTER_INSTANCES:
            try:
                rss_url = f"{nitter_base}/search/rss?f=tweets&q={encoded_query}"
                resp = await client.get(rss_url)
                if resp.status_code == 200:
                    jobs = self._parse_nitter_rss(resp.text, default_company="Twitter Community")
                    if jobs:
                        return jobs[:max_count]
            except Exception:
                continue
        return []

    def _parse_nitter_rss(self, rss_xml: str, default_company: str = "Twitter") -> List[JobPosting]:
        """Parses tweets from an RSS feed response."""
        postings: List[JobPosting] = []
        try:
            root = ET.fromstring(rss_xml)
            channel = root.find("channel")
            if channel is None:
                return []

            for item in channel.findall("item"):
                title_elem = item.find("title")
                desc_elem = item.find("description")
                link_elem = item.find("link")
                pub_date_elem = item.find("pubDate")

                text_content = (desc_elem.text or title_elem.text or "").strip()
                if not text_content:
                    continue

                # Filter for hiring intent
                lower_text = text_content.lower()
                hiring_keywords = ["hiring", "job", "vacancy", "intern", "engineer", "accountant", "developer", "looking for"]
                if not any(k in lower_text for k in hiring_keywords):
                    continue

                tweet_url = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                # Convert nitter domain back to x.com for canonicalization
                clean_tweet_url = re.sub(r"https?://[^/]+/", "https://x.com/", tweet_url)

                tweet_id_match = re.search(r"/status/(\d+)", tweet_url)
                tweet_id = tweet_id_match.group(1) if tweet_id_match else str(abs(hash(tweet_url or text_content)))

                extracted_title, extracted_company = self._extract_title_and_company(text_content, default_company)
                embedded_links = self._extract_urls(text_content)
                target_url = embedded_links[0] if embedded_links else clean_tweet_url

                is_remote = any(r in lower_text for r in ["remote", "worldwide", "anywhere", "wfh", "work from home"])

                posted_at = datetime.now(timezone.utc)
                if pub_date_elem is not None and pub_date_elem.text:
                    try:
                        from email.utils import parsedate_to_datetime
                        posted_at = parsedate_to_datetime(pub_date_elem.text)
                    except Exception:
                        pass

                posting = JobPosting(
                    id=f"twitter_{tweet_id}",
                    title=extracted_title,
                    company=extracted_company,
                    location="Worldwide Remote" if "worldwide" in lower_text else ("Remote" if is_remote else "Unspecified"),
                    is_remote=is_remote,
                    remote_scope="Worldwide" if "worldwide" in lower_text else ("Remote" if is_remote else "Unspecified"),
                    url=target_url,
                    raw_url=target_url,
                    description=text_content[:2500],
                    source="twitter",
                    posted_at=posted_at,
                    tags=["Twitter / X", default_company, "#hiring"],
                )
                postings.append(posting)

        except Exception as e:
            pass

        return postings

    def _parse_syndication_html(self, html_text: str, author_handle: str) -> List[JobPosting]:
        """Extracts tweets from Twitter's public syndication profile payload."""
        postings: List[JobPosting] = []
        try:
            # Look for embedded JSON state inside __NEXT_DATA__ or script tags
            match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html_text, re.DOTALL)
            if match:
                data = json.loads(match.group(1))
                entries = data.get("props", {}).get("pageProps", {}).get("timeline", {}).get("entries", [])
                for entry in entries:
                    content = entry.get("content", {}).get("tweet", {})
                    if not content:
                        continue
                    text = content.get("full_text", "")
                    tweet_id = str(content.get("id_str", ""))
                    if not text or not tweet_id:
                        continue

                    lower_text = text.lower()
                    if not any(k in lower_text for k in ["hiring", "job", "vacancy", "intern", "engineer", "accountant"]):
                        continue

                    extracted_title, extracted_company = self._extract_title_and_company(text, author_handle)
                    embedded_urls = self._extract_urls(text)
                    app_url = embedded_urls[0] if embedded_urls else f"https://x.com/{author_handle}/status/{tweet_id}"
                    is_remote = any(r in lower_text for r in ["remote", "worldwide", "wfh", "anywhere"])

                    posting = JobPosting(
                        id=f"twitter_{tweet_id}",
                        title=extracted_title,
                        company=extracted_company,
                        location="Remote" if is_remote else "Unspecified",
                        is_remote=is_remote,
                        remote_scope="Remote" if is_remote else "Unspecified",
                        url=app_url,
                        raw_url=app_url,
                        description=text[:2500],
                        source="twitter",
                        posted_at=datetime.now(timezone.utc),
                        tags=["Twitter / X", f"@{author_handle}", "#hiring"],
                    )
                    postings.append(posting)
        except Exception:
            pass

        return postings

    def _extract_title_and_company(self, text: str, default_company: str) -> Tuple[str, str]:
        """Heuristically extracts job title and hiring company from tweet text."""
        # Clean HTML tags and excessive whitespace
        clean_text = re.sub(r"<[^>]+>", " ", text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        company = default_company
        title = "Hiring Announcement"

        # Check for patterns like "Hiring: [Role]" or "[Role] at [Company]"
        hiring_patterns = [
            r"(?:we(?:'re| are)? hiring|looking for|opening for)\s+(?:a|an)?\s*([A-Za-z0-9\s\/\-\+]{4,45}?)(?:\s+at\s+([A-Za-z0-9\s]{2,30}))?(?:[.,!|\n]|$)",
            r"([A-Za-z0-9\s\/\-\+]{4,40})\s+(?:role|position|job)\s+(?:at|with)\s+([A-Za-z0-9\s]{2,30})",
            r"(?:hiring|wanted):\s*([A-Za-z0-9\s\/\-\+]{4,45})",
        ]

        for pat in hiring_patterns:
            m = re.search(pat, clean_text, re.IGNORECASE)
            if m:
                extracted_role = m.group(1).strip()
                # Ensure it's not a generic word
                if len(extracted_role) > 3 and not extracted_role.lower().startswith("http"):
                    title = extracted_role.title()
                if len(m.groups()) >= 2 and m.group(2):
                    extracted_comp = m.group(2).strip()
                    if len(extracted_comp) > 2:
                        company = extracted_comp
                break

        if title == "Hiring Announcement":
            # Fallback: take first 60 chars
            first_line = clean_text.split(".")[0].split("\n")[0][:60]
            if len(first_line) > 5:
                title = first_line

        return title, company

    def _extract_urls(self, text: str) -> List[str]:
        """Extracts embedded URLs (e.g. t.co or direct links) from tweet text."""
        urls = re.findall(r"https?://[^\s<>\"'{}|\\^`]+", text)
        clean_urls = []
        for u in urls:
            # Strip trailing punctuation
            u = u.rstrip(".,;!?)")
            if "pic.twitter.com" not in u and "pic.x.com" not in u:
                clean_urls.append(u)
        return clean_urls
