"""
Hacker News 'Who is Hiring?' Collector.
Parses monthly high-signal hiring threads from Hacker News via Algolia API.
"""

from __future__ import annotations
import html
import re
from datetime import datetime, timezone
from typing import List
from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting


class HackerNewsCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="hackernews")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.hackernews.enabled:
            return []

        all_jobs: List[JobPosting] = []

        async with self.create_http_client(timeout=15.0) as client:
            try:
                # 1. Locate the latest "Ask HN: Who is hiring?" thread
                search_url = "https://hn.algolia.com/api/v1/search?query=Ask%20HN:%20Who%20is%20hiring&tags=story&hitsPerPage=2"
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    return []
                stories = resp.json().get("hits", [])
                if not stories:
                    return []

                # Find the story that actually has "who is hiring" in title
                target_story = None
                for s in stories:
                    if "who is hiring?" in s.get("title", "").lower():
                        target_story = s
                        break
                if not target_story:
                    target_story = stories[0]

                story_id = target_story.get("objectID")

                # 2. Fetch top-level hiring comments
                comments_url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&hitsPerPage=60"
                c_resp = await client.get(comments_url)
                if c_resp.status_code != 200:
                    return []

                comments = c_resp.json().get("hits", [])

                for item in comments:
                    comment_text = item.get("comment_text", "")
                    if not comment_text:
                        continue

                    # Unescape HTML entities & clean formatting
                    unescaped = html.unescape(comment_text)
                    clean_text = re.sub(r"<p>", "\n", unescaped)
                    clean_text = re.sub(r"<[^>]+>", " ", clean_text)
                    lines = [line.strip() for line in clean_text.split("\n") if line.strip()]
                    if not lines:
                        continue

                    header_line = lines[0]
                    # Common header format: "Stripe | Senior Infrastructure Engineer | Remote (US/EU) | Full-time"
                    parts = [p.strip() for p in header_line.split("|")]
                    if len(parts) >= 2:
                        company = parts[0]
                        title = parts[1]
                        location = parts[2] if len(parts) >= 3 else "Remote"
                    else:
                        company = "Hacker News Startup"
                        title = header_line[:60]
                        location = "Remote"

                    comment_id = item.get("objectID", "")
                    job_url = f"https://news.ycombinator.com/item?id={comment_id}"

                    loc_lower = location.lower()
                    full_lower = clean_text.lower()
                    is_remote = "remote" in loc_lower or "remote" in full_lower or "anywhere" in loc_lower
                    remote_scope = "Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else ("Remote" if is_remote else "On-Site")

                    # Extract salary if present
                    salary_matches = re.findall(r"\$(\d{2,3})k?\s*[-–]\s*\$?(\d{2,3})k", full_lower)
                    s_min, s_max = None, None
                    if salary_matches:
                        try:
                            s_min = float(salary_matches[0][0]) * 1000
                            s_max = float(salary_matches[0][1]) * 1000
                        except Exception:
                            pass

                    posted_at = None
                    created_at_i = item.get("created_at_i")
                    if created_at_i:
                        try:
                            posted_at = datetime.fromtimestamp(created_at_i, tz=timezone.utc)
                        except Exception:
                            pass

                    posting = JobPosting(
                        id=f"hn_{comment_id}",
                        title=title[:100],
                        company=company[:60],
                        location=location[:100],
                        is_remote=is_remote,
                        remote_scope=remote_scope,
                        url=job_url,
                        raw_url=job_url,
                        description=clean_text[:3000],
                        salary_min=s_min,
                        salary_max=s_max,
                        source="hackernews",
                        posted_at=posted_at,
                        tags=["HN Who is Hiring", "Startup"]
                    )
                    all_jobs.append(posting)

            except Exception as e:
                self.health.error_message = str(e)

        return all_jobs
