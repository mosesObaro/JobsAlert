"""
JobsAlert Collector Base.
Shared runtime for job and income collectors: enable checks, HTTP clients, timing,
error capture and health reporting.
"""

from __future__ import annotations
import asyncio
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Awaitable, Generic, Iterable, List, Optional, TypeVar

import httpx

from src.deduplication import canonicalize_url, compute_job_fingerprint
from src.models import CrawlerHealth, JobPosting

USER_AGENT = "JobsAlert/2.0 (personal job alert scout)"

T = TypeVar("T")


class SourceCollector(ABC, Generic[T]):
    """Runs one source and reports its health.

    Status is "healthy", "degraded" (partial failure or no results), "error"
    (the whole source failed) or "disabled".
    """

    # An enabled source that returns nothing is reported as degraded.
    expects_results: bool = True

    def __init__(self, name: str):
        self.name = name
        self.issues: List[str] = []
        self.status = "healthy"
        self.error_message: Optional[str] = None
        self.latency_ms = 0.0
        self.item_count = 0
        self.last_crawled: Optional[datetime] = None

    def is_enabled(self, config: Any) -> bool:
        return True

    @abstractmethod
    async def collect(self, config: Any) -> List[T]:
        """Fetches items from the source."""

    def note(self, message: str) -> None:
        """Records a partial failure, e.g. one company's board returned 404."""
        self.issues.append(message)

    def accept(self, response: httpx.Response, label: str) -> bool:
        """True for HTTP 200; otherwise records the status as an issue."""
        if response.status_code == 200:
            return True
        self.note(f"{label}: HTTP {response.status_code}")
        return False

    def prepare(self, items: List[T]) -> None:
        """Normalizes collected items. Overridden per item type."""

    def publish_health(self) -> None:
        """Copies the run status into the collector's health model. Overridden per item type."""

    async def execute(self, config: Any) -> List[T]:
        start = time.perf_counter()
        self.issues = []
        self.last_crawled = datetime.now(timezone.utc)
        items: List[T] = []
        if not self.is_enabled(config):
            self.status, self.error_message = "disabled", None
        else:
            try:
                items = await self.collect(config)
            except Exception as exc:  # one broken source must not stop the others
                self.status, self.error_message = "error", f"{type(exc).__name__}: {exc}"[:300]
            else:
                self.prepare(items)
                if self.issues:
                    self.status = "degraded"
                    self.error_message = "; ".join(self.issues[:5])[:300]
                elif self.expects_results and not items:
                    self.status, self.error_message = "degraded", "No postings returned"
                else:
                    self.status, self.error_message = "healthy", None
        self.latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
        self.item_count = len(items)
        self.publish_health()
        return items

    def create_http_client(self, timeout: float = 12.0, accept: str = "application/json, text/plain, */*") -> httpx.AsyncClient:
        headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
        return httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True)


async def gather_limited(coroutines: Iterable[Awaitable[T]], limit: int) -> List[Any]:
    """asyncio.gather with at most `limit` coroutines in flight; exceptions are returned, not raised."""
    semaphore = asyncio.Semaphore(max(1, limit))

    async def run(coroutine: Awaitable[T]) -> T:
        async with semaphore:
            return await coroutine

    return await asyncio.gather(*(run(c) for c in coroutines), return_exceptions=True)


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def optional_float(value: Any) -> Optional[float]:
    """float(value), or None for missing, empty, zero or non-numeric values."""
    if value in (None, "", 0, "0"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


class BaseCollector(SourceCollector[JobPosting]):
    """Base class for job sources."""

    def __init__(self, name: str):
        super().__init__(name)
        self.health = CrawlerHealth(source_name=name)

    def prepare(self, items: List[JobPosting]) -> None:
        for job in items:
            job.url = canonicalize_url(job.url)
            if not job.fingerprint:
                job.fingerprint = compute_job_fingerprint(
                    company=job.company,
                    title=job.title,
                    location_type=job.remote_scope or job.location,
                    reference_id=job.id,
                    canonical_url=job.url,
                )

    def publish_health(self) -> None:
        self.health = CrawlerHealth(
            source_name=self.name,
            status=self.status,
            jobs_found=self.item_count,
            latency_ms=self.latency_ms,
            last_crawled=self.last_crawled,
            error_message=self.error_message,
        )
