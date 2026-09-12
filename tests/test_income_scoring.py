import pytest
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import OnlineIncomeOpportunity, SourceTrustTier
from src.income_opportunities.scoring import IncomeScoringEngine


@pytest.fixture
def scoring_engine():
    config = OnlineIncomeConfig(
        eligible_countries=["Nigeria", "Worldwide"],
        minimum_quality_score=7.0,
        minimum_side_job_fit_score=6.0,
        minimum_final_score=7.5,
        instant_alert_score=9.0,
        minimum_hourly_rate_usd=8.0,
    )
    return IncomeScoringEngine(config)


def test_score_verified_high_match_opportunity(scoring_engine):
    opp = OnlineIncomeOpportunity(
        id="test-dat-1",
        title="AI Response Evaluator & Benchmark Annotator",
        organization="DataAnnotation.tech",
        description="Benchmark and evaluate LLM responses for factual reasoning and accuracy. Self-paced asynchronous tasks.",
        category="ai_evaluation",
        url="https://www.dataannotation.tech",
        source_trust_tier=SourceTrustTier.TIER_1_HIGHEST,
        location_eligibility="Worldwide / Global",
        eligible_countries=["Worldwide", "Nigeria"],
        estimated_pay_min=20.0,
        estimated_pay_max=25.0,
        pay_rate_display="$20–$25/hr",
        is_asynchronous=True,
        verification_status="verified_source",
        is_verified=True,
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score >= 8.5
    assert scored.breakdown.passed_quality_gate
    assert scored.action in ["digest", "instant"]
    assert len(scored.breakdown.highlights) >= 2
    assert any("Platform" in h or "Location" in h for h in scored.breakdown.highlights)
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
        description="Comprehensive academic research study evaluating online behavior for verified US participants only.",
        category="research",
        url="https://example.com/study",
        location_eligibility="United States Only",
        country_restrictions=["US Only"],
        estimated_pay_min=25.0,
        estimated_pay_max=35.0,
        pay_rate_display="$25 - $35 / hr",
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score == 0.0
    assert scored.action == "discard"
    assert any("Country restriction" in p or "Ineligible" in p for p in scored.breakdown.penalties_applied)


def test_score_scam_rejected_discarded(scoring_engine):
    opp = OnlineIncomeOpportunity(
        id="test-scam-1",
        title="Earn $500/day guaranteed wire transfer",
        organization="Suspicious Org",
        category="ai_evaluation",
        url="https://example.com/scam",
        location_eligibility="Worldwide",
        verification_status="rejected",
        scam_risk_indicators=["Requires upfront registration fee"],
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score == 0.0
    assert scored.action == "discard"
    assert not scored.breakdown.is_verified
