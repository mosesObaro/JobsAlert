"""
Guards for the shipped source configuration.

Phase 1 of the source-expansion work removed board tokens that answer 404 and
switched off a source whose upstream has gone. These tests pin the outcome so a
dead board is not re-added by accident, and pin the protected LinkedIn settings
that must survive the rest of the expansion.

Every board token listed here was checked against its live endpoint on
2026-11-19; the tests themselves make no network calls.
"""

import asyncio
from pathlib import Path

import pytest

from src.collectors.ashby import AshbyCollector
from src.collectors.greenhouse import GreenhouseCollector
from src.collectors.lever import LeverCollector
from src.collectors.twitter import TwitterCollector
from src.config import AppConfig, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]

# Verified 404 on their own ATS, with no replacement board found on Greenhouse,
# Lever, Ashby, SmartRecruiters or Workable (except kuda, which is on Workable —
# a platform this project has no collector for yet).
DEAD_BOARDS = {
    "greenhouse": ["flutterwave", "paystack", "kuda", "automattic"],
    "lever": ["deel"],
    "ashby": ["scalearmy"],
}


@pytest.fixture
def shipped() -> AppConfig:
    return load_config(REPO_ROOT / "config" / "jobs.yaml")


def test_no_known_dead_board_token_is_configured(shipped):
    for source_name, dead in DEAD_BOARDS.items():
        configured = [c.lower() for c in getattr(shipped.sources, source_name).companies]
        for token in dead:
            assert token not in configured, (
                f"{source_name}/{token} answers 404; re-adding it makes the source "
                f"report degraded on every run"
            )


def test_automattic_is_configured_under_its_current_token(shipped):
    """The board moved; the old token 404s while this one serves postings."""
    assert "automatticcareers" in shipped.sources.greenhouse.companies


@pytest.mark.parametrize("collector_cls, source_name", [
    (GreenhouseCollector, "greenhouse"),
    (LeverCollector, "lever"),
    (AshbyCollector, "ashby"),
])
def test_an_ats_source_without_tokens_reports_disabled_not_degraded(collector_cls, source_name):
    """An empty board list is a deliberate state, not a failure.

    This is what keeps Lever quiet now that its only token is dead: `is_enabled`
    is False, so `execute` never calls the network and health reads "disabled".
    """
    config = AppConfig()
    getattr(config.sources, source_name).companies = []
    collector = collector_cls()

    jobs = asyncio.run(collector.execute(config))

    assert jobs == []
    assert collector.health.status == "disabled"
    assert collector.health.error_message is None


def test_lever_is_quiet_until_a_verified_token_is_added(shipped):
    assert shipped.sources.lever.companies == []


def test_twitter_is_switched_off(shipped):
    """Both Nitter mirrors fail DNS, the third answers 451 and the syndication
    endpoint answers 429, so the source returned nothing on every run."""
    assert shipped.sources.twitter.enabled is False


def test_disabled_twitter_makes_no_request():
    config = AppConfig()
    config.sources.twitter.enabled = False
    collector = TwitterCollector()

    # conftest blocks real network, so reaching HTTP here would raise.
    jobs = asyncio.run(collector.execute(config))

    assert jobs == []
    assert collector.health.status == "disabled"


# --- protected configuration -------------------------------------------------

def test_linkedin_keeps_its_six_searches_with_nigeria_first(shipped):
    """Protected: search order mitigates rate limiting, and the Nigerian
    searches must not be narrowed back to remote-only or contract-only."""
    searches = shipped.sources.linkedin.searches
    assert len(searches) == 6

    nigerian = [s for s in searches if s.location.lower() == "nigeria"]
    assert len(nigerian) == 3
    assert [s.name for s in searches[:3]] == [s.name for s in nigerian], "Nigerian searches must run first"
    for search in nigerian:
        assert search.remote_only is False
        assert search.job_type == ""


def test_linkedin_request_budget_stays_small(shipped):
    """Nine requests per run at three pages maximum each; raising this risks the
    429s that the pacing exists to avoid."""
    settings = shipped.sources.linkedin
    pages = sum(min(3, max(1, -(-s.max_results // 10))) for s in settings.searches)

    assert pages <= 9
    assert settings.request_delay_seconds >= 2.0


def test_every_enabled_job_spec_still_present(shipped):
    """Protected: the four configured tracks and their tuned thresholds."""
    names = [s.name for s in shipped.get_effective_job_specs()]
    assert names == [
        "Contract iOS (All Levels)",
        "HR Remote Roles",
        "Junior Swift/iOS Developer — Remote Contract",
        "Junior Data Analyst — Remote Contract",
    ]


# --- international coverage (Phase 4) ----------------------------------------

def test_the_we_work_remotely_people_feed_is_configured(shipped):
    """Verified 2026-11-19: 53 entries, newest same day. This is the category
    We Work Remotely files people roles under — there is no
    remote-human-resources-jobs feed, which answers 301 with no body."""
    urls = [f.url for f in shipped.sources.rss_feeds if f.enabled]
    assert any("remote-management-and-finance-jobs.rss" in u for u in urls)


def test_no_international_platform_was_integrated_without_a_permitted_route(shipped):
    """Indeed, Glassdoor and Wellfound all disallow their job pages in
    robots.txt and expose no public jobs API, so none of them is collected.
    This pins that decision so a scraper is not added quietly later."""
    configured = " ".join(
        [f.url for f in shipped.sources.rss_feeds]
        + [s.keywords + s.location for s in shipped.sources.linkedin.searches]
    ).lower()
    for blocked in ("indeed.com", "glassdoor.com", "wellfound.com", "angel.co"):
        assert blocked not in configured


def test_the_collector_registry_has_no_source_without_a_config_entry():
    """Every registered collector must be switchable from configuration."""
    from src.collectors import get_all_collectors
    from src.config import AppConfig

    sources = AppConfig().sources
    # `custom` and `rss` are driven by data files and the feed list respectively.
    exempt = {"custom", "rss"}
    for collector in get_all_collectors():
        if collector.name in exempt:
            continue
        assert hasattr(sources, collector.name), f"{collector.name} has no entry under SourcesConfig"
