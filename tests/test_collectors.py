"""
Unit tests for job collectors, parsing, stable identities and health reporting.
"""

import asyncio
import json

import httpx

from src import paths
from src.collectors.custom import CustomJobCollector, add_custom_job, custom_job_id
from src.collectors.greenhouse import GreenhouseCollector
from src.collectors.hackernews import HackerNewsCollector
from src.collectors.jobicy import JobicyCollector
from src.collectors.lever import LeverCollector
from src.collectors.remotive import parse_salary_string
from src.collectors.rss import RSSCollector
from src.collectors.twitter import TwitterCollector
from src.config import AppConfig, RSSFeedConfig
from src.deduplication import stable_hash


def use_transport(collector, handler):
    """Routes a collector's HTTP client through an in-memory handler."""
    collector.create_http_client = lambda *args, **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )
    return collector


def test_parse_salary_string():
    assert parse_salary_string("$120k - $160k") == (120000.0, 160000.0)
    assert parse_salary_string("110,000 - 150,000 USD") == (110000.0, 150000.0)
    assert parse_salary_string("$140k") == (140000.0, 140000.0)
    assert parse_salary_string("$31,2k- $52k") == (31200.0, 52000.0)
    assert parse_salary_string("") == (None, None)


def test_greenhouse_collector_disabled():
    config = AppConfig()
    config.sources.greenhouse.enabled = False
    assert asyncio.run(GreenhouseCollector().collect(config)) == []


def test_lever_collector_disabled():
    config = AppConfig()
    config.sources.lever.enabled = False
    assert asyncio.run(LeverCollector().collect(config)) == []


def test_disabled_source_reports_disabled_status():
    config = AppConfig()
    config.sources.lever.enabled = False
    collector = LeverCollector()
    asyncio.run(collector.execute(config))
    assert collector.health.status == "disabled"


def test_http_failures_are_reported_as_degraded():
    def handler(request):
        if "/boards/missing/" in request.url.path:
            return httpx.Response(404)
        return httpx.Response(200, json={"jobs": [{"id": 1, "title": "HR Generalist", "location": {"name": "Remote"},
                                                   "absolute_url": "https://boards.greenhouse.io/acme/jobs/1",
                                                   "first_published": "2026-09-01T10:00:00Z", "content": "&lt;p&gt;HR&lt;/p&gt;"}]})

    config = AppConfig()
    config.sources.greenhouse.companies = ["acme", "missing"]
    collector = use_transport(GreenhouseCollector(), handler)
    jobs = asyncio.run(collector.execute(config))

    assert len(jobs) == 1
    assert jobs[0].description == "HR"
    assert jobs[0].posted_at.year == 2026
    assert collector.health.status == "degraded"
    assert "greenhouse/missing: HTTP 404" in collector.health.error_message


def test_source_returning_nothing_is_degraded():
    config = AppConfig()
    config.sources.greenhouse.companies = ["acme"]
    collector = use_transport(GreenhouseCollector(), lambda request: httpx.Response(200, json={"jobs": []}))
    asyncio.run(collector.execute(config))
    assert collector.health.status == "degraded"
    assert collector.health.error_message == "No postings returned"


def test_custom_job_collector():
    add_custom_job(
        title="Staff Engineer",
        company="Anthropic",
        location="Remote",
        url="https://example.com/anthropic",
        description="Go and Kubernetes",
        salary_min=190000,
        salary_max=250000,
    )
    jobs = asyncio.run(CustomJobCollector().collect(AppConfig()))
    assert len(jobs) == 1
    assert jobs[0].title == "Staff Engineer"
    assert jobs[0].salary_min == 190000.0
    assert jobs[0].source == "custom"


def test_custom_job_without_salary_does_not_hide_other_jobs():
    add_custom_job(title="Older Role", company="Acme", url="https://acme.test/1", salary_min=50000)
    add_custom_job(title="New Role Without Salary", company="Beta", url="https://beta.test/2")  # stored first, salary null
    collector = CustomJobCollector()
    jobs = asyncio.run(collector.execute(AppConfig()))
    assert {j.title for j in jobs} == {"Older Role", "New Role Without Salary"}
    assert collector.health.status == "healthy"


def test_custom_job_ids_are_stable_and_unique():
    legacy_entry = {"title": "Finance Accountant", "company": "Moniepoint", "url": "https://www.jobberman.com"}
    paths.data_file(paths.CUSTOM_JOBS).write_text(json.dumps([legacy_entry]))
    first = asyncio.run(CustomJobCollector().collect(AppConfig()))[0].id
    second = asyncio.run(CustomJobCollector().collect(AppConfig()))[0].id
    assert first == second == f"custom_{custom_job_id(legacy_entry)}"

    created = add_custom_job(title="Another", company="Moniepoint", url="https://www.jobberman.com")
    assert created["id"] and created["id"] != custom_job_id(legacy_entry)


