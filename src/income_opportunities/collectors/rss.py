"""
Online Income Opportunities RSS / Syndication Collector.
Parses configured RSS/Atom feeds of flexible online work and drops non-work
articles and scams early with the HardRejectionClassifier.
"""

from __future__ import annotations
import xml.etree.ElementTree as ET
from typing import List

from src.deduplication import stable_hash
from src.feeds import parse_feed, strip_html
from src.income_opportunities.collectors.base import BaseIncomeCollector
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import (
    GeographicScope,
    OnlineIncomeOpportunity,
    OpportunityStatus,
    SourceTrustTier,
)
from src.income_opportunities.verifier import HardRejectionClassifier


class IncomeRSSCollector(BaseIncomeCollector):
    """Parses configured RSS and Atom feeds for concrete flexible online gigs."""

    def __init__(self):
        super().__init__(name="income_rss", trust_tier=SourceTrustTier.TIER_3_REVIEW)

    def is_enabled(self, config: OnlineIncomeConfig) -> bool:
        return any(feed.enabled for feed in config.sources.rss_feeds)

    async def collect(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        feeds = [f for f in config.sources.rss_feeds if f.enabled]
        all_opps: List[OnlineIncomeOpportunity] = []

        async with self.create_http_client(timeout=10.0, accept="application/rss+xml, application/atom+xml, text/xml, */*") as client:
            for feed in feeds:
                try:
                    resp = await client.get(feed.url)
                except Exception as exc:
                    self.note(f"income_rss/{feed.name}: {type(exc).__name__}")
                    continue
                if not self.accept(resp, f"income_rss/{feed.name}"):
                    continue
                try:
                    items = parse_feed(resp.text)
                except ET.ParseError as exc:
                    self.note(f"income_rss/{feed.name}: invalid XML ({exc})")
                    continue

                for item in items:
                    description = strip_html(item.summary)
                    text = f"{item.title} {description}".lower()
                    is_remote = "remote" in text or "anywhere" in text or "worldwide" in text
                    location = "Worldwide" if ("worldwide" in text or "global" in text) else ("Remote" if is_remote else "Unspecified")
                    opp = OnlineIncomeOpportunity(
                        id=f"rss_{feed.name}_{stable_hash(item.guid or item.link or item.title)}",
                        title=item.title or "Income Opportunity",
                        organization=feed.name,
                        description=description[:3000],
                        category=feed.category or "other_verified_remote_work",
                        url=item.link,
                        application_url=item.link,
                        source=self.name,
                        source_type="aggregator",
                        source_trust_tier=SourceTrustTier.TIER_3_REVIEW,
                        source_url=feed.url,
                        location_eligibility=location,
                        geographic_scope=GeographicScope.WORLDWIDE if location == "Worldwide" else GeographicScope.UNKNOWN,
                        is_remote=is_remote,
                        is_flexible=True,
                        status=OpportunityStatus.NEW,
                        date_published=item.published,
                        tags=["RSS", feed.name],
                        verification_status="needs_review",
                    )
                    is_rejected, _reasons = HardRejectionClassifier.evaluate(opp)
                    if not is_rejected:
                        all_opps.append(opp)
        return all_opps
