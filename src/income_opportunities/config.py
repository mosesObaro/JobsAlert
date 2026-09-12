"""
Online Income Opportunities Configuration Schema.
Supports work categories, country eligibility, compensation floors, flexibility filters,
source trust tiers, quality gates, and multi-factor scoring weights.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class IncomeSourceSubConfig(BaseModel):
    enabled: bool = True
    trust_tier: str = "tier_1_highest"
    platforms: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    limit_items: int = 30


class IncomeRSSFeedConfig(BaseModel):
    name: str
    url: str
    category: str = "other_verified_remote_work"
    trust_tier: str = "tier_3_review"
    enabled: bool = True


class IncomeSourcesConfig(BaseModel):
    ai_evaluation: IncomeSourceSubConfig = Field(
        default_factory=lambda: IncomeSourceSubConfig(
            enabled=True,
            trust_tier="tier_1_highest",
            platforms=["dataannotation", "outlier", "oneforma", "telus", "appen"]
        )
    )
    user_testing: IncomeSourceSubConfig = Field(
        default_factory=lambda: IncomeSourceSubConfig(
            enabled=True,
            trust_tier="tier_2_good",
            platforms=["usertesting", "testbirds", "respondent", "prolific"]
        )
    )
    academic_tutoring: IncomeSourceSubConfig = Field(
        default_factory=lambda: IncomeSourceSubConfig(
            enabled=True,
            trust_tier="tier_1_highest",
            platforms=["cambridge_proofreading", "scribbr", "preply", "cambly", "academic_positions"]
        )
    )
    transcription_support: IncomeSourceSubConfig = Field(
        default_factory=lambda: IncomeSourceSubConfig(
            enabled=True,
            trust_tier="tier_2_good",
            platforms=["rev", "gotranscript", "modsquad", "belay", "time_etc"]
        )
    )
    rss_feeds: List[IncomeRSSFeedConfig] = Field(default_factory=list)
    custom: IncomeSourceSubConfig = Field(
        default_factory=lambda: IncomeSourceSubConfig(enabled=True, trust_tier="tier_2_good")
    )


class IncomeScoringWeightsConfig(BaseModel):
    quality: float = 30.0
    relevance: float = 25.0
    side_job_fit: float = 20.0
    country_eligibility: float = 15.0
    compensation: float = 10.0

    # Backward compatibility aliases
    legitimacy_verification: float = 20.0
    flexibility_time: float = 15.0
    category_alignment: float = 15.0
    ease_and_recurring: float = 5.0


class OnlineIncomeConfig(BaseModel):
    """Complete configuration settings for high-precision Online Income Opportunities scout."""
    enabled: bool = True
    include_in_daily_digest: bool = True
    candidate_name: str = "Candidate"
    eligible_countries: List[str] = Field(
        default_factory=lambda: ["Nigeria", "Worldwide", "Global", "All Countries", "Africa"]
    )
    
    # Work-focused legitimate categories only
    preferred_categories: List[str] = Field(
        default_factory=lambda: [
            "ai_evaluation",
            "ai_training",
            "data_annotation",
            "research",
            "academic_editing",
            "proofreading",
            "tutoring",
            "user_testing",
            "transcription",
            "customer_support",
            "virtual_assistant",
            "data_entry",
            "bookkeeping",
            "content_editorial",
            "expert_research",
            "other_verified_remote_work",
        ]
    )
    
    # Excluded noise categories and non-work schemes
    excluded_categories: List[str] = Field(
        default_factory=lambda: [
            "passive_income",
            "side_hustle",
            "online_business",
            "make_money_online",
            "entrepreneurship",
            "affiliate_marketing",
            "dropshipping",
            "ecommerce",
            "courses_coaching",
            "mlm",
            "pyramid_scheme",
            "trading",
            "crypto",
            "gambling",
            "betting",
            "software_dev",
            "tech_engineering",
            "marketing",
            "advertising",
            "sales",
            "social_media_promotion",
        ]
    )

    # Quality Gate & Scoring Thresholds
    minimum_quality_score: float = 7.0
    minimum_side_job_fit_score: float = 6.0
    minimum_final_score: float = 7.5
    minimum_score: float = 7.5  # backward-compatibility
    instant_alert_score: float = 9.0
    max_digest_items: int = 5  # Precision cap: never flood digest with mediocre opportunities
    
    # Source Trust & Eligibility Requirements
    min_source_trust_tier: str = "tier_3_review"  # tier_1, tier_2, tier_3 accepted; tier_4 rejected
    require_verified_source: bool = True
    reject_unknown_eligibility: bool = False
    reject_unknown_compensation: bool = False
    
    # Financial & Scheduling Preferences
    minimum_hourly_rate_usd: float = 8.0
    preferred_flexibility: str = "high"  # "high", "medium", "any"
    maximum_hours_per_week: int = 25
    allow_asynchronous_only: bool = False
    
    preferred_payment_methods: List[str] = Field(
        default_factory=lambda: ["PayPal", "Direct Deposit", "Payoneer", "Wise", "Bank Transfer", "Stripe"]
    )
    preferred_currencies: List[str] = Field(
        default_factory=lambda: ["USD", "EUR", "GBP", "NGN"]
    )
    require_link_verification: bool = True
    scoring_weights: IncomeScoringWeightsConfig = Field(default_factory=IncomeScoringWeightsConfig)
    sources: IncomeSourcesConfig = Field(default_factory=IncomeSourcesConfig)
