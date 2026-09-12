"""
Online Income Opportunities RSS / Syndication Collector.
Parses public RSS/Atom feeds configured for flexible micro-work, academic gigs, and research.
Applies early HardRejectionClassifier filtering to discard SEO articles and listicles.
"""

from __future__ import annotations
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List

from src.income_opportunities.collectors.base import BaseIncomeCollector
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import (
    CompensationDetails,
    CompensationType,
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

    async def collect(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        feeds = [f for f in config.sources.rss_feeds if f.enabled]
        if not feeds:
            return []

        all_opps: List[OnlineIncomeOpportunity] = []

        async with self.create_http_client(timeout=10.0) as client:
            for feed in feeds:
                try:
                    resp = await client.get(feed.url)
                    if resp.status_code != 200:
                        continue

                    root = ET.fromstring(resp.text)
                    items = root.findall(".//item")
                    if not items:
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

                        title = title_el.text.strip() if title_el is not None and title_el.text else "Income Opportunity"
                        link = ""
                        if link_el is not None:
                            link = link_el.text or link_el.attrib.get("href", "")

                        raw_desc = desc_el.text if desc_el is not None and desc_el.text else ""
                        clean_desc = re.sub(r"<[^>]+>", " ", raw_desc)
                        clean_desc = " ".join(clean_desc.split())

                        date_pub = None
                        if date_el is not None and date_el.text:
                            try:
                                date_pub = parsedate_to_datetime(date_el.text)
                            except Exception:
                                try:
                                    date_pub = datetime.fromisoformat(date_el.text.replace("Z", "+00:00"))
                                except Exception:
                                    pass

                        text_full = f"{title} {clean_desc}".lower()
                        is_remote = "remote" in text_full or "anywhere" in text_full or "worldwide" in text_full
                        location_eligibility = "Worldwide" if ("worldwide" in text_full or "global" in text_full) else ("Remote" if is_remote else "Unspecified")

                        opp = OnlineIncomeOpportunity(
                            id=f"rss_{feed.name}_{abs(hash(link or title))}",
                            title=title,
                            organization=feed.name,
                            description=clean_desc[:3000],
                            category=feed.category or "other_verified_remote_work",
                            url=link,
                            application_url=link,
                            source=self.name,
                            source_type="aggregator",
                            source_trust_tier=SourceTrustTier.TIER_3_REVIEW,
                            source_url=feed.url,
                            location_eligibility=location_eligibility,
                            geographic_scope=GeographicScope.WORLDWIDE if "worldwide" in location_eligibility.lower() else GeographicScope.UNKNOWN,
                            is_remote=is_remote,
                            is_flexible=True,
                            status=OpportunityStatus.NEW,
                            date_published=date_pub,
                            tags=["RSS", feed.name],
                            verification_status="needs_review",
                            legitimacy_indicators=[f"Aggregated from RSS feed ({feed.name})"]
                        )

                        # Filter out non-work advice and scam listicles immediately
                        is_rejected, reasons = HardRejectionClassifier.evaluate(opp)
                        if not is_rejected:
                            all_opps.append(opp)
                except Exception:
                    continue

        return all_opps
