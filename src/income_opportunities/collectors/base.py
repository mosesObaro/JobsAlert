"""
Online Income Opportunities Base Collector.
Income sources share the job collectors' runtime (timing, error capture, health);
this adds trust tiers, fingerprints and per-source telemetry.
"""

from __future__ import annotations
from typing import List

import httpx

from src.collectors.base import SourceCollector
from src.deduplication import canonicalize_url
from src.income_opportunities.deduplication import compute_opportunity_fingerprint
from src.income_opportunities.models import (
    IncomeCollectorHealth,
    OnlineIncomeOpportunity,
    SourceTelemetry,
    SourceTrustTier,
)


class BaseIncomeCollector(SourceCollector[OnlineIncomeOpportunity]):
    """Base class for online income opportunity sources."""

    def __init__(self, name: str, trust_tier: SourceTrustTier = SourceTrustTier.TIER_1_HIGHEST):
        super().__init__(name)
        self.trust_tier = trust_tier
        self.health = IncomeCollectorHealth(
            source_name=name,
            telemetry=SourceTelemetry(source_name=name, trust_tier=trust_tier.value),
        )

    def prepare(self, items: List[OnlineIncomeOpportunity]) -> None:
        for opp in items:
            opp.url = canonicalize_url(opp.url)
            if not opp.source_trust_tier:
                opp.source_trust_tier = self.trust_tier
            if not opp.fingerprint:
                opp.fingerprint = compute_opportunity_fingerprint(
                    organization=opp.organization,
                    title=opp.title,
                    category=opp.category,
                    reference_id=opp.id,
                    canonical_url=opp.url,
                )

    def publish_health(self) -> None:
        telemetry = SourceTelemetry(
            source_name=self.name,
            trust_tier=self.trust_tier.value,
            status=self.status,
            discovered=self.item_count,
            latency_ms=self.latency_ms,
            last_crawled=self.last_crawled,
            error_message=self.error_message,
        )
        self.health = IncomeCollectorHealth(
            source_name=self.name,
            status=self.status,
            opportunities_found=self.item_count,
            latency_ms=self.latency_ms,
            last_crawled=self.last_crawled,
            error_message=self.error_message,
            telemetry=telemetry,
        )

    def create_http_client(self, timeout: float = 12.0, accept: str = "application/json, text/html, application/xhtml+xml, */*") -> httpx.AsyncClient:
        return super().create_http_client(timeout=timeout, accept=accept)
