"""
Online Income Opportunities Data Models.
Standardized representation for non-traditional remote income opportunities,
including AI evaluation, data annotation, tutoring, research, proofreading,
user testing, transcription, virtual assistance, and flexible online work.
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SourceTrustTier(str, Enum):
    TIER_1_HIGHEST = "tier_1_highest"  # Official company portals, direct contractor hubs, universities
    TIER_2_GOOD = "tier_2_good"        # Established testing, tutoring, research platforms
    TIER_3_REVIEW = "tier_3_review"    # Curated aggregators, vetted RSS feeds
    TIER_4_LOW = "tier_4_low"          # Generic blogs, content farms, SEO side-hustle sites (rejected)


class OpportunityStatus(str, Enum):
    NEW = "new"
    VERIFIED = "verified"
    NEEDS_REVIEW = "needs_review"
    EXPIRED = "expired"
    REJECTED = "rejected"
    DISMISSED = "dismissed"


class GeographicScope(str, Enum):
    WORLDWIDE = "worldwide"
    COUNTRY_SPECIFIC = "country_specific"
    REGION_SPECIFIC = "region_specific"
    UNKNOWN = "unknown"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    UNKNOWN = "unknown"


class CompensationType(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ANNUAL = "annual"
    PER_TASK = "per_task"
    PER_PROJECT = "per_project"
    PER_SESSION = "per_session"
    COMMISSION = "commission"
    UNKNOWN = "unknown"


class CompensationDetails(BaseModel):
    """Structured compensation data."""
    min_pay: Optional[float] = None
    max_pay: Optional[float] = None
    currency: str = "USD"
    pay_period: Optional[str] = "hourly"
    pay_type: CompensationType = CompensationType.HOURLY
    compensation_verified: bool = False
    pay_rate_display: Optional[str] = None  # e.g. "$20–$25/hr", "$10–$50/test", "₦15,000/task"


class QualityBreakdown(BaseModel):
    """Component breakdown of deterministic quality score (0–10)."""
    source_trust_score: float = 0.0
    specificity_score: float = 0.0
    compensation_transparency_score: float = 0.0
    geographic_clarity_score: float = 0.0
    actionability_score: float = 0.0
    passed_quality_gate: bool = False
    reasons: List[str] = Field(default_factory=list)


class SideJobFitBreakdown(BaseModel):
    """Component breakdown of side-job fit score (0–10) for supplementary work."""
    asynchronous_flexibility_score: float = 0.0
    hours_commitment_score: float = 0.0
    task_structure_score: float = 0.0
    schedule_description: str = "Flexible"
    highlights: List[str] = Field(default_factory=list)


class OnlineIncomeOpportunity(BaseModel):
    """Normalized representation of a concrete flexible online income opportunity."""
    id: str
    fingerprint: str = ""
    title: str
    organization: str
    description: str = ""
    
    # Work-focused categories only
    category: str = "ai_evaluation"
    # Supported categories:
    # "ai_evaluation", "ai_training", "data_annotation", "research",
    # "academic_editing", "proofreading", "tutoring", "user_testing",
    # "transcription", "customer_support", "virtual_assistant",
    # "data_entry", "bookkeeping", "content_editorial", "expert_research",
    # "other_verified_remote_work"

    opportunity_type: str = "hourly"  # "hourly", "per_task", "contract", "study", "freelance_project", "part_time"
    url: str
    application_url: Optional[str] = None

    # Source & Trust Metadata
    source: str = "general"
    source_type: str = "direct_platform"  # "official_portal", "verified_platform", "aggregator", "custom"
    source_trust_tier: SourceTrustTier = SourceTrustTier.TIER_1_HIGHEST
    source_url: Optional[str] = None

    # Location & Geographic Eligibility
    location_eligibility: str = "Worldwide"
    geographic_scope: GeographicScope = GeographicScope.WORLDWIDE
    eligibility_status: EligibilityStatus = EligibilityStatus.ELIGIBLE
    country_restrictions: List[str] = Field(default_factory=list)
    eligible_countries: List[str] = Field(default_factory=list)
    is_remote: bool = True
    is_flexible: bool = True

    # Compensation
    compensation: CompensationDetails = Field(default_factory=CompensationDetails)
    estimated_pay_min: Optional[float] = None
    estimated_pay_max: Optional[float] = None
    pay_rate_display: Optional[str] = None
    pay_currency: str = "USD"
    pay_frequency: str = "hourly"

    # Work Requirements & Schedule
    experience_requirement: str = "none"  # "none", "beginner", "intermediate", "expert"
    time_commitment: str = "flexible"    # "flexible", "under_10_hrs", "10_to_20_hrs", "ad_hoc", "full_time"
    flexibility: str = "high"             # "high", "medium", "low"
    is_asynchronous: bool = True

    # Scores & Quality Metrics
    quality_score: float = 0.0
    side_job_fit_score: float = 0.0
    relevance_score: float = 0.0
    final_score: float = 0.0
    quality_breakdown: QualityBreakdown = Field(default_factory=QualityBreakdown)
    side_job_breakdown: SideJobFitBreakdown = Field(default_factory=SideJobFitBreakdown)

    # Verification, Status & Safety
    status: OpportunityStatus = OpportunityStatus.NEW
    verification_status: str = "needs_review"  # "verified_source", "needs_review", "risk_flagged", "rejected"
    is_verified: bool = True
    link_verification_status: Optional[str] = "active"
    legitimacy_indicators: List[str] = Field(default_factory=list)
    scam_risk_indicators: List[str] = Field(default_factory=list)
    rejection_reasons: List[str] = Field(default_factory=list)

    # Metadata & Tags
    highlights: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    date_discovered: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    date_published: Optional[datetime] = None


class IncomeMatchBreakdown(BaseModel):
    """Detailed score decomposition for transparency and 'Why This Is Worth Considering' bullets."""
    quality_score: float = 0.0
    side_job_fit_score: float = 0.0
    relevance_score: float = 0.0
    final_score: float = 0.0

    category_score: float = 0.0
    country_eligibility_score: float = 0.0
    compensation_score: float = 0.0
    flexibility_score: float = 0.0
    source_quality_score: float = 0.0
    ease_of_entry_score: float = 0.0

    passed_quality_gate: bool = True
    eligibility_status: str = "eligible"
    penalties_applied: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    rejection_reasons: List[str] = Field(default_factory=list)
    is_verified: bool = True


class ScoredOpportunity(BaseModel):
    """An income opportunity scored against candidate preferences."""
    opportunity: OnlineIncomeOpportunity
    score: float = 0.0  # 0.0 to 10.0 scale
    action: str = "discard"  # "discard", "low_match", "digest", "instant"
    breakdown: IncomeMatchBreakdown = Field(default_factory=IncomeMatchBreakdown)
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SourceTelemetry(BaseModel):
    """Granular health, conversion, and rejection breakdown per source connector."""
    source_name: str
    trust_tier: str = "tier_1_highest"
    status: str = "healthy"  # "healthy", "degraded", "error"
    discovered: int = 0
    duplicates_removed: int = 0
    hard_rejected: int = 0
    quality_rejected: int = 0
    ineligible: int = 0
    verification_failed: int = 0
    expired: int = 0
    verified: int = 0
    high_quality: int = 0
    alerted: int = 0
    latency_ms: float = 0.0
    last_crawled: Optional[datetime] = None
    error_message: Optional[str] = None


class IncomeCollectorHealth(BaseModel):
    """Backward-compatible health report for collector runners."""
    source_name: str
    status: str = "healthy"
    opportunities_found: int = 0
    latency_ms: float = 0.0
    last_crawled: Optional[datetime] = None
    error_message: Optional[str] = None
    telemetry: Optional[SourceTelemetry] = None


class IncomeRunSummary(BaseModel):
    """Summary of an online income opportunities discovery, quality gating, and evaluation run."""
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    total_fetched: int = 0
    unique_candidates: int = 0
    hard_rejected: int = 0
    quality_rejected: int = 0
    ineligible: int = 0
    verification_failed: int = 0
    expired_links_removed: int = 0
    discarded: int = 0
    low_matches: int = 0
    digest_matches: int = 0
    instant_matches: int = 0
    high_quality: int = 0
    emails_dispatched: int = 0
    risk_rejected: int = 0
    execution_time_seconds: float = 0.0
    source_health: List[IncomeCollectorHealth] = Field(default_factory=list)
    source_telemetry: Dict[str, SourceTelemetry] = Field(default_factory=dict)
    error_count: int = 0
