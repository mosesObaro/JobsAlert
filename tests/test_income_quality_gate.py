"""
Unit and Integration Tests for Online Income Quality Gate,
Source Trust Model, Hard Rejection Classifier, and Precision Scoring.
"""

import pytest
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import (
    CompensationDetails,
    CompensationType,
    GeographicScope,
    OnlineIncomeOpportunity,
    OpportunityStatus,
    SourceTrustTier,
)
from src.income_opportunities.scoring import IncomeScoringEngine
from src.income_opportunities.verifier import (
    HardRejectionClassifier,
    analyze_opportunity_safety,
)


@pytest.fixture
def scoring_engine():
    config = OnlineIncomeConfig(
        candidate_name="Moses Obaro",
        eligible_countries=["Nigeria", "Worldwide", "Global", "Africa"],
        minimum_quality_score=7.0,
        minimum_side_job_fit_score=6.0,
        minimum_final_score=7.5,
        instant_alert_score=9.0,
        minimum_hourly_rate_usd=8.0,
    )
    return IncomeScoringEngine(config)


# ==============================================================================
# POSITIVE ACCEPTANCE TESTS (Legitimate, High-Quality Work)
# ==============================================================================

def test_accepts_official_ai_evaluator_contract(scoring_engine):
    """Tier 1 AI evaluation contract with explicit hourly pay must pass Quality Gate."""
    opp = OnlineIncomeOpportunity(
        id="test-dat-01",
        title="AI Response Evaluator & Generalist Trainer",
        organization="DataAnnotation.tech",
        description="Evaluate conversational AI responses for factual accuracy, logic, and coding benchmarks. Self-paced asynchronous tasks.",
        category="ai_evaluation",
        opportunity_type="hourly",
        url="https://www.dataannotation.tech",
        application_url="https://www.dataannotation.tech/workers",
        source="ai_evaluation",
        source_trust_tier=SourceTrustTier.TIER_1_HIGHEST,
        location_eligibility="Worldwide / Global",
        eligible_countries=["Worldwide", "Nigeria"],
        estimated_pay_min=20.0,
        estimated_pay_max=25.0,
        pay_rate_display="$20–$25/hr",
        is_remote=True,
        is_flexible=True,
        is_asynchronous=True,
        verification_status="verified_source",
        is_verified=True,
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score >= 8.5
    assert scored.breakdown.passed_quality_gate
    assert scored.breakdown.quality_score >= 8.5
    assert scored.breakdown.side_job_fit_score >= 8.5
    assert scored.action in ["digest", "instant"]
    assert any("Platform" in h for h in scored.breakdown.highlights)
    assert any("Side-Job Fit" in h for h in scored.breakdown.highlights)


def test_accepts_legitimate_research_assistant(scoring_engine):
    """Legitimate remote research assistant track from academic network."""
    opp = OnlineIncomeOpportunity(
        id="test-academic-01",
        title="Remote Academic Research Assistant & Literature Synthesizer",
        organization="Academic Positions Network",
        description="Synthesize literature, compile bibliographies (APA/Harvard), and organize data for faculty research papers.",
        category="research",
        opportunity_type="hourly",
        url="https://academicpositions.com",
        application_url="https://academicpositions.com/jobs",
        source="academic_tutoring",
        source_trust_tier=SourceTrustTier.TIER_1_HIGHEST,
        location_eligibility="Worldwide / Remote",
        eligible_countries=["Worldwide", "Nigeria"],
        estimated_pay_min=18.0,
        estimated_pay_max=26.0,
        pay_rate_display="$18–$26/hr",
        is_remote=True,
        is_asynchronous=True,
        verification_status="verified_source",
        is_verified=True,
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score >= 8.0
    assert scored.breakdown.passed_quality_gate
    assert scored.action == "digest" or scored.action == "instant"


def test_accepts_paid_academic_proofreading(scoring_engine):
    """Paid manuscript proofreading with self-paced asynchronous delivery."""
    opp = OnlineIncomeOpportunity(
        id="test-cp-01",
        title="Remote Academic Proofreader & Manuscript Editor",
        organization="Cambridge Proofreading LLC",
        description="Proofread and edit journal submissions and dissertations. 100% self-paced manuscript review with bi-weekly payout.",
        category="academic_editing",
        opportunity_type="hourly",
        url="https://proofreading.org",
        application_url="https://proofreading.org/careers/",
        source="academic_tutoring",
        source_trust_tier=SourceTrustTier.TIER_1_HIGHEST,
        location_eligibility="Worldwide",
        eligible_countries=["Worldwide", "Nigeria"],
        estimated_pay_min=20.0,
        estimated_pay_max=30.0,
        pay_rate_display="$20–$30/hr",
        is_asynchronous=True,
        verification_status="verified_source",
        is_verified=True,
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score >= 8.5
    assert scored.breakdown.passed_quality_gate
    assert scored.breakdown.side_job_fit_score >= 8.5


def test_accepts_worldwide_user_testing(scoring_engine):
    """Usability testing with fixed payouts per test."""
    opp = OnlineIncomeOpportunity(
        id="test-ut-01",
        title="Website & Mobile App Usability Tester",
        organization="UserTesting",
        description="Complete 15-20 minute usability walk-throughs speaking thoughts aloud. Receive verified payments via PayPal.",
        category="user_testing",
        opportunity_type="per_task",
        url="https://www.usertesting.com",
        application_url="https://www.usertesting.com/get-paid-to-test",
        source="user_testing",
        source_trust_tier=SourceTrustTier.TIER_2_GOOD,
        location_eligibility="Worldwide",
        eligible_countries=["Worldwide", "Nigeria"],
        estimated_pay_min=10.0,
        estimated_pay_max=60.0,
        pay_rate_display="$10–$60 per test",
        is_asynchronous=True,
        verification_status="verified_source",
        is_verified=True,
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score >= 7.5
    assert scored.breakdown.passed_quality_gate
    assert scored.action in ["digest", "instant"]


# ==============================================================================
# NEGATIVE REJECTION TESTS (Hard Rejections & Scams)
# ==============================================================================

def test_rejects_10_ways_to_make_money_online_article():
    """Listicle articles about making money must be hard rejected."""
    opp = OnlineIncomeOpportunity(
        id="test-blog-1",
        title="10 Ways To Make Money Online In 2026",
        organization="SideHustleBlog",
        description="Check out our comprehensive guide on the top 10 best websites to earn extra cash from home.",
        url="https://sidehustleblog.com/10-ways",
    )
    is_rejected, reasons = HardRejectionClassifier.evaluate(opp)
    assert is_rejected
    assert any("article" in r.lower() or "listicle" in r.lower() for r in reasons)


def test_rejects_mlm_pyramid_scheme():
    """MLM or downline recruitment schemes must be hard rejected."""
    opp = OnlineIncomeOpportunity(
        id="test-mlm-1",
        title="Direct Sales Consultant - Recruit 5 Friends for Downline Commission",
        organization="Matrix Wealth MLM",
        description="Build your team and earn multi-level marketing residual commissions from downlines.",
        url="https://matrixwealth.example.com",
    )
    is_rejected, reasons = HardRejectionClassifier.evaluate(opp)
    assert is_rejected
    assert any("multi-level marketing" in r.lower() or "recruitment" in r.lower() for r in reasons)


def test_rejects_crypto_trading_scheme():
    """Crypto investment and trading schemes must be rejected."""
    opp = OnlineIncomeOpportunity(
        id="test-crypto-1",
        title="Crypto Trading Bot Assistant - Earn Daily Bitcoin Deposit",
        organization="CryptoYield",
        description="Deposit into crypto wallet to trade crypto for profit with our high-yield investment system.",
        url="https://cryptoyield.example.com",
    )
    is_rejected, reasons = HardRejectionClassifier.evaluate(opp)
    assert is_rejected
    assert any("crypto" in r.lower() or "trading" in r.lower() for r in reasons)


def test_rejects_sports_betting_scheme():
    """Gambling and betting schemes must be rejected."""
    opp = OnlineIncomeOpportunity(
        id="test-betting-1",
        title="Sports Betting Bot Operator",
        organization="BetBot VIP",
        description="Run automated casino payout and sports betting algorithms to generate passive profits.",
        url="https://betbot.example.com",
    )
    is_rejected, reasons = HardRejectionClassifier.evaluate(opp)
    assert is_rejected
    assert any("gambling" in r.lower() or "betting" in r.lower() for r in reasons)


def test_rejects_affiliate_and_dropshipping():
    """Dropshipping and affiliate marketing must be rejected."""
    opp = OnlineIncomeOpportunity(
        id="test-affiliate-1",
        title="Automated Shopify Store Dropshipping Manager",
        organization="Ecom Success",
        description="Earn high affiliate commissions by setting up dropshipping e-commerce stores on TikTok shop.",
        url="https://ecomsuccess.example.com",
    )
    is_rejected, reasons = HardRejectionClassifier.evaluate(opp)
    assert is_rejected
    assert any("dropshipping" in r.lower() or "affiliate" in r.lower() for r in reasons)


def test_rejects_paid_course_and_coaching():
    """Paid courses or coaching packages must be rejected."""
    opp = OnlineIncomeOpportunity(
        id="test-course-1",
        title="High-Ticket Closer - Buy Our Masterclass Mentorship Program",
        organization="Closing Academy",
        description="Buy this course to unlock our high-ticket sales coaching package and starter kit.",
        url="https://closingacademy.example.com",
    )
    is_rejected, reasons = HardRejectionClassifier.evaluate(opp)
    assert is_rejected
    assert any("course" in r.lower() or "coaching" in r.lower() or "starter" in r.lower() for r in reasons)


def test_rejects_upfront_fee_opportunity(scoring_engine):
    """Opportunities demanding registration or starter fees must be rejected."""
    opp = OnlineIncomeOpportunity(
        id="test-fee-1",
        title="Data Entry Assistant - Pay $50 registration fee to start",
        organization="Scam Data Corp",
        description="Earn $30/hr after paying upfront starter kit fee and registration deposit.",
        url="https://scamcorp.example.com",
    )
    opp = analyze_opportunity_safety(opp)
    scored = scoring_engine.score_opportunity(opp)
    assert scored.score == 0.0
    assert scored.action == "discard"
    assert not scored.breakdown.passed_quality_gate


def test_rejects_us_only_for_nigeria_candidate(scoring_engine):
    """A remote opportunity restricted to US Only must be rejected when candidate is in Nigeria."""
    opp = OnlineIncomeOpportunity(
        id="test-us-only-1",
        title="Remote Usability Study Participant (United States Only)",
        organization="US Focus Group",
        description="Participate in video focus group sessions. Must be a US resident.",
        category="research",
        url="https://usfocus.example.com",
        location_eligibility="Remote - US Only",
        country_restrictions=["United States Only"],
        estimated_pay_min=50.0,
        estimated_pay_max=100.0,
        pay_rate_display="$50–$100/study",
        source_trust_tier=SourceTrustTier.TIER_2_GOOD,
        verification_status="verified_source",
        is_verified=True,
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score == 0.0
    assert scored.action == "discard"
    assert scored.breakdown.country_eligibility_score == 0.0
    assert any("Country restriction" in p or "Ineligible" in p for p in scored.breakdown.penalties_applied)


def test_rejects_dead_or_expired_link(scoring_engine):
    """Dead or expired links must be discarded."""
    opp = OnlineIncomeOpportunity(
        id="test-dead-1",
        title="AI Annotator",
        organization="AI Corp",
        url="https://expired-platform.example.com",
        status=OpportunityStatus.EXPIRED,
        is_verified=False,
        link_verification_status="404 Not Found",
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.score == 0.0
    assert scored.action == "discard"
    assert not scored.breakdown.is_verified


# ==============================================================================
# EDGE CASES
# ==============================================================================

def test_edge_case_unknown_compensation_reduces_quality_not_hard_blocked(scoring_engine):
    """Legitimate Tier-1 platform with unstated compensation passes Quality Gate but with lower score."""
    opp = OnlineIncomeOpportunity(
        id="test-unlisted-pay",
        title="AI Prompt Evaluator & Safety Annotator",
        organization="TELUS International AI",
        description="Review search engine prompts and multilingual AI responses. Ongoing part-time project stream.",
        category="ai_evaluation",
        url="https://telusinternational.ai",
        application_url="https://telusinternational.ai/community",
        source="ai_evaluation",
        source_trust_tier=SourceTrustTier.TIER_1_HIGHEST,
        location_eligibility="Worldwide",
        eligible_countries=["Worldwide", "Nigeria"],
        estimated_pay_min=None,
        estimated_pay_max=None,
        pay_rate_display=None,
        is_asynchronous=True,
        verification_status="verified_source",
        is_verified=True,
    )

    scored = scoring_engine.score_opportunity(opp)
    assert scored.breakdown.passed_quality_gate
    # Score is reduced compared to explicit pay ($20/hr at 9.5), but still valid
    assert 7.0 <= scored.score <= 9.3


def test_edge_case_crypto_in_unrelated_tech_stack_not_rejected():
    """Legitimate engineering or research task mentioning cryptography/blockchain in tech context is NOT a scam."""
    opp = OnlineIncomeOpportunity(
        id="test-crypto-stack",
        title="AI Model Evaluator for Cryptography & Network Security",
        organization="DataAnnotation.tech",
        description="Benchmark and evaluate LLM responses on applied cryptography, distributed hash algorithms, and cryptographic protocol implementations.",
        category="ai_evaluation",
        url="https://dataannotation.tech",
    )

    is_rejected, reasons = HardRejectionClassifier.evaluate(opp)
    assert not is_rejected
