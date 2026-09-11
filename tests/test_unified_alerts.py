"""
Unit and integration tests for Unified Daily Alerts (Jobs + Online Income Opportunities).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
import pytest

from src.config import AppConfig
from src.deduplication import StateManager
from src.income_opportunities.config import OnlineIncomeConfig
from src.income_opportunities.deduplication import IncomeStateManager
from src.income_opportunities.models import (
    IncomeCollectorHealth,
    IncomeMatchBreakdown,
    OnlineIncomeOpportunity,
    ScoredOpportunity,
)
from src.models import CrawlerHealth, JobPosting, MatchBreakdown, ScoredJob
from src.notifier.email_service import EmailNotifier
from src.pipeline import JobPipeline


@pytest.fixture
def sample_job():
    job = JobPosting(
        id="sample_career_1",
        fingerprint="fp_career_sample_1",
        title="Senior Financial Analyst",
        company="Moniepoint",
        location="Worldwide Remote",
        is_remote=True,
        remote_scope="Worldwide",
        url="https://boards.greenhouse.io/moniepoint/jobs/101",
        salary_min=75000.0,
        salary_max=95000.0,
        source="greenhouse",
        posted_at=datetime.now(timezone.utc),
    )
    breakdown = MatchBreakdown(
        title_score=35.0,
        stack_score=20.0,
        location_score=20.0,
        compensation_score=10.0,
        company_score=10.0,
        recency_score=5.0,
        highlights=[
            "Role matches target 'Senior Financial Analyst'",
            "Watchlist Priority Multiplier applied (1.3x)",
            "Strong Compensation: $75,000 - $95,000",
        ],
        is_verified=True,
    )
    return ScoredJob(job=job, score=9.2, action="instant", breakdown=breakdown)


@pytest.fixture
def sample_income_opp():
    opp = OnlineIncomeOpportunity(
        id="sample_income_1",
        fingerprint="fp_income_sample_1",
        title="AI Evaluation Specialist - Reasoning & Logic",
        organization="DataAnnotation.tech",
        category="ai_evaluation",
        url="https://www.dataannotation.tech/apply",
        application_url="https://www.dataannotation.tech/apply",
        location_eligibility="Worldwide (Nigeria Eligible)",
        pay_rate_display="$20 - $40 / hr",
        estimated_hourly_usd=30.0,
        description="Evaluate reasoning models and rate generated responses for accuracy.",
        source="ai_evaluation",
        is_safe=True,
        is_active=True,
    )
    breakdown = IncomeMatchBreakdown(
        country_score=25.0,
        compensation_score=20.0,
        legitimacy_score=20.0,
        flexibility_score=15.0,
        category_score=15.0,
        ease_score=5.0,
        highlights=[
            "High pay rate ($20–$40/hr) exceeds minimum floor",
            "Open to candidates in Nigeria / Worldwide",
            "Verified legitimate platform with weekly payouts",
        ],
    )
    return ScoredOpportunity(opportunity=opp, score=9.5, action="instant", breakdown=breakdown)


def test_format_digest_subject_scenarios(sample_job, sample_income_opp):
    notifier = EmailNotifier()

    # Both jobs and income
    subj_both = notifier.format_digest_subject([sample_job], [sample_income_opp])
    assert "1 Target Role" in subj_both
    assert "1 Online Income Track" in subj_both
    assert "[Daily Alert]" in subj_both

    # Only jobs
    subj_jobs = notifier.format_digest_subject([sample_job], [])
    assert "[Job Alert]" in subj_jobs
    assert "1 High-Match Opportunity Found" in subj_jobs

    # Only income
    subj_income = notifier.format_digest_subject([], [sample_income_opp])
    assert "[Income Alert]" in subj_income
    assert "1 Verified Online Income Track Found" in subj_income

    # Empty
    subj_empty = notifier.format_digest_subject([], [])
    assert "[Daily Alert]" in subj_empty


def test_render_unified_digest_email(sample_job, sample_income_opp):
    config = AppConfig()
    notifier = EmailNotifier()

    subject, html_content, text_content = notifier.render_digest(
        jobs=[sample_job],
        config=config,
        income_opportunities=[sample_income_opp],
    )

    # HTML assertions
    assert "Target Career & Employment Opportunities" in html_content
    assert "Verified Online Income & Flexible Remote Tracks" in html_content
    assert "Senior Financial Analyst" in html_content
    assert "Moniepoint" in html_content
    assert "AI Evaluation Specialist" in html_content
    assert "DataAnnotation.tech" in html_content
    assert "$20 - $40 / hr" in html_content
    assert "Scam-Screened" in html_content
    assert "https://www.dataannotation.tech/apply" in html_content
    assert "https://boards.greenhouse.io/moniepoint/jobs/101" in html_content

    # Plaintext assertions
    assert "TARGET CAREER & EMPLOYMENT OPPORTUNITIES" in text_content
    assert "VERIFIED ONLINE INCOME & FLEXIBLE REMOTE TRACKS" in text_content
    assert "Senior Financial Analyst" in text_content
    assert "AI Evaluation Specialist - Reasoning & Logic" in text_content


def test_render_income_only_digest(sample_income_opp):
    config = AppConfig()
    notifier = EmailNotifier()

    subject, html_content, text_content = notifier.render_digest(
        jobs=[],
        config=config,
        income_opportunities=[sample_income_opp],
    )

    assert "Verified Online Income Tracks" in html_content
    assert "DataAnnotation.tech" in html_content
    assert "Target Career & Employment Opportunities" not in html_content


@pytest.mark.anyio
async def test_job_pipeline_unified_execution(tmp_path, sample_job, sample_income_opp):
    """Verifies that JobPipeline concurrently executes and unifies career & income opportunities."""
    state_file = tmp_path / "seen_jobs.json"
    income_state_file = tmp_path / "seen_income.json"

    state_mgr = StateManager(filepath=state_file)
    income_state_mgr = IncomeStateManager(filepath=income_state_file)

    config = AppConfig()
    config.online_income.enabled = True
    config.online_income.include_in_daily_digest = True
    config.online_income.require_link_verification = False
    config.link_verification.enabled = False
    config.delivery.send_daily_digest = True

    pipeline = JobPipeline(
        config=config,
        state_manager=state_mgr,
        income_state_manager=income_state_mgr,
    )

    # Mock collectors
    mock_jobs = [sample_job.job]
    mock_job_health = [CrawlerHealth(source_name="greenhouse", status="healthy", jobs_found=1, latency_ms=100.0)]

    mock_income = [sample_income_opp.opportunity]
    mock_income_health = [IncomeCollectorHealth(source_name="ai_evaluation", status="healthy", items_fetched=1, execution_time_seconds=0.1)]

    with patch("src.pipeline.run_all_collectors", new_callable=AsyncMock) as mock_rc, \
         patch("src.pipeline.run_all_income_collectors", new_callable=AsyncMock) as mock_ric, \
         patch.object(pipeline.notifier, "send_digest", new_callable=AsyncMock) as mock_send_digest:

        mock_rc.return_value = (mock_jobs, mock_job_health)
        mock_ric.return_value = (mock_income, mock_income_health)
        mock_send_digest.return_value = True

        summary, scored_jobs = await pipeline.execute(
            dry_run=False,
            send_email=True,
            force_all=True,
        )

        assert summary.total_fetched == 2
        assert len(scored_jobs) == 1
        assert len(pipeline.latest_income_opportunities) == 1

        # Verify send_digest was called with both career jobs and income opportunities
        assert mock_send_digest.called
        call_args = mock_send_digest.call_args
        assert len(call_args.kwargs.get("jobs", [])) >= 1
        assert len(call_args.kwargs.get("income_opportunities", [])) >= 1

        # Verify both state managers recorded items
        assert state_mgr.is_seen(sample_job.job.fingerprint)
        assert income_state_mgr.is_seen(sample_income_opp.opportunity.fingerprint)


@pytest.mark.anyio
async def test_job_pipeline_income_disabled(tmp_path, sample_job):
    """Verifies that income tracks are not collected when include_in_daily_digest is False."""
    state_mgr = StateManager(filepath=tmp_path / "seen_jobs.json")
    income_state_mgr = IncomeStateManager(filepath=tmp_path / "seen_income.json")

    config = AppConfig()
    config.online_income.include_in_daily_digest = False

    pipeline = JobPipeline(
        config=config,
        state_manager=state_mgr,
        income_state_manager=income_state_mgr,
    )

    mock_jobs = [sample_job.job]
    mock_job_health = [CrawlerHealth(source_name="greenhouse", status="healthy", jobs_found=1, latency_ms=100.0)]

    with patch("src.pipeline.run_all_collectors", new_callable=AsyncMock) as mock_rc, \
         patch("src.pipeline.run_all_income_collectors", new_callable=AsyncMock) as mock_ric:

        mock_rc.return_value = (mock_jobs, mock_job_health)

        summary, scored_jobs = await pipeline.execute(dry_run=True, send_email=False)

        assert mock_rc.called
        assert not mock_ric.called
        assert len(pipeline.latest_income_opportunities) == 0


@pytest.mark.anyio
async def test_job_pipeline_previously_alerted_suppressed(tmp_path, sample_job, sample_income_opp):
    """Verifies that previously alerted jobs and income tracks are never re-sent in daily alerts."""
    state_file = tmp_path / "seen_jobs_alerted.json"
    income_state_file = tmp_path / "seen_income_alerted.json"

    state_mgr = StateManager(filepath=state_file)
    income_state_mgr = IncomeStateManager(filepath=income_state_file)

    # 1. Pre-record the existing sample_job and sample_income_opp as ALREADY ALERTED
    state_mgr.record_job(sample_job.job, score=sample_job.score, action=sample_job.action, alerted=True)
    state_mgr.save()
    assert state_mgr.is_alerted(sample_job.job.fingerprint) is True

    income_state_mgr.record_opportunity(sample_income_opp.opportunity, score=sample_income_opp.score, action=sample_income_opp.action, alerted=True)
    income_state_mgr.save()
    assert income_state_mgr.is_alerted(sample_income_opp.opportunity.fingerprint) is True

    # 2. Create a brand NEW unalerted job
    new_job = JobPosting(
        id="new_career_2",
        fingerprint="fp_career_sample_2",
        title="Finance Director",
        company="Flutterwave",
        location="Worldwide Remote",
        is_remote=True,
        remote_scope="Worldwide",
        url="https://boards.greenhouse.io/flutterwave/jobs/202",
        salary_min=120000.0,
        salary_max=160000.0,
        source="greenhouse",
        posted_at=datetime.now(timezone.utc),
    )

    config = AppConfig()
    config.online_income.enabled = True
    config.online_income.include_in_daily_digest = True
    config.online_income.require_link_verification = False
    config.link_verification.enabled = False
    config.delivery.send_daily_digest = True

    pipeline = JobPipeline(
        config=config,
        state_manager=state_mgr,
        income_state_manager=income_state_mgr,
    )

    mock_jobs = [sample_job.job, new_job]
    mock_job_health = [CrawlerHealth(source_name="greenhouse", status="healthy", jobs_found=2, latency_ms=100.0)]
    mock_income = [sample_income_opp.opportunity]
    mock_income_health = [IncomeCollectorHealth(source_name="ai_evaluation", status="healthy", items_fetched=1, execution_time_seconds=0.1)]

    with patch("src.pipeline.run_all_collectors", new_callable=AsyncMock) as mock_rc, \
         patch("src.pipeline.run_all_income_collectors", new_callable=AsyncMock) as mock_ric, \
         patch.object(pipeline.notifier, "send_digest", new_callable=AsyncMock) as mock_send_digest:

        mock_rc.return_value = (mock_jobs, mock_job_health)
        mock_ric.return_value = (mock_income, mock_income_health)
        mock_send_digest.return_value = True

        summary, scored_jobs = await pipeline.execute(
            dry_run=False,
            send_email=True,
            force_all=True,
        )

        assert mock_send_digest.called
        call_args = mock_send_digest.call_args

        sent_jobs = call_args.kwargs.get("jobs", [])
        sent_income = call_args.kwargs.get("income_opportunities", [])

        # The previously alerted job MUST NOT be in sent_jobs
        sent_job_fps = [j.job.fingerprint for j in sent_jobs]
        assert sample_job.job.fingerprint not in sent_job_fps
        assert new_job.fingerprint in sent_job_fps

        # The previously alerted income track MUST NOT be in sent_income
        sent_income_fps = [o.opportunity.fingerprint for o in sent_income]
        assert sample_income_opp.opportunity.fingerprint not in sent_income_fps
        assert len(sent_income) == 0
