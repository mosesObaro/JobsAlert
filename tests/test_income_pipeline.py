import asyncio
import pytest
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.deduplication import IncomeStateManager
from src.income_opportunities.pipeline import IncomeOpportunityPipeline


def test_income_pipeline_dry_run(tmp_path):
    state_file = tmp_path / "test_seen_income.json"
    state_mgr = IncomeStateManager(state_file=state_file)

    config = OnlineIncomeConfig(
        eligible_countries=["Nigeria", "Worldwide"],
        minimum_score=7.0,
        instant_alert_score=9.0,
        require_link_verification=False,
    )

    pipeline = IncomeOpportunityPipeline(config=config, state_manager=state_mgr)

    summary, scored = asyncio.run(pipeline.execute(
        dry_run=True,
        send_email=False,
        force_all=True,
    ))

    assert summary.total_fetched > 0
    assert len(scored) > 0
    assert summary.instant_matches + summary.digest_matches > 0
    # Dry run should not record alerts to persistent state
    assert len(state_mgr.get_all_records()) == 0


def test_income_pipeline_live_state_persistence(tmp_path):
    state_file = tmp_path / "test_seen_income_live.json"
    state_mgr = IncomeStateManager(state_file=state_file)

    config = OnlineIncomeConfig(
        eligible_countries=["Nigeria", "Worldwide"],
        require_link_verification=False,
    )

    pipeline = IncomeOpportunityPipeline(config=config, state_manager=state_mgr)

    summary, scored = asyncio.run(pipeline.execute(
        dry_run=False,
        send_email=False,
        force_all=True,
    ))

    # State file should now have records
    assert len(state_mgr.get_all_records()) > 0
