"""
Remotive Remote Jobs API Collector.
Fetches curated remote technical listings from remotive.com.
"""

from __future__ import annotations
import re
from datetime import datetime
from typing import List, Tuple
from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.models import JobPosting


def parse_salary_string(salary_str: str) -> Tuple[float | None, float | None]:
    """Parses text like '$120k - $160k' or '110,000 - 140,000 USD' into min and max floats."""
    if not salary_str:
        return None, None
    clean = salary_str.replace(",", "").replace("$", "").lower()
    numbers = re.findall(r"\d+(?:\.\d+)?", clean)
    if not numbers:
        return None, None

    vals = []
    for n in numbers:
        val = float(n)
        if "k" in clean and val < 1000:
            val *= 1000
        vals.append(val)

    if len(vals) == 1:
        return vals[0], vals[0]
    return min(vals[0], vals[1]), max(vals[0], vals[1])


class RemotiveCollector(BaseCollector):
    def __init__(self):
        super().__init__(name="remotive")

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.remotive.enabled:
            return []

        category = config.sources.remotive.categories[0] if config.sources.remotive.categories else "software-dev"
        url = f"https://remotive.com/api/remote-jobs?category={category}&limit=50"
        all_jobs: List[JobPosting] = []

        async with self.create_http_client(timeout=12.0) as client:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return []
                data = resp.json()
                items = data.get("jobs", [])

                for item in items:
                    job_id = str(item.get("id", ""))
                    title = item.get("title", "").strip()
                    company = item.get("company_name", "").strip()
                    location = item.get("candidate_required_location", "Worldwide") or "Worldwide"
                    job_url = item.get("url", "")
                    salary_str = item.get("salary", "")
                    s_min, s_max = parse_salary_string(salary_str)

                    # Strip HTML from description
                    raw_desc = item.get("description", "")
                    clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                    clean_desc = " ".join(clean_desc.split())

                    posted_at = None
                    if item.get("publication_date"):
                        try:
                            posted_at = datetime.fromisoformat(item["publication_date"].replace("Z", "+00:00"))
                        except Exception:
                            pass

                    loc_lower = location.lower()
                    remote_scope = "Worldwide" if ("worldwide" in loc_lower or "anywhere" in loc_lower) else location

                    posting = JobPosting(
                        id=f"remotive_{job_id}",
                        title=title,
                        company=company,
                        location=f"Remote ({location})",
                        is_remote=True,
                        remote_scope=remote_scope,
                        url=job_url,
                        raw_url=job_url,
                        description=clean_desc[:3000],
                        salary_min=s_min,
                        salary_max=s_max,
                        source="remotive",
                        posted_at=posted_at,
                        tags=item.get("tags", [])
                    )
                    all_jobs.append(posting)
            except Exception as e:
                self.health.error_message = str(e)

        return all_jobs
