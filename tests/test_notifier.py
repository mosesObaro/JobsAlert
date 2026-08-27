"""
Unit tests for the email notification service and templating.
"""

from datetime import datetime, timezone
import pytest

from src.config import AppConfig
from src.models import JobPosting, MatchBreakdown, ScoredJob
from src.notifier.email_service import EmailNotifier


@pytest.fixture
def sample_scored_jobs():
    job1 = JobPosting(
        id="sample_1",
        title="Staff Distributed Systems Engineer",
        company="Cloudflare",
        location="Worldwide Remote",
        is_remote=True,
        remote_scope="Worldwide",
        url="https://boards.greenhouse.io/cloudflare/jobs/9999",
        salary_min=180000.0,
        salary_max=240000.0,
        source="greenhouse",
        posted_at=datetime.now(timezone.utc),
    )
    breakdown1 = MatchBreakdown(
        title_score=18.0,
        stack_score=18.0,
        location_score=20.0,
        compensation_score=15.0,
        company_score=15.0,
        recency_score=10.0,
        highlights=[
            "Role matches target 'Staff Distributed Systems Engineer'",
            "Aligned core skills: Go, Kubernetes, Distributed Systems",
            "Top-tier compensation: $180,000 - $240,000",
            "Priority Watchlist Company: Cloudflare (1.3x boost)",
        ],
    )
    return [ScoredJob(job=job1, score=9.5, action="instant", breakdown=breakdown1)]


def test_render_digest_email(sample_scored_jobs):
    config = AppConfig()
    notifier = EmailNotifier()

    subject, html_content, text_content = notifier.render_digest(sample_scored_jobs, config)

    assert "High-Match" in subject
    assert "Cloudflare" in html_content
    assert "9.5/10 Match" in html_content
    assert "Why You Match" in html_content
    assert "$180,000" in html_content
    assert "https://boards.greenhouse.io/cloudflare/jobs/9999" in html_content

    assert "Staff Distributed Systems Engineer" in text_content
    assert "Cloudflare" in text_content


def test_console_preview_dispatch(sample_scored_jobs):
    import asyncio
    config = AppConfig()
    config.delivery.email_provider = "console"
    notifier = EmailNotifier()

    success = asyncio.run(notifier.send_digest(sample_scored_jobs, config, dry_run=True))
    assert success is True

