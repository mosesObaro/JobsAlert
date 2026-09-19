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


# --- regressions from the audit ---------------------------------------------

def _job(title, location="Remote", **kw):
    return JobPosting(id=f"t-{title}", title=title, company="Acme", location=location, url="https://x.test/1", source="remoteok", **kw)


def test_short_keywords_do_not_match_inside_other_words():
    config = AppConfig()
    config.profile.target_roles = ["HR"]
    config.filters.must_have_skills = []
    scored = ScoringEngine(config).score_job(_job("Chrome Extension Engineer"))
    assert not any("Role matches target" in h for h in scored.breakdown.highlights)


def test_senior_candidates_keep_international_and_internal_roles(base_config):
    engine = ScoringEngine(base_config)
    for title in ["International Payments Engineer", "Internal Tools Senior Software Engineer"]:
        assert engine.score_job(_job(title, description="Go Python Kubernetes")).action != "discard", title


def test_region_locked_remote_role_is_penalised_for_a_candidate_elsewhere():
    config = AppConfig()
    config.profile.preferred_locations = ["Remote", "Worldwide", "Nigeria"]
    engine = ScoringEngine(config)
    locked = engine.score_job(_job("Senior Software Engineer", location="Remote (US)", is_remote=True))
    open_ = engine.score_job(_job("Senior Software Engineer", location="Remote (Worldwide)", is_remote=True))
    assert locked.breakdown.location_score < open_.breakdown.location_score
    assert any("restricted to United States" in p for p in locked.breakdown.penalties_applied)


def test_foreign_currency_salary_is_converted_before_comparing_with_the_floor():
    config = AppConfig()
    config.profile.salary_floor_usd = 10000
    scored = ScoringEngine(config).score_job(
        _job("Senior Software Engineer", salary_min=300000, salary_max=450000, salary_currency="NGN", salary_period="monthly")
    )
    assert any("below floor" in p and "₦300,000" in p for p in scored.breakdown.penalties_applied)


def test_instant_threshold_comes_from_config(base_config):
    base_config.schedule.instant_alert_threshold = 8.0
    job = JobPosting(
        id="4", title="Senior Software Engineer, Distributed Systems", company="Cloudflare", location="Worldwide Remote",
        is_remote=True, remote_scope="Worldwide", url="https://example.com/job4",
        description="Go, Python, Kubernetes, distributed systems, Rust and Kafka.", salary_min=160000.0, salary_max=210000.0,
        posted_at=datetime.now(timezone.utc), source="greenhouse",
    )
    assert ScoringEngine(base_config).score_job(job).action == "instant"
