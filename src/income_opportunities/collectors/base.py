"""
Online Income Opportunities Base Collector.
Abstract class defining collector interfaces, HTTP client handling, error tracking,
latency measurement, and standard health telemetry.
"""

from __future__ import annotations
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional
import httpx

from src.deduplication import canonicalize_url
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.deduplication import compute_opportunity_fingerprint
from src.income_opportunities.models import IncomeCollectorHealth, OnlineIncomeOpportunity

INCOME_USER_AGENT = "JobsAlert-IncomeScout/1.0 (+https://github.com/jobsalert/jobsalert)"


class BaseIncomeCollector(ABC):
    """Abstract base class for all online income opportunity sources."""

    def __init__(self, name: str):
        self.name = name
        self.health = IncomeCollectorHealth(source_name=name)

    @abstractmethod
    async def collect(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        """Fetches raw opportunities and transforms them into standardized OnlineIncomeOpportunity instances."""
        pass

    async def execute(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        """Runs the collection pipeline with latency timing, error isolation, and fingerprint computation."""
        start_time = time.perf_counter()
        self.health.last_crawled = datetime.now(timezone.utc)

        try:
            opportunities = await self.collect(config)
            # Ensure every opportunity has canonical URL and deterministic fingerprint
            for opp in opportunities:
                opp.url = canonicalize_url(opp.url)
                if not opp.fingerprint:
                    opp.fingerprint = compute_opportunity_fingerprint(
                        organization=opp.organization,
                        title=opp.title,
                        category=opp.category,
                        reference_id=opp.id,
                        canonical_url=opp.url
                    )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.health.latency_ms = round(elapsed_ms, 2)
            self.health.opportunities_found = len(opportunities)
            self.health.status = "healthy"
            self.health.error_message = None
            return opportunities
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            self.health.latency_ms = round(elapsed_ms, 2)
            self.health.status = "error"
            self.health.error_message = str(e)
            return []

    def create_http_client(self, timeout: float = 12.0) -> httpx.AsyncClient:
        """Returns an async HTTP client with standard User-Agent, headers, and redirects enabled."""
        headers = {
            "User-Agent": INCOME_USER_AGENT,
            "Accept": "application/json, text/html, application/xhtml+xml, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        return httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True)
