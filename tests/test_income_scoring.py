import pytest
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import OnlineIncomeOpportunity
from src.income_opportunities.scoring import IncomeScoringEngine


@pytest.fixture
def scoring_engine():
    config = OnlineIncomeConfig(
        eligible_countries=["Nigeria", "Worldwide"],
        minimum_score=7.0,
        instant_alert_score=9.0,
        minimum_hourly_rate_usd=5.0,
    )
    return IncomeScoringEngine(config)


def test_score_verified_high_match_opportunity(scoring_engine):
    opp = OnlineIncomeOpportunity(
        id="test-dat-1",
        title="AI Evaluator & Content Annotator",
        organization="DataAnnotation.tech",
        category="ai_evaluation",
        url="https://www.dataannotation.tech",
        location_eligibility="Worldwide / Global",
        eligible_countries=["Worldwide", "Nigeria"],
        estimated_pay_min=20.0,
        estimated_pay_max=25.0,
        pay_rate_display="$20–$25/hr",
        verification_status="verified_source",
        is_verified=True,
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score >= 9.0
    assert scored.action == "instant"
    assert len(scored.breakdown.highlights) >= 2
    assert any("Location" in h for h in scored.breakdown.highlights)
    assert any("Compensation" in h for h in scored.breakdown.highlights)


def test_score_excluded_category_discarded(scoring_engine):
    opp = OnlineIncomeOpportunity(
        id="test-software-1",
        title="Full Stack Software Engineer",
        organization="Tech Co",
        category="software_dev",
        url="https://example.com/job",
        location_eligibility="Worldwide",
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score == 0.0
    assert scored.action == "discard"
    assert any("Hard Exclusion" in p for p in scored.breakdown.penalties_applied)


def test_score_country_restricted_discarded(scoring_engine):
    opp = OnlineIncomeOpportunity(
        id="test-us-only-1",
        title="US Only Research Study",
        organization="US Lab",
        category="survey_research",
        url="https://example.com/study",
        location_eligibility="United States Only",
        country_restrictions=["US Only"],
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score == 0.0
    assert scored.action == "discard"
    assert any("Country restriction" in p for p in scored.breakdown.penalties_applied)


def test_score_scam_rejected_discarded(scoring_engine):
    opp = OnlineIncomeOpportunity(
        id="test-scam-1",
        title="Earn $500/day guaranteed wire transfer",
        organization="Suspicious Org",
        category="general_flexible",
        url="https://example.com/scam",
        location_eligibility="Worldwide",
        verification_status="rejected",
        scam_risk_indicators=["Requires upfront registration fee"],
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score == 0.0
    assert scored.action == "discard"
    assert not scored.breakdown.is_verified