def test_rss_collector_parses_rss_and_atom():
    rss = """<rss version="2.0"><channel><item><title>Remote HR Manager</title><link>https://careers.test/1</link>
             <guid>job-1</guid><description>&lt;p&gt;Fully remote&lt;/p&gt;</description>
             <pubDate>Tue, 15 Sep 2026 10:00:00 GMT</pubDate></item></channel></rss>"""
    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Recruiter</title>
              <link rel="alternate" href="https://careers.test/2"/><id>tag:2</id><summary>Remote</summary>
              <updated>2026-09-15T10:00:00Z</updated></entry></feed>"""

    config = AppConfig()
    config.sources.rss_feeds = [RSSFeedConfig(name="rss_feed", url="https://feeds.test/rss"),
                                RSSFeedConfig(name="atom_feed", url="https://feeds.test/atom")]
    collector = use_transport(RSSCollector(), lambda request: httpx.Response(200, text=rss if request.url.path.endswith("rss") else atom))
    jobs = asyncio.run(collector.execute(config))

    assert [(j.title, j.url) for j in jobs] == [("Remote HR Manager", "https://careers.test/1"), ("Recruiter", "https://careers.test/2")]
    assert jobs[0].description == "Fully remote"
    assert jobs[0].id == f"rss_rss_feed_{stable_hash('job-1')}"  # derived from the guid, identical on every run


def test_jobicy_sends_no_geo_filter_and_keeps_country_scope():
    seen_params = {}

    def handler(request):
        seen_params.update(dict(request.url.params))
        return httpx.Response(200, json={"jobs": [
            {"id": 7, "jobTitle": "HR Partner", "companyName": "Acme", "jobGeo": "Germany", "url": "https://jobicy.test/7",
             "jobType": ["Contract"], "salaryMin": 4000, "salaryMax": 5000, "salaryCurrency": "EUR", "salaryPeriod": "monthly",
             "pubDate": "2026-09-18T14:43:04+00:00"},
        ]})

    jobs = asyncio.run(use_transport(JobicyCollector(), handler).execute(AppConfig()))
    assert "geo" not in seen_params
    assert jobs[0].remote_scope == "Germany"
    assert (jobs[0].salary_currency, jobs[0].salary_period, jobs[0].employment_type) == ("EUR", "monthly", "contract")


def test_hackernews_reads_latest_thread_top_level_comments_only():
    def handler(request):
        if request.url.path.endswith("search_by_date"):
            return httpx.Response(200, json={"hits": [
                {"objectID": "500", "title": "Ask HN: Who wants to be hired? (September 2026)"},
                {"objectID": "501", "title": "Ask HN: Who is hiring? (September 2026)"},
                {"objectID": "400", "title": "Ask HN: Who is hiring? (August 2026)"},
            ]})
        assert request.url.params["tags"] == "comment,story_501"
        return httpx.Response(200, json={"nbPages": 1, "hits": [
            {"objectID": "601", "parent_id": 501, "created_at_i": 1788000000,
             "comment_text": "Acme | People Partner | Remote (Worldwide) | $90k - $120k<p>We are hiring."},
            {"objectID": "602", "parent_id": 601, "comment_text": "Is this role still open?"},
        ]})

    jobs = asyncio.run(use_transport(HackerNewsCollector(), handler).execute(AppConfig()))
    assert len(jobs) == 1
    assert (jobs[0].company, jobs[0].title, jobs[0].salary_min, jobs[0].salary_max) == ("Acme", "People Partner", 90000.0, 120000.0)


def test_twitter_collector_disabled():
    config = AppConfig()
    config.sources.twitter.enabled = False
    assert asyncio.run(TwitterCollector().collect(config)) == []


def test_twitter_collector_rss_parsing():
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
    jobs = TwitterCollector()._parse_nitter_rss(sample_rss, default_company="Moniepoint")
    assert len(jobs) == 1
    assert "Python Engineer" in jobs[0].title or "Senior Python" in jobs[0].title
    assert jobs[0].source == "twitter"
    assert jobs[0].is_remote is True
    assert jobs[0].url == "https://t.co/xyz123"
    assert jobs[0].id == "twitter_1234567890"


def test_twitter_links_come_from_tweet_text_not_mirror_html():
    sample_rss = """<rss version="2.0"><channel><item><title>Hiring</title>
      <description><![CDATA[<p>We are hiring a Recruiter <a href="https://nitter.poast.org/search?q=%23hiring">#hiring</a> apply https://jobs.acme.test/42</p>]]></description>
      <link>https://nitter.poast.org/acme/status/42</link></item></channel></rss>"""
    jobs = TwitterCollector()._parse_nitter_rss(sample_rss, default_company="acme")
    assert jobs[0].url == "https://jobs.acme.test/42"
