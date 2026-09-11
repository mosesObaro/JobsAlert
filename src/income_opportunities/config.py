"""
Online Income Opportunities Configuration Schema.
Supports categories, country eligibility, compensation floors, flexibility filters,
source toggles, and multi-factor scoring weights.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class IncomeSourceSubConfig(BaseModel):
    enabled: bool = True
    platforms: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    limit_items: int = 30


class IncomeRSSFeedConfig(BaseModel):
    name: str
    url: str
    category: str = "general_flexible"
    enabled: bool = True


class IncomeSourcesConfig(BaseModel):
    ai_evaluation: IncomeSourceSubConfig = Field(
        default_factory=lambda: IncomeSourceSubConfig(
            enabled=True,
            platforms=["dataannotation", "outlier", "oneforma", "telus", "appen"]
        )
    )
    user_testing: IncomeSourceSubConfig = Field(
        default_factory=lambda: IncomeSourceSubConfig(
            enabled=True,
            platforms=["usertesting", "testbirds", "respondent", "prolific"]
        )
    )
    academic_tutoring: IncomeSourceSubConfig = Field(
        default_factory=lambda: IncomeSourceSubConfig(
            enabled=True,
            platforms=["cambridge_proofreading", "scribbr", "preply", "cambly", "academic_positions"]
        )
    )
    transcription_support: IncomeSourceSubConfig = Field(
        default_factory=lambda: IncomeSourceSubConfig(
            enabled=True,
            platforms=["rev", "gotranscript", "modsquad", "belay", "time_etc"]
        )
    )
    rss_feeds: List[IncomeRSSFeedConfig] = Field(default_factory=list)
    custom: IncomeSourceSubConfig = Field(default_factory=lambda: IncomeSourceSubConfig(enabled=True))


class IncomeScoringWeightsConfig(BaseModel):
    country_eligibility: float = 25.0
    compensation: float = 20.0
    legitimacy_verification: float = 20.0
    flexibility_time: float = 15.0
    category_alignment: float = 15.0
    ease_and_recurring: float = 5.0


class OnlineIncomeConfig(BaseModel):
    """Complete configuration settings for Online Income Opportunities scout."""
    enabled: bool = True
    candidate_name: str = "Candidate"
    eligible_countries: List[str] = Field(
        default_factory=lambda: ["Nigeria", "Worldwide", "Global", "All Countries", "Africa"]
    )
    preferred_categories: List[str] = Field(
        default_factory=lambda: [
            "ai_evaluation",
            "data_annotation",
            "research_assistant",
            "academic_proofreading",
            "online_tutoring",
            "transcription",
            "user_testing",
            "virtual_assistant",
            "remote_support",
            "data_entry",
            "bookkeeping",
            "survey_research",
            "content_editorial",
            "general_flexible"
        ]
    )
    excluded_categories: List[str] = Field(
        default_factory=lambda: [
            "software_dev",
            "tech_engineering",
            "marketing",
            "advertising",
            "sales",
            "social_media_promotion",
            "trading",
            "crypto",
            "gambling",
            "betting",
            "mlm"
        ]
    )
    minimum_score: float = 7.0
    instant_alert_score: float = 9.0
    minimum_hourly_rate_usd: float = 5.0
    preferred_flexibility: str = "high"  # "high", "medium", "any"
    maximum_hours_per_week: int = 25
    preferred_payment_methods: List[str] = Field(
        default_factory=lambda: ["PayPal", "Direct Deposit", "Payoneer", "Wise", "Bank Transfer", "Stripe"]
    )
    preferred_currencies: List[str] = Field(
        default_factory=lambda: ["USD", "EUR", "GBP", "NGN"]
    )
    require_link_verification: bool = True
    scoring_weights: IncomeScoringWeightsConfig = Field(default_factory=IncomeScoringWeightsConfig)
    sources: IncomeSourcesConfig = Field(default_factory=IncomeSourcesConfig)
