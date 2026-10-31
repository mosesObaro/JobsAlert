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

    result = asyncio.run(notifier.send_digest(sample_scored_jobs, config, dry_run=True))
    assert result.ok
    assert result.provider == "console"



# --- link rendering in strict clients ---------------------------------------

def _anchors(markup: str):
    """Anchors as a parser sees them, with attributes and visible text."""
    from html.parser import HTMLParser

    class Collector(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.found, self.current = [], None

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.current = {"attrs": dict(attrs), "text": ""}

        def handle_endtag(self, tag):
            if tag == "a" and self.current is not None:
                self.found.append(self.current)
                self.current = None

        def handle_data(self, data):
            if self.current is not None:
                self.current["text"] += data

    collector = Collector()
    collector.feed(markup)
    return collector.found


def without_style_block(markup: str) -> str:
    """The same email as a client that drops <style> blocks would see it."""
    import re

    return re.sub(r"<style.*?</style>", "", markup, flags=re.DOTALL)


def test_job_links_survive_a_client_that_drops_style_blocks(sample_scored_jobs):
    """Gmail's mobile apps mangle <head> styles. A button whose colour comes
    from a stripped stylesheet can render white-on-white and be untappable, so
    the critical styles are inline and the title is a link in its own right."""
    _, html, _ = EmailNotifier().render_digest(jobs=sample_scored_jobs, config=AppConfig())
    target = sample_scored_jobs[0].job.url

    for label, markup in (("full", html), ("no stylesheet", without_style_block(html))):
        links = [a for a in _anchors(markup) if a["attrs"].get("href") == target]
        assert len(links) >= 2, f"{label}: expected the title and the button to link to the job"
        assert any("Apply" in a["text"] for a in links), f"{label}: no apply button"
        assert any(sample_scored_jobs[0].job.title in a["text"] for a in links), f"{label}: title is not a link"
        for anchor in links:
            assert anchor["attrs"].get("style"), f"{label}: {anchor['text'].strip()!r} relies on the stylesheet alone"


def test_no_link_sets_a_light_colour_without_its_background(sample_scored_jobs):
    """The white-on-white failure: colour and background must travel together."""
    _, html, _ = EmailNotifier().render_digest(jobs=sample_scored_jobs, config=AppConfig())

    for anchor in _anchors(html):
        style = (anchor["attrs"].get("style") or "").replace(" ", "").lower()
        if "color:#ffffff" in style or "color:#fff;" in style:
            assert "background-color:" in style, f"{anchor['text'].strip()!r} would be invisible without its stylesheet"


def test_every_apply_button_in_every_template_carries_inline_styles():
    """Covers the instant and income templates, which the digest test misses."""
    from pathlib import Path

    templates = Path("src/notifier/templates")
    for name in ("digest.html", "immediate.html", "income_digest.html", "income_immediate.html"):
        body = (templates / name).read_text()
        for marker in ('class="apply-btn"', 'class="apply-btn-income"', 'class="btn"'):
            start = 0
            while (index := body.find(marker, start)) != -1:
                tag_end = body.find(">", index)
                assert "style=" in body[index:tag_end], f"{name}: {marker} has no inline style"
                start = tag_end
