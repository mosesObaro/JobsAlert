"""
Unit tests for job collectors and data parsing.
"""

from unittest.mock import AsyncMock, patch
import pytest

from src.collectors.greenhouse import GreenhouseCollector
from src.collectors.lever import LeverCollector
from src.collectors.remotive import parse_salary_string
from src.config import AppConfig


def test_parse_salary_string():
    min_s, max_s = parse_salary_string("$120k - $160k")
    assert min_s == 120000.0
    assert max_s == 160000.0

    min_s, max_s = parse_salary_string("110,000 - 150,000 USD")
    assert min_s == 110000.0
    assert max_s == 150000.0

    min_s, max_s = parse_salary_string("$140k")
    assert min_s == 140000.0
    assert max_s == 140000.0

    min_s, max_s = parse_salary_string("")
    assert min_s is None
    assert max_s is None


def test_greenhouse_collector_disabled():
    import asyncio
    config = AppConfig()
    config.sources.greenhouse.enabled = False
    collector = GreenhouseCollector()
    jobs = asyncio.run(collector.collect(config))
    assert jobs == []


def test_lever_collector_disabled():
    import asyncio
    config = AppConfig()
    config.sources.lever.enabled = False
    collector = LeverCollector()
    jobs = asyncio.run(collector.collect(config))
    assert jobs == []
