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


def test_custom_job_collector(tmp_path, monkeypatch):
    import asyncio
    from src.collectors.custom import CustomJobCollector, add_custom_job
    import src.collectors.custom as c_mod

    test_file = tmp_path / "custom_jobs.json"
    monkeypatch.setattr(c_mod, "CUSTOM_JOBS_FILE", test_file)

    add_custom_job(
        title="Staff Engineer",
        company="Anthropic",
        location="Remote",
        url="https://example.com/anthropic",
        description="Go and Kubernetes",
        salary_min=190000,
        salary_max=250000,
    )

    config = AppConfig()
    collector = CustomJobCollector()
    jobs = asyncio.run(collector.collect(config))

    assert len(jobs) == 1
    assert jobs[0].title == "Staff Engineer"
    assert jobs[0].company == "Anthropic"
    assert jobs[0].salary_min == 190000.0
    assert jobs[0].source == "custom"


def test_twitter_collector_disabled():
    import asyncio
    from src.collectors.twitter import TwitterCollector
    config = AppConfig()
    config.sources.twitter.enabled = False
    collector = TwitterCollector()
    jobs = asyncio.run(collector.collect(config))
    assert jobs == []


def test_twitter_collector_rss_parsing():
    from src.collectors.twitter import TwitterCollector
    collector = TwitterCollector()

    sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Twitter / Search</title>
        <item>
          <title>We are hiring a Senior Python Engineer at Moniepoint! Apply: https://t.co/xyz123 #remote #hiring</title>
          <description>We are hiring a Senior Python Engineer at Moniepoint! Apply: https://t.co/xyz123 #remote #hiring</description>
          <link>https://nitter.poast.org/TechJobsAfrica/status/1234567890</link>
          <pubDate>Fri, 05 Sep 2026 10:00:00 GMT</pubDate>
        </item>
      </channel>
    </rss>
    """

    jobs = collector._parse_nitter_rss(sample_rss, default_company="Moniepoint")
    assert len(jobs) == 1
    assert "Python Engineer" in jobs[0].title or "Senior Python" in jobs[0].title
    assert jobs[0].source == "twitter"
    assert jobs[0].is_remote is True
    assert jobs[0].url == "https://t.co/xyz123"


