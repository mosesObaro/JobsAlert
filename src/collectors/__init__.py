"""
JobsAlert Collectors Registry & Concurrent Dispatcher.
"""

from __future__ import annotations
import asyncio
from typing import Dict, List, Tuple
from src.collectors.base import BaseCollector
from src.collectors.greenhouse import GreenhouseCollector
from src.collectors.lever import LeverCollector
from src.collectors.ashby import AshbyCollector
from src.collectors.remotive import RemotiveCollector
from src.collectors.remoteok import RemoteOKCollector
from src.collectors.arbeitnow import ArbeitnowCollector
from src.collectors.jobicy import JobicyCollector
from src.collectors.hackernews import HackerNewsCollector
from src.collectors.rss import RSSCollector
from src.config import AppConfig
from src.models import CrawlerHealth, JobPosting


def get_all_collectors() -> List[BaseCollector]:
    """Instantiates all supported job feed collectors."""
    return [
        GreenhouseCollector(),
        LeverCollector(),
        AshbyCollector(),
        RemotiveCollector(),
        RemoteOKCollector(),
        ArbeitnowCollector(),
        JobicyCollector(),
        HackerNewsCollector(),
        RSSCollector(),
    ]


async def run_all_collectors(config: AppConfig) -> Tuple[List[JobPosting], List[CrawlerHealth]]:
    """Runs all enabled collectors concurrently, returning collected jobs and health stats."""
    collectors = get_all_collectors()
    tasks = [col.execute(config) for col in collectors]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_jobs: List[JobPosting] = []
    health_reports: List[CrawlerHealth] = []

    for col, res in zip(collectors, results):
        health_reports.append(col.health)
        if isinstance(res, list):
            all_jobs.extend(res)

    return all_jobs, health_reports
