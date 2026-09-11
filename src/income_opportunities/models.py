"""
Online Income Opportunities Data Models.
Standardized representation for non-traditional remote income opportunities,
including AI evaluation, data annotation, tutoring, research, proofreading,
user testing, transcription, virtual assistance, and flexible online work.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class OnlineIncomeOpportunity(BaseModel):
    """Normalized representation of a flexible online income opportunity."""
    id: str
    fingerprint: str = ""
    title: str
    organization: str
    description: str = ""
    category: str = "general_flexible"
    # Supported categories:
    # "ai_evaluation", "data_annotation", "research_assistant", "academic_proofreading",
    # "online_tutoring", "transcription", "user_testing", "virtual_assistant",
    # "remote_support", "data_entry", "bookkeeping", "survey_research", "content_editorial", "general_flexible"

    opportunity_type: str = "hourly"  # "hourly", "per_task", "contract", "bounty", "part_time", "study"
    url: str
    application_url: Optional[str] = None

    # Location & Eligibility
    location_eligibility: str = "Worldwide"  # e.g., "Worldwide", "Nigeria Eligible", "Global (Select Countries)", "US/UK Only"
    country_restrictions: List[str] = Field(default_factory=list)  # explicitly restricted countries if known
    eligible_countries: List[str] = Field(default_factory=list)    # explicitly allowed countries if known
    is_remote: bool = True
    is_flexible: bool = True

    # Compensation
    estimated_pay_min: Optional[float] = None
    estimated_pay_max: Optional[float] = None
    pay_rate_display: Optional[str] = None  # e.g. "$15–$25/hr", "$5/audio hour", "$10–$50/test", "₦15,000/task"
    pay_currency: str = "USD"
    pay_frequency: str = "hourly"  # "hourly", "per_task", "weekly", "biweekly", "monthly", "per_milestone"

    # Work Requirements & Commitment
    experience_requirement: str = "none"  # "none", "beginner", "intermediate", "expert"
    time_commitment: str = "flexible"    # "flexible", "under_10_hrs", "10_to_20_hrs", "ad_hoc"
    flexibility: str = "high"             # "high", "medium", "low"

    # Source & Metadata
    source: str = "general"  # "ai_evaluation", "user_testing", "academic_tutoring", "transcription_support", "income_rss", "custom"
    tags: List[str] = Field(default_factory=list)
    date_discovered: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    date_published: Optional[datetime] = None

    # Verification & Safety
    verification_status: str = "needs_review"  # "verified_source", "needs_review", "risk_flagged", "rejected"
    legitimacy_indicators: List[str] = Field(default_factory=list)
    scam_risk_indicators: List[str] = Field(default_factory=list)
    is_verified: bool = True
    link_verification_status: Optional[str] = "active"


class IncomeMatchBreakdown(BaseModel):
    """Detailed score decomposition for transparency and 'Why This Is Worth Considering' bullets."""
    category_score: float = 0.0
    country_eligibility_score: float = 0.0
    compensation_score: float = 0.0
    flexibility_score: float = 0.0
    time_commitment_score: float = 0.0
    legitimacy_score: float = 0.0
    ease_of_entry_score: float = 0.0
    recurring_potential_score: float = 0.0
    source_quality_score: float = 0.0

    penalties_applied: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)  # 2-4 "Why this is worth considering" bullets
    risk_flags: List[str] = Field(default_factory=list)
    is_verified: bool = True


class ScoredOpportunity(BaseModel):
    """An income opportunity scored against user configuration."""
    opportunity: OnlineIncomeOpportunity
    score: float = 0.0  # 0.0 to 10.0 scale
    action: str = "discard"  # "discard" (0.0-4.9), "low_match" (5.0-6.9), "digest" (7.0-8.9), "instant" (9.0-10.0)
    breakdown: IncomeMatchBreakdown = Field(default_factory=IncomeMatchBreakdown)
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class IncomeCollectorHealth(BaseModel):
    """Health and telemetry report for an income opportunity source."""
    source_name: str
    status: str = "healthy"  # "healthy", "degraded", "error"
    opportunities_found: int = 0
    latency_ms: float = 0.0
    last_crawled: Optional[datetime] = None
    error_message: Optional[str] = None


class IncomeRunSummary(BaseModel):
    """Summary of an online income opportunities crawl & evaluation run."""
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    total_fetched: int = 0
    unique_candidates: int = 0
    discarded: int = 0
    low_matches: int = 0
    digest_matches: int = 0
    instant_matches: int = 0
    emails_dispatched: int = 0
    expired_links_removed: int = 0
    risk_rejected: int = 0
    execution_time_seconds: float = 0.0
    source_health: List[IncomeCollectorHealth] = Field(default_factory=list)
    error_count: int = 0
