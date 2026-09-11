import asyncio
import pytest
from src.income_opportunities.collectors import (
    AIEvaluationCollector,
    UserTestingCollector,
    AcademicTutoringCollector,
    TranscriptionSupportCollector,
    CustomIncomeCollector,
    get_all_income_collectors,
    run_all_income_collectors,
)
from src.income_opportunities.config import OnlineIncomeConfig


def test_ai_evaluation_collector():
    collector = AIEvaluationCollector()
    config = OnlineIncomeConfig()
    opps = asyncio.run(collector.collect(config))
    assert len(opps) >= 4
    orgs = [o.organization.lower() for o in opps]
    assert any("dataannotation" in o for o in orgs)
    assert any("outlier" in o for o in orgs)


def test_user_testing_collector():
    collector = UserTestingCollector()
    config = OnlineIncomeConfig()
    opps = asyncio.run(collector.collect(config))
    assert len(opps) >= 3
    orgs = [o.organization.lower() for o in opps]
    assert any("usertesting" in o for o in orgs)
    assert any("testbirds" in o for o in orgs)


def test_academic_tutoring_collector():
    collector = AcademicTutoringCollector()
    config = OnlineIncomeConfig()
    opps = asyncio.run(collector.collect(config))
    assert len(opps) >= 3
    orgs = [o.organization.lower() for o in opps]
    assert any("cambridge" in o for o in orgs)
    assert any("preply" in o for o in orgs)


def test_transcription_support_collector():
    collector = TranscriptionSupportCollector()
    config = OnlineIncomeConfig()
    opps = asyncio.run(collector.collect(config))
    assert len(opps) >= 3
    orgs = [o.organization.lower() for o in opps]
    assert any("rev" in o for o in orgs)
    assert any("gotranscript" in o for o in orgs)


def test_run_all_income_collectors():
    config = OnlineIncomeConfig()
    opps, health = asyncio.run(run_all_income_collectors(config))
    assert len(opps) > 10
    assert len(health) == len(get_all_income_collectors())
    assert all(h.status in ["healthy", "degraded"] for h in health)
