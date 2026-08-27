"""
JobsAlert Base Collector.
Abstract class defining collector interfaces, HTTP client handling, rate-limiting, and error tracking.
"""

from __future__ import annotations
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional
import httpx

from src.config import AppConfig
from src.deduplication import canonicalize_url, compute_job_fingerprint
from src.models import CrawlerHealth, JobPosting

USER_AGENT = "JobsAlert-CareerScout/1.0 (+https://github.com/jobsalert/jobsalert)"


class BaseCollector(ABC):
    """Abstract base class for all job data sources and ATS platforms."""

    def __init__(self, name: str):
        self.name = name
        self.health = CrawlerHealth(source_name=name)

    @abstractmethod
    async def collect(self, config: AppConfig) -> List[JobPosting]:
        """Fetches raw jobs and transforms them into standardized JobPosting instances."""
        pass

    async def execute(self, config: AppConfig) -> List[JobPosting]:
        """Runs the collection pipeline with latency timing, error trapping, and deduplication prep."""
        start_time = time.perf_counter()
        self.health.last_crawled = datetime.now(timezone.utc)

        try:
            jobs = await self.collect(config)
            # Ensure every job has canonical URL and deterministic fingerprint
            for job in jobs:
                job.url = canonicalize_url(job.url)
                if not job.fingerprint:
                    job.fingerprint = compute_job_fingerprint(
                        company=job.company,
                        title=job.title,
                        location_type=job.remote_scope or job.location,
                        reference_id=job.id,
                        canonical_url=job.url
                    )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.health.latency_ms = round(elapsed_ms, 2)
            self.health.jobs_found = len(jobs)
            self.health.status = "healthy"
            self.health.error_message = None
            return jobs
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.health.latency_ms = round(elapsed_ms, 2)
            self.health.status = "error"
            self.health.error_message = str(e)
            return []

    def create_http_client(self, timeout: float = 12.0) -> httpx.AsyncClient:
        """Returns an async HTTP client with standard User-Agent, headers, and redirects enabled."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        return httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True)
