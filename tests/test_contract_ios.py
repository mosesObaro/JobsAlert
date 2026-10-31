"""
Unit tests for the Contract iOS track: the employment-fit boost, remote policy
for a Lagos-based candidate, hard exclusions, and that junior titles are not
penalised when a spec opts out of seniority matching.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.config import (
    AppConfig,
    FiltersConfig,
    JobSpecConfig,
    ProfileConfig,
    ScoringWeightsConfig,
    load_config,
)
from src.models import JobPosting
from src.scoring import ScoringEngine, triage

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_WEIGHTS = ScoringWeightsConfig(
    title_and_stack=40.0, location_remote=25.0, compensation=10.0,
    company_priority=10.0, recency_urgency=15.0, employment_fit=10.0,
)


@pytest.fixture
def ios_config() -> AppConfig:
    """A Lagos-based iOS engineer open to Worldwide/EMEA/Africa remote work."""
    config = AppConfig()
    config.profile = ProfileConfig(
        candidate_name="iOS Engineer",
        target_roles=["iOS Engineer", "iOS Developer"],
        experience_years=3,
        preferred_locations=["Remote", "Worldwide", "EMEA", "Africa", "Nigeria", "Anywhere"],
        salary_floor_usd=10000.0,
    )
    config.filters = FiltersConfig(must_have_skills=["Swift", "iOS"], nice_to_have_skills=["UIKit", "SwiftUI"])
    config.job_specs = [contract_spec()]
    return config


def contract_spec(**overrides) -> JobSpecConfig:
    fields = dict(
        name="Contract iOS (All Levels)",
        target_roles=[
            "iOS Engineer", "iOS Developer", "Junior iOS Developer",
            "Associate iOS Engineer", "Senior iOS Engineer", "Swift Developer",
        ],
        must_have_skills=["Swift", "iOS"],
        nice_to_have_skills=["UIKit", "SwiftUI", "Flutter", "Xamarin", "TestFlight", "KYC"],
        employment_type="contract",
        remote=True,
        preferred_locations=["Remote", "Worldwide", "EMEA", "Africa", "Nigeria", "Anywhere"],
        excluded_terms=["Security Clearance", "US Citizen", "US Only", "Intern", "Internship", "For Hire"],
        scoring_weights=CONTRACT_WEIGHTS,
        require_must_have=True,
        ignore_seniority=True,
        digest_threshold=6.0,
        instant_threshold=8.5,
        experience_years=3,
    )
    fields.update(overrides)
    return JobSpecConfig(**fields)


def ios_job(**overrides) -> JobPosting:
    fields = dict(
        id="job-1",
        title="iOS Engineer",
        company="Acme Mobile",
        location="Remote (Worldwide)",
        is_remote=True,
        remote_scope="Worldwide",
        url="https://example.com/jobs/1",
        description="Build iOS apps in Swift with UIKit and SwiftUI. Ship via TestFlight.",
        employment_type="full_time",
        source="remotive",
        posted_at=datetime.now(timezone.utc) - timedelta(hours=5),
    )
    fields.update(overrides)
    return JobPosting(**fields)


def score(config: AppConfig, job: JobPosting, spec: JobSpecConfig = None):
    return ScoringEngine(config).score_job(job, spec or config.job_specs[0])


# --- the contract boost -----------------------------------------------------

def test_contract_engagement_scores_above_an_identical_permanent_role(ios_config):
    permanent = score(ios_config, ios_job(employment_type="full_time"))
    contract = score(ios_config, ios_job(id="job-2", employment_type="contract"))

    assert contract.score > permanent.score
    assert contract.breakdown.employment_score == 10.0
    assert permanent.breakdown.employment_score == 0.0
    assert any("Contract / Freelance role match" in h for h in contract.breakdown.highlights)


def test_permanent_role_is_noted_but_not_discarded(ios_config):
    """Contract is a boost, not a filter."""
    permanent = score(ios_config, ios_job(employment_type="full_time"))

    assert permanent.score > 0.0
    assert permanent.action != "discard"
    assert any("Permanent full-time role" in p for p in permanent.breakdown.penalties_applied)


@pytest.mark.parametrize("phrase", [
    "This is a freelance engagement.",
    "Open to C2C candidates.",
    "1099 contractor position.",
    "A fixed-term six month engagement.",
    "Short-term project for an iOS consultant.",
    "This is a project-based role.",
])
def test_contract_wording_in_the_text_earns_a_partial_boost(ios_config, phrase):
    """A source that does not type the engagement still describes it."""
    job = ios_job(description=f"Swift and iOS work. {phrase}", employment_type="full_time")
    scored = score(ios_config, job)

    assert scored.breakdown.employment_score == 8.0
    assert any("Contract / Freelance role match" in h for h in scored.breakdown.highlights)


def test_tracks_without_employment_fit_are_unaffected(ios_config):
    """employment_fit defaults to 0, so other specs score exactly as before."""
    plain = contract_spec(scoring_weights=ScoringWeightsConfig(), ignore_seniority=True)
    contract = score(ios_config, ios_job(employment_type="contract"), plain)
    permanent = score(ios_config, ios_job(id="job-2", employment_type="full_time"), plain)

    assert contract.breakdown.employment_score == 0.0
    assert contract.score == permanent.score


# --- remote policy ----------------------------------------------------------

@pytest.mark.parametrize("location, remote_scope, expected", [
    ("Remote (Worldwide)", "Worldwide", "eligible"),
    ("Remote - EMEA", "EMEA", "eligible"),
    ("Remote (Africa)", "Africa", "eligible"),
    ("Remote (Nigeria)", "Nigeria", "eligible"),
    ("Remote (Canada only)", "Canada", "ineligible"),
    ("Remote - Europe", "Europe", "ineligible"),
])
def test_remote_eligibility_for_a_lagos_candidate(ios_config, location, remote_scope, expected):
    scored = score(ios_config, ios_job(location=location, remote_scope=remote_scope))
    assert scored.breakdown.eligibility == expected


def test_us_only_is_excluded_outright_rather_than_merely_ineligible(ios_config):
    """US-only authorisation is a hard exclusion, so it never reaches scoring."""
    scored = score(ios_config, ios_job(location="Remote (US only)", remote_scope="US-Only"))

    assert scored.action == "discard"
    assert any("US Only" in p for p in scored.breakdown.penalties_applied)


def test_a_region_locked_role_is_kept_but_penalised(ios_config):
    """Only the three listed exclusions discard; other regions just score lower."""
    scored = score(ios_config, ios_job(location="Remote (Canada only)", remote_scope="Canada"))

    assert scored.action != "discard"
    assert scored.breakdown.eligibility == "ineligible"


def test_worldwide_remote_outscores_a_region_locked_role(ios_config):
    worldwide = score(ios_config, ios_job(location="Remote (Worldwide)", remote_scope="Worldwide"))
    locked = score(ios_config, ios_job(id="job-2", location="Remote (Canada only)", remote_scope="Canada"))

    assert worldwide.score > locked.score
    assert any("open to all locations" in h for h in worldwide.breakdown.highlights)
    assert any("Remote but" in p for p in locked.breakdown.penalties_applied)


def test_onsite_lagos_role_matches_a_preferred_location(ios_config):
    scored = score(ios_config, ios_job(location="Lagos, Nigeria", remote_scope="On-Site", is_remote=False))
    assert scored.breakdown.location_score > 20.0


def test_onsite_role_elsewhere_is_penalised(ios_config):
    scored = score(ios_config, ios_job(location="Berlin, Germany", remote_scope="On-Site", is_remote=False))
    assert any("Non-matching on-site location" in p for p in scored.breakdown.penalties_applied)


# --- hard exclusions --------------------------------------------------------

@pytest.mark.parametrize("field, value", [
    ("title", "iOS Engineer (Security Clearance Required)"),
    ("title", "iOS Developer - US Citizens Only"),
    ("title", "iOS Engineering Intern"),
    ("title", "iOS Internship Programme"),
    ("title", "[FOR HIRE] iOS developer available"),
])
def test_hard_exclusions_discard_the_posting(ios_config, field, value):
    scored = score(ios_config, ios_job(**{field: value}))
    assert scored.score == 0.0
    assert scored.action == "discard"


def test_exclusions_also_apply_to_the_description(ios_config):
    job = ios_job(description="Swift iOS role. Applicants must hold an active Security Clearance.")
    assert score(ios_config, job).action == "discard"


@pytest.mark.parametrize("title", [
    "Junior iOS Developer",
    "Entry-Level iOS Engineer",
    "Graduate iOS Developer",
    "Associate iOS Engineer",
    "Trainee Swift Developer",
])
def test_junior_wording_is_not_an_exclusion(ios_config, title):
    """Junior, entry-level and graduate are deliberately not excluded."""
    scored = score(ios_config, ios_job(title=title))
    assert scored.score > 0.0
    assert scored.action != "discard"


def test_international_is_not_mistaken_for_intern(ios_config):
    """'Intern' is a whole-phrase exclusion, so 'International' must survive it."""
    scored = score(ios_config, ios_job(title="International iOS Engineer"))
    assert scored.action != "discard"


# --- seniority neutrality ---------------------------------------------------

@pytest.mark.parametrize("title", [
    "iOS Engineer",
    "Junior iOS Developer",
    "Senior iOS Engineer",
])
def test_every_level_scores_alike_on_seniority(ios_config, title):
    """Only the title wording differs, so the scores must not diverge on level."""
    baseline = score(ios_config, ios_job(title="iOS Developer", employment_type="contract"))
    scored = score(ios_config, ios_job(title=title, employment_type="contract"))

    assert scored.action != "discard"
    assert abs(scored.score - baseline.score) <= 0.5


def test_ignore_seniority_is_what_prevents_the_junior_discard(ios_config):
    """Without the opt-out, an experienced spec discards junior titles outright."""
    experienced = contract_spec(ignore_seniority=False, experience_years=7)
    junior_title = ios_job(title="Junior iOS Developer", employment_type="contract")

    assert score(ios_config, junior_title, experienced).action == "discard"
    assert score(ios_config, junior_title, contract_spec(experience_years=7)).action != "discard"


# --- the must-have gate -----------------------------------------------------

def test_posting_without_any_must_have_skill_is_held_out_of_the_digest(ios_config):
    """Location and recency alone must not carry a non-iOS role into the digest."""
    job = ios_job(
        title="Senior Backend Engineer",
        description="Build APIs in Go and Postgres. Worldwide remote contract.",
        employment_type="contract",
    )
    scored = score(ios_config, job)

    assert scored.breakdown.matched_must_have == []
    assert scored.action == "low_match", "a posting with neither Swift nor iOS must not reach the digest"
    assert any("None of the must-have skills" in p for p in scored.breakdown.penalties_applied)


def test_one_must_have_skill_is_enough_to_pass_the_gate(ios_config):
    """The gate asks for evidence, not for every skill."""
    job = ios_job(description="Maintain our iOS application.", employment_type="contract")
    scored = score(ios_config, job)

    assert scored.breakdown.matched_must_have == ["iOS"]
    assert scored.action in ("digest", "instant")


def test_the_gate_is_opt_in(ios_config):
    """Specs that do not set it keep scoring exactly as before."""
    ungated = contract_spec(require_must_have=False)
    job = ios_job(title="Senior Backend Engineer", description="Go and Postgres, worldwide remote contract.")

    gated_action = score(ios_config, job).action
    assert score(ios_config, job, ungated).action == "digest"
    assert gated_action == "low_match"


def test_the_gate_does_not_discard(ios_config):
    """Held-out postings still score and still reach the dashboard."""
    job = ios_job(title="Senior Backend Engineer", description="Go and Postgres, worldwide remote contract.")
    scored = score(ios_config, job)

    assert scored.score > 0.0
    assert scored.action != "discard"


# --- per-spec triage thresholds ---------------------------------------------

def test_triage_uses_the_spec_thresholds():
    assert triage(6.2, 8.5, 6.0) == "digest"
    assert triage(5.9, 8.5, 6.0) == "low_match"
    assert triage(8.6, 8.5, 6.0) == "instant"
    # Unchanged for a spec that sets no thresholds.
    assert triage(6.2, 9.2, None) == "low_match"
    assert triage(7.4, 9.2, None) == "digest"
    assert triage(4.9, 9.2, None) == "discard"


def test_lowered_digest_threshold_promotes_a_mid_scoring_role(ios_config):
    # Weak on purpose: no Swift in the text and over a week old, which lands
    # between the default 7.0 digest cut and this track's 6.0.
    job = ios_job(
        description="iOS maintenance work.",
        employment_type="full_time",
        posted_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    default_spec = contract_spec(digest_threshold=None, instant_threshold=None)

    boosted = score(ios_config, job)
    plain = score(ios_config, job, default_spec)

    assert 6.0 <= boosted.score < 7.0, f"fixture should land between the two thresholds, got {boosted.score}"
    assert boosted.action == "digest"
    assert plain.action == "low_match"


# --- the shipped configuration ----------------------------------------------

def test_shipped_profile_and_daily_config_agree_on_the_track():
    """The standalone profile and the daily digest must describe the same track."""
    profile = load_config(REPO_ROOT / "config" / "profiles" / "contract_ios.yaml")
    daily = load_config(REPO_ROOT / "config" / "jobs.yaml")

    from_profile = profile.get_effective_job_specs()[0]
    from_daily = daily.get_effective_job_specs()[0]

    for spec in (from_profile, from_daily):
        assert spec.name == "Contract iOS (All Levels)"
        assert spec.ignore_seniority is True
        assert spec.require_must_have is True
        assert (spec.digest_threshold, spec.instant_threshold) == (6.0, 8.5)
        assert spec.employment_type == "contract"
        assert set(spec.get_must_have_skills()) == {"Swift", "iOS"}
        assert spec.scoring_weights.employment_fit == 10.0
        assert not any(term.lower() in {"junior", "entry-level", "graduate"} for term in spec.excluded_terms)
        for required in ("Security Clearance", "US Citizen", "Intern", "Internship"):
            assert required in spec.excluded_terms


def test_daily_config_lists_the_contract_track_first():
    """Spec order is digest section order, so this track leads the email."""
    daily = load_config(REPO_ROOT / "config" / "jobs.yaml")
    names = [s.name for s in daily.get_effective_job_specs()]

    assert names[0] == "Contract iOS (All Levels)"
    assert len(names) > 1, "the other tracks must still be present and merged into one digest"


def test_daily_config_keeps_the_other_tracks_on_default_thresholds():
    daily = load_config(REPO_ROOT / "config" / "jobs.yaml")
    for spec in daily.get_effective_job_specs()[1:]:
        assert spec.digest_threshold is None
        assert spec.instant_threshold is None
        assert spec.scoring_weights.employment_fit == 0.0


# --- digest rendering -------------------------------------------------------

def test_digest_leads_with_the_contract_section_and_shows_the_badge(ios_config):
    """Spec order drives section order, and a contract role is marked as one."""
    from src.models import SpecMatchGroup
    from src.notifier.email_service import EmailNotifier

    contract = score(ios_config, ios_job(title="iOS Engineer", employment_type="contract"))
    permanent = score(ios_config, ios_job(id="job-2", title="Senior iOS Engineer", employment_type="full_time"))
    groups = [
        SpecMatchGroup(spec_name="Contract iOS (All Levels)", jobs=[contract], unalerted_jobs=[contract], total_matches=1),
        SpecMatchGroup(spec_name="HR Remote Roles", jobs=[permanent], unalerted_jobs=[permanent], total_matches=1),
    ]
    _, html, text = EmailNotifier().render_digest(jobs=[contract, permanent], config=ios_config, spec_groups=groups)

    assert html.index("Contract iOS (All Levels)") < html.index("HR Remote Roles")
    assert "📝 Contract / Freelance" in html, "a contract-typed role must carry the contract badge"
    assert "[CONTRACT / FREELANCE]" in text
    assert "Why You Match" in html and "Why You Match" in text
    # The permanent role keeps the plain engagement chip.
    assert "👔 Full time" in html
