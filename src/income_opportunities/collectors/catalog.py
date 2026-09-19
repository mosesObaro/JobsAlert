"""
Curated Income Platform Catalogue Collectors.
Serves hand-maintained platform listings from config/income_catalog.yaml. Nothing
here is fetched live: each entry records when it was last reviewed, and entries
older than `catalog_stale_after_days` are flagged for review.
"""

from __future__ import annotations
from datetime import date, datetime, timezone
from typing import List, Optional

import yaml

from src import paths
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


def load_catalog() -> List[dict]:
    """Entries from config/income_catalog.yaml."""
    with open(paths.income_catalog_path(), "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("platforms", [])
    if not isinstance(entries, list):
        raise ValueError("income catalogue: 'platforms' must be a list")
    return entries


def _reviewed_on(entry: dict) -> Optional[date]:
    value = entry.get("last_reviewed")
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


class CatalogIncomeCollector(BaseIncomeCollector):
    """Serves the catalogue entries whose `collector` field matches this source."""

    config_key = ""
    default_tier = SourceTrustTier.TIER_2_GOOD

    def __init__(self):
        super().__init__(name=self.config_key, trust_tier=self.default_tier)

    def is_enabled(self, config: OnlineIncomeConfig) -> bool:
        return getattr(config.sources, self.config_key).enabled

    async def collect(self, config: OnlineIncomeConfig) -> List[OnlineIncomeOpportunity]:
        sub_cfg = getattr(config.sources, self.config_key)
        if not sub_cfg.enabled:
            return []
        entries = [e for e in load_catalog() if e.get("collector") == self.config_key]
        if sub_cfg.platforms:
            entries = [e for e in entries if any(p in str(e.get("platform_id", "")) for p in sub_cfg.platforms)]
        today = datetime.now(timezone.utc).date()
        opportunities = [self._to_opportunity(e, today, config.catalog_stale_after_days) for e in entries]
        return opportunities[: sub_cfg.limit_items or 30]

    def _to_opportunity(self, entry: dict, today: date, stale_after_days: int) -> OnlineIncomeOpportunity:
        reviewed = _reviewed_on(entry)
        overdue = reviewed is None or (today - reviewed).days > stale_after_days
        pay_period = entry.get("pay_period") or "hourly"
        location = entry.get("location_eligibility") or "Worldwide"
        url = entry["url"]
        tier_value = entry.get("trust_tier") or self.default_tier.value
        return OnlineIncomeOpportunity(
            id=entry["id"],
            title=entry["title"],
            organization=entry["organization"],
            description=entry.get("description", ""),
            category=entry.get("category", "other_verified_remote_work"),
            opportunity_type=entry.get("opportunity_type", "hourly"),
            url=url,
            application_url=entry.get("application_url") or url,
            source=self.name,
            source_type="catalog",
            source_trust_tier=SourceTrustTier(tier_value),
            source_url=url,
            location_eligibility=location,
            geographic_scope=GeographicScope.WORLDWIDE if "worldwide" in location.lower() else GeographicScope.UNKNOWN,
            eligible_countries=entry.get("eligible_countries") or [],
            country_restrictions=entry.get("country_restrictions") or [],
            is_remote=True,
            is_flexible=entry.get("flexibility", "high") != "low",
            is_asynchronous=bool(entry.get("is_asynchronous", True)),
            compensation=CompensationDetails(
                min_pay=entry.get("pay_min"),
                max_pay=entry.get("pay_max"),
                currency=entry.get("pay_currency") or "USD",
                pay_period=pay_period,
                pay_type=CompensationType.HOURLY if pay_period == "hourly" else CompensationType.PER_TASK,
                compensation_verified=False,
                pay_rate_display=entry.get("pay_rate_display"),
            ),
            estimated_pay_min=entry.get("pay_min"),
            estimated_pay_max=entry.get("pay_max"),
            pay_rate_display=entry.get("pay_rate_display"),
            pay_currency=entry.get("pay_currency") or "USD",
            pay_frequency=pay_period,
            experience_requirement=entry.get("experience_requirement", "none"),
            time_commitment=entry.get("time_commitment", "flexible"),
            flexibility=entry.get("flexibility", "high"),
            status=OpportunityStatus.NEW,
            tags=entry.get("tags") or [],
            verification_status="needs_review",
            last_reviewed=reviewed.isoformat() if reviewed else None,
            review_overdue=overdue,
        )


class AIEvaluationCollector(CatalogIncomeCollector):
    """AI training, evaluation and data annotation platforms."""
    config_key = "ai_evaluation"
    default_tier = SourceTrustTier.TIER_1_HIGHEST


class UserTestingCollector(CatalogIncomeCollector):
    """Usability testing and paid research study platforms."""
    config_key = "user_testing"
    default_tier = SourceTrustTier.TIER_2_GOOD


class AcademicTutoringCollector(CatalogIncomeCollector):
    """Academic proofreading, editing and online tutoring platforms."""
    config_key = "academic_tutoring"
    default_tier = SourceTrustTier.TIER_1_HIGHEST


class TranscriptionSupportCollector(CatalogIncomeCollector):
    """Transcription, virtual assistance and remote support platforms."""
    config_key = "transcription_support"
    default_tier = SourceTrustTier.TIER_2_GOOD
