import pytest
from datetime import datetime, timezone
from src.income_opportunities.models import (
    OnlineIncomeOpportunity,
    IncomeMatchBreakdown,
    ScoredOpportunity,
    IncomeCollectorHealth,
    IncomeRunSummary,
    SourceTrustTier,
    OpportunityStatus,
)
from src.income_opportunities.config import OnlineIncomeConfig, IncomeSourcesConfig


def test_online_income_opportunity_defaults():
    opp = OnlineIncomeOpportunity(
        id="test-opp-1",
        title="AI Prompt Evaluator",
        organization="DataAnnotation",
        url="https://dataannotation.tech",
    )
    assert opp.id == "test-opp-1"
    assert opp.category == "ai_evaluation"
    assert opp.is_remote is True
    assert opp.is_flexible is True
    assert opp.verification_status == "needs_review"
    assert opp.is_verified is True
    assert opp.source_trust_tier == SourceTrustTier.TIER_1_HIGHEST


def test_scored_opportunity_action():
    opp = OnlineIncomeOpportunity(
        id="test-opp-2",
        title="UX Tester",
        organization="UserTesting",
        url="https://usertesting.com",
    )
    breakdown = IncomeMatchBreakdown(
        quality_score=8.5,
        side_job_fit_score=9.0,
        category_score=9.0,
        compensation_score=8.5,
        highlights=["Great flexibility", "Verified company"],
    )
    scored = ScoredOpportunity(
        opportunity=opp,
        score=8.8,
        action="digest",
        breakdown=breakdown,
    )
    assert scored.score == 8.8
    assert scored.action == "digest"
    assert len(scored.breakdown.highlights) == 2


def test_income_run_summary():
    summary = IncomeRunSummary(
        run_id="run_test_01",
        total_fetched=25,
        unique_candidates=20,
        instant_matches=2,
        digest_matches=10,
        discarded=8,
    )
    assert summary.total_fetched == 25
    assert summary.instant_matches == 2
    assert summary.error_count == 0


def test_online_income_config_defaults():
    cfg = OnlineIncomeConfig()
    assert cfg.enabled is True
    assert "Nigeria" in cfg.eligible_countries
    assert "Worldwide" in cfg.eligible_countries
    assert "ai_evaluation" in cfg.preferred_categories
    assert "passive_income" in cfg.excluded_categories
    assert "software_dev" in cfg.excluded_categories
    assert cfg.minimum_quality_score == 7.0
    assert cfg.minimum_side_job_fit_score == 6.0
    assert cfg.minimum_final_score == 7.5
    assert cfg.max_digest_items == 5
    assert cfg.minimum_hourly_rate_usd == 8.0
