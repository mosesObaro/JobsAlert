"""
Generic RSS / Atom Feed Collector.
Parses company careers feeds, Workday RSS endpoints and job-board feeds.
"""

from __future__ import annotations
import xml.etree.ElementTree as ET
from typing import List

from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.deduplication import stable_hash
from src.feeds import parse_feed, strip_html
from src.models import JobPosting


class RSSCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="rss")

    def is_enabled(self, config: AppConfig) -> bool:
        return any(feed.enabled for feed in config.sources.rss_feeds)

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        feeds = [f for f in config.sources.rss_feeds if f.enabled]
        all_jobs: List[JobPosting] = []

        async with self.create_http_client(timeout=10.0, accept="application/rss+xml, application/atom+xml, text/xml, */*") as client:
            for feed in feeds:
                try:
                    resp = await client.get(feed.url)
                except Exception as exc:
                    self.note(f"rss/{feed.name}: {type(exc).__name__}")
                    continue
                if not self.accept(resp, f"rss/{feed.name}"):
                    continue
                try:
                    items = parse_feed(resp.text)
                except ET.ParseError as exc:
                    self.note(f"rss/{feed.name}: invalid XML ({exc})")
                    continue

                for item in items:
                    description = strip_html(item.summary)
                    text = f"{item.title} {description}".lower()
                    is_remote = "remote" in text or "anywhere" in text
                    all_jobs.append(JobPosting(
                        id=f"rss_{feed.name}_{stable_hash(item.guid or item.link or item.title)}",
                        title=item.title or "Job Opening",
                        company=feed.name,
                        location="Remote" if is_remote else "Company Office",
                        is_remote=is_remote,
                        remote_scope="Worldwide" if ("worldwide" in text or "anywhere" in text) else ("Remote" if is_remote else "On-Site"),
                        url=item.link,
                        raw_url=item.link,
                        description=description[:3000],
                        source="rss",
                        posted_at=item.published,
                        tags=[feed.name],
                    ))
        return all_jobs
