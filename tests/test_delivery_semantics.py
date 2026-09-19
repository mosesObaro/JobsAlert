"""
Regression tests for alert delivery: an alert is recorded as sent only after the
provider accepted it, and undelivered matches are retried on the next live run.
"""

from datetime import datetime, timezone
from typing import List
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.config import AppConfig, JobSpecConfig
from src.deduplication import StateManager
from src.income_opportunities.deduplication import IncomeStateManager
from src.models import CrawlerHealth, JobPosting
from src.notifier.email_service import DeliveryResult
from src.pipeline import JobPipeline
from src.verifier import LinkVerifier

pytestmark = pytest.mark.anyio


def strong_job(**overrides) -> JobPosting:
    fields = dict(
        id="gh_acme_1", fingerprint="fp_strong", title="HR Generalist", company="Acme", location="Remote (Worldwide)",
        is_remote=True, remote_scope="Worldwide", url="https://boards.greenhouse.io/acme/jobs/1", source="greenhouse",
        description="Human Resources, recruitment, onboarding and people operations.", posted_at=datetime.now(timezone.utc),
    )
    fields.update(overrides)
    return JobPosting(**fields)


def weak_job() -> JobPosting:
    return JobPosting(id="gh_acme_2", fingerprint="fp_weak", title="Warehouse Forklift Operator", company="Acme",
                      location="Hamburg, Germany", url="https://boards.greenhouse.io/acme/jobs/2", source="greenhouse")


def make_config(**delivery) -> AppConfig:
    config = AppConfig()
    config.job_specs = [JobSpecConfig(name="HR", target_roles=["HR Generalist"], must_have_skills=["Human Resources"],
                                      preferred_locations=["Remote", "Worldwide", "Nigeria"], salary_floor_usd=10000)]
    config.online_income.include_in_daily_digest = False
    config.link_verification.enabled = False
    config.schedule.instant_alert_threshold = 9.9
    for key, value in delivery.items():
        setattr(config.delivery, key, value)
    return config


def make_pipeline(tmp_path, config: AppConfig) -> JobPipeline:
    return JobPipeline(config=config, state_manager=StateManager(tmp_path / "seen.json"),
                       income_state_manager=IncomeStateManager(tmp_path / "income.json"))


async def run(pipeline: JobPipeline, jobs: List[JobPosting], result: DeliveryResult, **kwargs):
    with patch("src.pipeline.run_all_collectors", new_callable=AsyncMock) as collectors, \
         patch.object(pipeline.notifier, "send_digest", new_callable=AsyncMock) as send_digest:
        collectors.return_value = (jobs, [CrawlerHealth(source_name="greenhouse", jobs_found=len(jobs))])
        send_digest.return_value = result
        summary, scored = await pipeline.execute(dry_run=False, send_email=True, **kwargs)
        return summary, scored, send_digest


async def test_failed_digest_is_retried_on_the_next_run(tmp_path):
    config = make_config()
    first = make_pipeline(tmp_path, config)
    summary, _, send = await run(first, [strong_job()], DeliveryResult(ok=False, provider="resend", error="HTTP 500"))

    assert send.called
    assert summary.emails_dispatched == 0
    assert summary.pending_alerts == 1
    assert "Daily digest: HTTP 500" in summary.delivery_errors
    assert not first.state_manager.is_seen("fp_strong"), "an undelivered match must not be marked seen"

    retry = make_pipeline(tmp_path, config)
    summary, _, send = await run(retry, [strong_job()], DeliveryResult(ok=True, provider="resend"))
    assert [j.job.fingerprint for j in send.call_args.kwargs["jobs"]] == ["fp_strong"]
    assert summary.pending_alerts == 0
    assert retry.state_manager.is_alerted("fp_strong")


async def test_immediate_only_run_leaves_digest_matches_for_the_next_full_run(tmp_path):
    pipeline = make_pipeline(tmp_path, make_config())
    summary, _, send = await run(pipeline, [strong_job()], DeliveryResult(ok=True), immediate_only=True)
    assert not send.called
    assert summary.pending_alerts == 1
    assert not pipeline.state_manager.is_seen("fp_strong")


async def test_disabled_digest_records_matches_without_queueing_them(tmp_path):
    pipeline = make_pipeline(tmp_path, make_config(send_daily_digest=False))
    summary, _, send = await run(pipeline, [strong_job()], DeliveryResult(ok=True))
    assert not send.called
    assert summary.pending_alerts == 0
    assert pipeline.state_manager.is_seen("fp_strong")
    assert not pipeline.state_manager.is_alerted("fp_strong")


async def test_links_are_checked_only_for_candidates_and_dead_links_are_discarded(tmp_path):
    requested = []

    def handler(request):
        requested.append(str(request.url))
        return httpx.Response(404)

    config = make_config()
    config.link_verification.enabled = True
    pipeline = make_pipeline(tmp_path, config)
    pipeline.link_verifier = LinkVerifier(cache_file=tmp_path / "cache.json", transport=httpx.MockTransport(handler))

    summary, scored, send = await run(pipeline, [strong_job(), weak_job()], DeliveryResult(ok=True))
    assert requested == ["https://boards.greenhouse.io/acme/jobs/1"], "only the alert candidate is checked"
    assert not send.called
    assert summary.expired_links_removed == 1
    assert pipeline.state_manager.get("fp_strong")["action"] == "discard"


async def test_rate_limited_link_is_kept_and_delivered(tmp_path):
    config = make_config()
    config.link_verification.enabled = True
    pipeline = make_pipeline(tmp_path, config)
    pipeline.link_verifier = LinkVerifier(cache_file=tmp_path / "cache.json",
                                          transport=httpx.MockTransport(lambda request: httpx.Response(429)))

    summary, _, send = await run(pipeline, [strong_job()], DeliveryResult(ok=True))
    assert send.called
    assert summary.unverified_links == 1
    assert pipeline.state_manager.is_alerted("fp_strong")


async def test_counts_are_per_job_not_per_spec(tmp_path):
    config = make_config()
    config.job_specs.append(JobSpecConfig(name="Data", target_roles=["Data Analyst"], must_have_skills=["SQL"]))
    config.job_specs.append(JobSpecConfig(name="iOS", target_roles=["iOS Developer"], must_have_skills=["Swift"]))
    pipeline = make_pipeline(tmp_path, config)

    summary, scored, _ = await run(pipeline, [strong_job(), weak_job()], DeliveryResult(ok=True))
    assert len(scored) == 6  # 2 jobs x 3 specs
    assert summary.unique_candidates == 2
    assert summary.discarded + summary.low_matches + summary.digest_matches + summary.instant_matches == 2
    assert summary.spec_counts["HR"]["digest"] == 1
    assert pipeline.state_manager.get("fp_strong")["spec"] == "HR"
