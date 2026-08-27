"""
Generic RSS / Atom Feed Collector.
Parses company careers RSS feeds, Workday RSS endpoints, and public blogs.
"""

from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List
from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting


class RSSCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="rss")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        feeds = [f for f in config.sources.rss_feeds if f.enabled]
        if not feeds:
            return []

        all_jobs: List[JobPosting] = []

        async with self.create_http_client(timeout=10.0) as client:
            for feed in feeds:
                try:
                    resp = await client.get(feed.url)
                    if resp.status_code != 200:
                        continue

                    # Parse XML tree
                    root = ET.fromstring(resp.text)
                    # Check for RSS item or Atom entry
                    items = root.findall(".//item")
                    if not items:
                        # Atom entries
                        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

                    for item in items:
                        title_el = item.find("title") or item.find("{http://www.w3.org/2005/Atom}title")
                        link_el = item.find("link") or item.find("{http://www.w3.org/2005/Atom}link")
                        desc_el = (
                            item.find("description")
                            or item.find("summary")
                            or item.find("{http://www.w3.org/2005/Atom}summary")
                            or item.find("{http://www.w3.org/2005/Atom}content")
                        )
                        date_el = (
                            item.find("pubDate")
                            or item.find("published")
                            or item.find("{http://www.w3.org/2005/Atom}published")
                            or item.find("{http://www.w3.org/2005/Atom}updated")
                        )

                        title = title_el.text.strip() if title_el is not None and title_el.text else "Job Opening"
                        link = ""
                        if link_el is not None:
                            link = link_el.text or link_el.attrib.get("href", "")

                        raw_desc = desc_el.text if desc_el is not None and desc_el.text else ""
                        clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                        clean_desc = " ".join(clean_desc.split())

                        posted_at = None
                        if date_el is not None and date_el.text:
                            try:
                                posted_at = parsedate_to_datetime(date_el.text)
                            except Exception:
                                try:
                                    posted_at = datetime.fromisoformat(date_el.text.replace("Z", "+00:00"))
                                except Exception:
                                    pass

                        loc_lower = f"{title} {clean_desc}".lower()
                        is_remote = "remote" in loc_lower or "anywhere" in loc_lower
                        remote_scope = "Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else ("Remote" if is_remote else "On-Site")

                        posting = JobPosting(
                            id=f"rss_{feed.name}_{abs(hash(link or title))}",
                            title=title,
                            company=feed.name,
                            location="Remote" if is_remote else "Company Office",
                            is_remote=is_remote,
                            remote_scope=remote_scope,
                            url=link,
                            raw_url=link,
                            description=clean_desc[:3000],
                            source="rss",
                            posted_at=posted_at,
                            tags=[feed.name]
                        )
                        all_jobs.append(posting)
                except Exception:
                    continue

        return all_jobs
