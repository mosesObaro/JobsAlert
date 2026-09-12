"""
Custom / Manual Online Income Opportunity Collector.
Allows candidates to enter one-off online gigs, micro-tasks, and opportunities
into data/custom_income_opportunities.json to be deduplicated, verified, scored, and alerted.
"""

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

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

CUSTOM_INCOME_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "custom_income_opportunities.json"


class CustomIncomeCollector(BaseIncomeCollector):
    """Loads manually entered income opportunities from data/custom_income_opportunities.json."""

    def __init__(self):
        super().__init__(name="custom", trust_tier=SourceTrustTier.TIER_2_GOOD)

    async def collect(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        all_opps: List[OnlineIncomeOpportunity] = []

        if not CUSTOM_INCOME_FILE.exists():
            return []

        try:
            with open(CUSTOM_INCOME_FILE, "r", encoding="utf-8") as f:
                raw_items = json.load(f)

            if not isinstance(raw_items, list):
                return []

            for idx, item in enumerate(raw_items):
                title = item.get("title", "").strip()
                org = item.get("organization", "Custom Opportunity").strip()
                category = item.get("category", "ai_evaluation").strip()
                opp_type = item.get("opportunity_type", "hourly")
                url = item.get("url", f"https://example.com/custom-income-{idx}")
                app_url = item.get("application_url", url)
                location = item.get("location_eligibility", "Worldwide")
                desc = item.get("description", "")
                p_min = float(item.get("estimated_pay_min", 0)) or None
                p_max = float(item.get("estimated_pay_max", 0)) or None
                p_display = item.get("pay_rate_display")

                comp_details = CompensationDetails(
                    min_pay=p_min,
                    max_pay=p_max,
                    currency="USD",
                    pay_period="hourly" if opp_type == "hourly" else "per_task",
                    pay_type=CompensationType.HOURLY if opp_type == "hourly" else CompensationType.PER_TASK,
                    pay_rate_display=p_display,
                )

                opp = OnlineIncomeOpportunity(
                    id=f"custom_income_{idx}_{abs(hash(url or title))}",
                    title=title,
                    organization=org,
                    category=category,
                    opportunity_type=opp_type,
                    url=url,
                    application_url=app_url,
                    source=self.name,
                    source_type="custom",
                    source_trust_tier=SourceTrustTier.TIER_2_GOOD,
                    location_eligibility=location,
                    geographic_scope=GeographicScope.WORLDWIDE if "worldwide" in location.lower() else GeographicScope.UNKNOWN,
                    eligible_countries=item.get("eligible_countries", ["Worldwide", "Nigeria"]),
                    country_restrictions=item.get("country_restrictions", []),
                    is_remote=True,
                    is_flexible=True,
                    description=desc[:3000],
                    compensation=comp_details,
                    estimated_pay_min=p_min,
                    estimated_pay_max=p_max,
                    pay_rate_display=p_display,
                    date_discovered=datetime.now(timezone.utc),
                    status=OpportunityStatus.NEW,
                    tags=["Manual / Custom", org],
                    verification_status="needs_review",
                    legitimacy_indicators=[f"Manually added by user ({org})"]
                )
                all_opps.append(opp)
        except Exception as e:
            self.health.error_message = str(e)

        return all_opps


def add_custom_income_opportunity(
    title: str,
    organization: str,
    category: str = "ai_evaluation",
    url: str = "",
    application_url: str = "",
    location_eligibility: str = "Worldwide",
    description: str = "",
    estimated_pay_min: Optional[float] = None,
    estimated_pay_max: Optional[float] = None,
    pay_rate_display: Optional[str] = None,
    opportunity_type: str = "hourly",
) -> dict:
    """Helper to append a custom income opportunity to data/custom_income_opportunities.json."""
    CUSTOM_INCOME_FILE.parent.mkdir(parents=True, exist_ok=True)
    items = []
    if CUSTOM_INCOME_FILE.exists():
        try:
            with open(CUSTOM_INCOME_FILE, "r", encoding="utf-8") as f:
                items = json.load(f)
        except Exception:
            items = []

    new_entry = {
        "title": title,
        "organization": organization,
        "category": category,
        "url": url or f"https://example.com/income/{organization.lower()}-{abs(hash(title))}",
        "application_url": application_url or url,
        "location_eligibility": location_eligibility,
        "description": description,
        "estimated_pay_min": estimated_pay_min,
        "estimated_pay_max": estimated_pay_max,
        "pay_rate_display": pay_rate_display,
        "opportunity_type": opportunity_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    items.insert(0, new_entry)

    with open(CUSTOM_INCOME_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

    return new_entry
