"""
JobsAlert Data Models.
Standardized representation for job postings, scoring results, configuration, and telemetry.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, HttpUrl


class JobPosting(BaseModel):
    """Normalized representation of a job posting across any ATS or board."""
    id: str
    fingerprint: str = ""
    title: str
    company: str
    location: str = "Unknown"
    is_remote: bool = False
    remote_scope: str = "Unspecified"  # e.g., "Worldwide", "US-Only", "EMEA", "Hybrid", "On-Site"
    country: Optional[str] = None
    url: str
    raw_url: Optional[str] = None
    description: str = ""
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: str = "USD"
    salary_period: str = "yearly"  # "yearly", "hourly", "monthly"
    employment_type: str = "full_time"  # "full_time", "contract", "internship", "part_time"
    seniority: Optional[str] = None  # "junior", "mid", "senior", "staff", "principal", "lead", "executive"
    posted_at: Optional[datetime] = None
    source: str  # "greenhouse", "lever", "ashby", "remotive", "remoteok", "arbeitnow", "jobicy", "hackernews", "rss", "twitter", "custom"
    tags: List[str] = Field(default_factory=list)
    is_verified: bool = True
    verification_status: Optional[str] = None  # "active", "expired", "404", "closed", "timeout", "unverified"


class MatchBreakdown(BaseModel):
    """Detailed score decomposition for transparency and 'Why You Match' bullets."""
    title_score: float = 0.0
    stack_score: float = 0.0
    location_score: float = 0.0
    compensation_score: float = 0.0
    company_score: float = 0.0
    recency_score: float = 0.0
    matched_must_have: List[str] = Field(default_factory=list)
    matched_nice_to_have: List[str] = Field(default_factory=list)
    missing_must_have: List[str] = Field(default_factory=list)
    penalties_applied: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    is_verified: bool = True


class ScoredJob(BaseModel):
    """A job posting scored against candidate profile criteria."""
    job: JobPosting
    score: float = 0.0  # 0.0 to 10.0 scale
    action: str = "discard"  # "discard" (0-4), "low_match" (5-6), "digest" (7-8), "instant" (9-10)
    breakdown: MatchBreakdown = Field(default_factory=MatchBreakdown)
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CrawlerHealth(BaseModel):
    """Health and telemetry report for a specific job source."""
    source_name: str
    status: str = "healthy"  # "healthy", "degraded", "error"
    jobs_found: int = 0
    latency_ms: float = 0.0
    last_crawled: Optional[datetime] = None
    error_message: Optional[str] = None


class RunSummary(BaseModel):
    """Summary of a full crawler and scoring pipeline execution."""
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
    execution_time_seconds: float = 0.0
    source_health: List[CrawlerHealth] = Field(default_factory=list)
    error_count: int = 0

