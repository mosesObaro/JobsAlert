"""
Online Income Opportunities Collectors Registry and Runner.
"""

from __future__ import annotations
import asyncio
from typing import List, Tuple

from src.income_opportunities.collectors.base import BaseIncomeCollector
from src.income_opportunities.collectors.ai_evaluation import AIEvaluationCollector
from src.income_opportunities.collectors.user_testing import UserTestingCollector
from src.income_opportunities.collectors.academic_tutoring import AcademicTutoringCollector
from src.income_opportunities.collectors.transcription_support import TranscriptionSupportCollector
from src.income_opportunities.collectors.rss import IncomeRSSCollector
from src.income_opportunities.collectors.custom import CustomIncomeCollector, add_custom_income_opportunity
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import IncomeCollectorHealth, OnlineIncomeOpportunity


def get_all_income_collectors() -> List[BaseIncomeCollector]:
    """Returns initialized instances of all available income opportunity collectors."""
    return [
        AIEvaluationCollector(),
        UserTestingCollector(),
        AcademicTutoringCollector(),
        TranscriptionSupportCollector(),
        IncomeRSSCollector(),
        CustomIncomeCollector(),
    ]


async def run_all_income_collectors(
    config: OnlineIncomeConfig
) -> Tuple[List[OnlineIncomeOpportunity], List[IncomeCollectorHealth]]:
    """
    Runs all enabled income collectors concurrently.
    Returns:
        (all_opportunities, list_of_collector_health_records)
    """
    collectors = get_all_income_collectors()
    tasks = [c.execute(config) for c in collectors]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_opps: List[OnlineIncomeOpportunity] = []
    health_reports: List[IncomeCollectorHealth] = []

    for idx, res in enumerate(results):
        collector = collectors[idx]
        if isinstance(res, Exception):
            collector.health.status = "error"
            collector.health.error_message = str(res)
            health_reports.append(collector.health)
        else:
            health_reports.append(collector.health)
            all_opps.extend(res)

    return all_opps, health_reports
