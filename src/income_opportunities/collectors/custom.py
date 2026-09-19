"""
Custom / Manual Online Income Opportunity Collector.
One-off gigs entered by hand in data/custom_income_opportunities.json, then
deduplicated, screened, scored and alerted like any other source.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from src import paths
from src.collectors.base import optional_float
from src.deduplication import stable_hash
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
from src.storage import read_json, write_json_atomic


def custom_income_file():
    return paths.data_file(paths.CUSTOM_INCOME)


def load_custom_income() -> List[dict]:
    items = read_json(custom_income_file(), [])
    return items if isinstance(items, list) else []


def custom_income_id(entry: dict) -> str:
    """Stable id: the one stored at creation, else derived from the entry's content."""
    return str(entry.get("id") or stable_hash(entry.get("url"), entry.get("organization"), entry.get("title")))


class CustomIncomeCollector(BaseIncomeCollector):
    """Loads manually entered income opportunities from data/custom_income_opportunities.json."""

    expects_results = False  # an empty custom list is normal

    def __init__(self):
        super().__init__(name="custom", trust_tier=SourceTrustTier.TIER_2_GOOD)

    def is_enabled(self, config: OnlineIncomeConfig) -> bool:
        return config.sources.custom.enabled

    async def collect(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        opportunities: List[OnlineIncomeOpportunity] = []
        for position, item in enumerate(load_custom_income()):
            try:
                opportunities.append(self._to_opportunity(item))
            except Exception as exc:  # one malformed entry must not hide the others
                self.note(f"custom entry #{position + 1}: {type(exc).__name__}: {exc}")
        return opportunities

    def _to_opportunity(self, item: dict) -> OnlineIncomeOpportunity:
        title = (item.get("title") or "").strip()
        if not title:
            raise ValueError("missing title")
        org = (item.get("organization") or "Custom Opportunity").strip()
        opp_type = item.get("opportunity_type") or "hourly"
        url = (item.get("url") or "").strip()
        location = item.get("location_eligibility") or "Worldwide"
        pay_min = optional_float(item.get("estimated_pay_min"))
        pay_max = optional_float(item.get("estimated_pay_max"))
        currency = (item.get("pay_currency") or "USD").upper()
        period = "hourly" if opp_type == "hourly" else "per_task"
        return OnlineIncomeOpportunity(
            id=f"custom_income_{custom_income_id(item)}",
            title=title,
            organization=org,
            category=(item.get("category") or "general_flexible").strip(),
            opportunity_type=opp_type,
            url=url,
            application_url=(item.get("application_url") or url).strip(),
            source=self.name,
            source_type="custom",
            source_trust_tier=SourceTrustTier.TIER_2_GOOD,
            location_eligibility=location,
            geographic_scope=GeographicScope.WORLDWIDE if "worldwide" in location.lower() else GeographicScope.UNKNOWN,
            eligible_countries=item.get("eligible_countries") or [],
            country_restrictions=item.get("country_restrictions") or [],
            is_remote=True,
            is_flexible=True,
            description=(item.get("description") or "")[:3000],
            compensation=CompensationDetails(
                min_pay=pay_min,
                max_pay=pay_max,
                currency=currency,
                pay_period=period,
                pay_type=CompensationType.HOURLY if opp_type == "hourly" else CompensationType.PER_TASK,
                pay_rate_display=item.get("pay_rate_display"),
            ),
            estimated_pay_min=pay_min,
            estimated_pay_max=pay_max,
            pay_rate_display=item.get("pay_rate_display"),
            pay_currency=currency,
            pay_frequency=period,
            status=OpportunityStatus.NEW,
            tags=["Manual / Custom", org],
            verification_status="needs_review",
        )


def add_custom_income_opportunity(
    title: str,
    organization: str,
    category: str = "general_flexible",
    url: str = "",
    application_url: str = "",
    location_eligibility: str = "Worldwide",
    description: str = "",
    estimated_pay_min: Optional[float] = None,
    estimated_pay_max: Optional[float] = None,
    pay_rate_display: Optional[str] = None,
    opportunity_type: str = "hourly",
    pay_currency: str = "USD",
) -> dict:
    """Adds a custom income opportunity (newest first) and returns the stored entry."""
    items = load_custom_income()
    new_entry: dict[str, Any] = {
        "id": uuid.uuid4().hex[:16],
        "title": title,
        "organization": organization,
        "category": category,
        "url": url,
        "application_url": application_url or url,
        "location_eligibility": location_eligibility,
        "description": description,
        "estimated_pay_min": estimated_pay_min,
        "estimated_pay_max": estimated_pay_max,
        "pay_rate_display": pay_rate_display,
        "pay_currency": (pay_currency or "USD").upper(),
        "opportunity_type": opportunity_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    items.insert(0, new_entry)
    write_json_atomic(custom_income_file(), items)
    return new_entry


def delete_custom_income_opportunity(entry_id: str) -> Optional[dict]:
    """Removes the custom income entry with this id; returns it, or None when not found."""
    items = load_custom_income()
    for position, entry in enumerate(items):
        if custom_income_id(entry) == entry_id:
            removed = items.pop(position)
            write_json_atomic(custom_income_file(), items)
            return removed
    return None
