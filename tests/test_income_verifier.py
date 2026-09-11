import pytest
from src.income_opportunities.models import OnlineIncomeOpportunity
from src.income_opportunities.verifier import (
    IncomeOpportunityVerifier,
    analyze_opportunity_safety,
)


def test_safety_detection_verified_platform():
    opp = OnlineIncomeOpportunity(
        id="test-1",
        title="AI Trainer",
        organization="Outlier.ai",
        url="https://outlier.ai",
    )
    evaluated = analyze_opportunity_safety(opp)
    assert evaluated.verification_status == "verified_source"
    assert len(evaluated.legitimacy_indicators) > 0
    assert len(evaluated.scam_risk_indicators) == 0


def test_safety_detection_upfront_fee_rejection():
    opp = OnlineIncomeOpportunity(
        id="test-scam-fee",
        title="Data Entry Clerk - Pay $50 registration fee to start",
        organization="Fake Co",
        url="https://fakeco.com",
    )
    evaluated = analyze_opportunity_safety(opp)
    assert evaluated.verification_status == "rejected"
    assert any("upfront payment" in r.lower() for r in evaluated.scam_risk_indicators)


def test_safety_detection_mlm_pyramid_rejection():
    opp = OnlineIncomeOpportunity(
        id="test-mlm",
        title="Online Partner - Recruit others for downline commission",
        organization="Pyramid Scheme Inc",
        url="https://pyramid.com",
    )
    evaluated = analyze_opportunity_safety(opp)
    assert evaluated.verification_status == "rejected"
    assert any("multi-level marketing" in r.lower() for r in evaluated.scam_risk_indicators)


def test_safety_detection_crypto_forex_rejection():
    opp = OnlineIncomeOpportunity(
        id="test-crypto",
        title="Crypto wallet investment assistant earn daily bitcoin deposit",
        organization="CryptoBot",
        url="https://cryptobot.com",
    )
    evaluated = analyze_opportunity_safety(opp)
    assert evaluated.verification_status == "rejected"
    assert any("cryptocurrency" in r.lower() for r in evaluated.scam_risk_indicators)


def test_safety_detection_caution_signature():
    opp = OnlineIncomeOpportunity(
        id="test-caution",
        title="Remote Clerk",
        organization="Unknown Co",
        description="Contact via WhatsApp only for details",
        url="https://unknownco.com",
    )
    evaluated = analyze_opportunity_safety(opp)
    assert evaluated.verification_status == "risk_flagged"
    assert any("whatsapp" in r.lower() for r in evaluated.scam_risk_indicators)
