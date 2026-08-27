"""
Lever Public Postings API Collector.
Fetches verified direct ATS job postings from api.lever.co endpoints.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import List
from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting


class LeverCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="lever")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.lever.enabled:
            return []

        companies = config.sources.lever.companies
        all_jobs: List[JobPosting] = []

        async with self.create_http_client(timeout=10.0) as client:
            for company_slug in companies:
                if not company_slug:
                    continue
                url = f"https://api.lever.co/v0/postings/{company_slug.strip().lower()}?mode=json"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue
                    postings = resp.json()
                    if not isinstance(postings, list):
                        continue

                    for item in postings:
                        job_id = item.get("id", "")
                        title = item.get("text", "").strip()
                        categories = item.get("categories", {})
                        location = categories.get("location", "Remote") or "Remote"
                        team = categories.get("team", "")
                        commitment = categories.get("commitment", "Full-time")
                        desc = item.get("descriptionPlain", "") or item.get("additionalPlain", "")
                        hosted_url = item.get("hostedUrl", "")

                        loc_lower = location.lower()
                        is_remote = "remote" in loc_lower or "anywhere" in loc_lower or "worldwide" in loc_lower
                        remote_scope = "Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else ("Remote" if is_remote else "On-Site")

                        posted_at = None
                        created_ts = item.get("createdAt")
                        if created_ts:
                            try:
                                posted_at = datetime.fromtimestamp(created_ts / 1000.0, tz=timezone.utc)
                            except Exception:
                                pass

                        posting = JobPosting(
                            id=f"lever_{company_slug}_{job_id}",
                            title=title,
                            company=company_slug.capitalize(),
                            location=location,
                            is_remote=is_remote,
                            remote_scope=remote_scope,
                            url=hosted_url,
                            raw_url=hosted_url,
                            description=desc[:3000],
                            employment_type="full_time" if "full" in commitment.lower() else "contract",
                            source="lever",
                            posted_at=posted_at,
                            tags=[team] if team else []
                        )
                        all_jobs.append(posting)
                except Exception:
                    continue

        return all_jobs
