"""
Unit tests for the weighted scoring engine.
"""

from datetime import datetime, timezone
import pytest

from src.config import AppConfig, FiltersConfig, ProfileConfig, WatchlistCompany
from src.models import JobPosting
from src.scoring import ScoringEngine


@pytest.fixture
def base_config():
    config = AppConfig()
    config.profile = ProfileConfig(
        candidate_name="Senior Engineer",
        target_roles=["Senior Software Engineer", "Distributed Systems Engineer"],
        experience_years=7,
        preferred_locations=["Remote", "Worldwide", "United States"],
        salary_floor_usd=120000.0,
    )
    config.filters = FiltersConfig(
        must_have_skills=["Go", "Python", "Kubernetes", "Distributed Systems"],
        nice_to_have_skills=["Rust", "Kafka"],
        excluded_terms=["PHP", "WordPress", "Intern", "Junior"],
        excluded_companies=["Spam Recruiter Corp"],
    )
    config.company_watchlist = [
        WatchlistCompany(name="Cloudflare", priority_multiplier=1.3),
        WatchlistCompany(name="Datadog", priority_multiplier=1.2),
    ]
    return config


def test_hard_exclusion_blacklisted_company(base_config):
    engine = ScoringEngine(base_config)
    job = JobPosting(
        id="1",
        title="Senior Software Engineer",
        company="Spam Recruiter Corp Ltd",
        location="Remote",
        url="https://example.com/job1",
        description="Great Go and Kubernetes role",
        source="greenhouse",
    )
    scored = engine.score_job(job)
    assert scored.score == 0.0
    assert scored.action == "discard"
    assert any("Blacklisted company" in p for p in scored.breakdown.penalties_applied)


def test_hard_exclusion_excluded_term(base_config):
    engine = ScoringEngine(base_config)
    job = JobPosting(
        id="2",
        title="Senior Software Engineer - PHP & WordPress",
        company="Tech Co",
        location="Remote",
        url="https://example.com/job2",
        description="Maintain legacy PHP code and WordPress sites",
        source="remotive",
    )
    scored = engine.score_job(job)
    assert scored.score == 0.0
    assert scored.action == "discard"
    assert any("Excluded term" in p for p in scored.breakdown.penalties_applied)


def test_seniority_mismatch_penalty(base_config):
    engine = ScoringEngine(base_config)
    job = JobPosting(
        id="3",
        title="Junior Software Engineer Intern",
        company="Good Co",
        location="Remote",
        url="https://example.com/job3",
        description="Entry level internship for students",
        source="greenhouse",
    )
    scored = engine.score_job(job)
    assert scored.score == 0.0
    assert scored.action == "discard"


def test_high_priority_target_match(base_config):
    engine = ScoringEngine(base_config)
    job = JobPosting(
        id="4",
        title="Senior Software Engineer, Distributed Systems",
        company="Cloudflare",
        location="Worldwide Remote",
        is_remote=True,
        remote_scope="Worldwide",
        url="https://example.com/job4",
        description="Build distributed systems in Go, Python, and Kubernetes at massive scale. Rust and Kafka a plus.",
        salary_min=160000.0,
        salary_max=210000.0,
        posted_at=datetime.now(timezone.utc),
        source="greenhouse",
    )
    scored = engine.score_job(job)
    # Cloudflare (1.3x boost) + Senior Distributed Systems + all must-haves + nice-to-haves + high comp + 24h
    assert scored.score >= 9.0
    assert scored.action == "instant"
    assert len(scored.breakdown.highlights) >= 3
    assert any("Cloudflare" in h for h in scored.breakdown.highlights)


def test_compensation_fit_below_floor(base_config):
    engine = ScoringEngine(base_config)
    job = JobPosting(
        id="5",
        title="Senior Software Engineer",
        company="Small Co",
        location="Remote",
        is_remote=True,
        remote_scope="Worldwide",
        url="https://example.com/job5",
        description="Go and Kubernetes",
        salary_min=45000.0,
        salary_max=55000.0,  # Far below $120k floor
        source="arbeitnow",
    )
    scored = engine.score_job(job)
    assert scored.breakdown.compensation_score < 3.0
    assert any("below floor" in p for p in scored.breakdown.penalties_applied)
