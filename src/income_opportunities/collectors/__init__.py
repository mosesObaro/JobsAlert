"""
Online Income Opportunities Collectors Registry and Runner.
"""

from __future__ import annotations
import asyncio
from typing import List, Tuple

from src.income_opportunities.collectors.base import BaseIncomeCollector
from src.income_opportunities.collectors.catalog import (
    AcademicTutoringCollector,
    AIEvaluationCollector,
    TranscriptionSupportCollector,
    UserTestingCollector,
)
from src.income_opportunities.collectors.custom import CustomIncomeCollector
from src.income_opportunities.collectors.rss import IncomeRSSCollector
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.models import IncomeCollectorHealth, OnlineIncomeOpportunity

__all__ = [
    "AIEvaluationCollector",
    "AcademicTutoringCollector",
    "BaseIncomeCollector",
    "CustomIncomeCollector",
    "IncomeRSSCollector",
    "TranscriptionSupportCollector",
    "UserTestingCollector",
    "get_all_income_collectors",
    "run_all_income_collectors",
]


def get_all_income_collectors() -> List[BaseIncomeCollector]:
    """Instances of every income opportunity collector."""
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
    """Runs every enabled income collector concurrently; returns items and per-source health."""
    collectors = get_all_income_collectors()
    results = await asyncio.gather(*(c.execute(config) for c in collectors), return_exceptions=True)

    all_opps: List[OnlineIncomeOpportunity] = []
    for result in results:
        if isinstance(result, list):
            all_opps.extend(result)
    return all_opps, [c.health for c in collectors]
