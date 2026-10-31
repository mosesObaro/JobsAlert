"""
Unit tests for the LinkedIn guest search collector.

The fragments below follow the markup the live endpoint returned on 2026-10-23:
an unwrapped list of `<li>` cards carrying `data-entity-urn`, a full-link anchor
with per-click tracking, and a `<time datetime="YYYY-MM-DD">`. The salary span in
CARD_WITH_SALARY was not present in any sampled response; it covers the
best-effort branch for when LinkedIn does include one.
"""

import asyncio
import re

import httpx
import pytest
from pydantic import ValidationError

from src.collectors.linkedin import (
    LinkedInCollector,
    canonical_job_url,
    parse_card,
    split_cards,
    strip_tracking,
)
from src.config import AppConfig, LinkedInSearchConfig


def card(job_id: str, title: str, company: str, location: str, host: str = "ng.linkedin.com", posted: str = "2026-10-23", extra: str = "") -> str:
    slug = title.lower().replace(" ", "-").replace(",", "")
    return f'''
      <li>
      <div class="base-card relative w-full hover:no-underline focus:no-underline
        base-card--link
         base-search-card base-search-card--link job-search-card" data-entity-urn="urn:li:jobPosting:{job_id}" data-impression-id="jobs-search-result-0" data-reference-id="wXZGpXd4hjzVY/Qfm9BvTg==" data-tracking-id="VxnnlECHCbX+xrLgUmin2g==" data-column="1" data-row="1">
        <a class="base-card__full-link absolute top-0 right-0 bottom-0 left-0 p-0 z-[2] outline-offset-[4px]" href="https://{host}/jobs/view/{slug}-at-acme-{job_id}?position=1&amp;pageNum=0&amp;refId=wXZGpXd4hjzVY%2FQfm9BvTg%3D%3D&amp;trackingId=VxnnlECHCbX%2BxrLgUmin2g%3D%3D" data-tracking-control-name="public_jobs_jserp-result_search-card" data-tracking-will-navigate>
          <span class="sr-only">
        {title}
          </span>
        </a>
        <div class="base-search-card__info">
          <h3 class="base-search-card__title">
        {title}
          </h3>
            <h4 class="base-search-card__subtitle">
          <a class="hidden-nested-link" data-tracking-control-name="public_jobs_jserp-result_job-search-card-subtitle" data-tracking-will-navigate href="https://{host}/company/acme?trk=public_jobs_jserp-result_job-search-card-subtitle">
            {company}
          </a>
            </h4>
<!---->
            <div class="base-search-card__metadata">
          <span class="job-search-card__location">
            {location}
          </span>
<!---->
          <time class="job-search-card__listdate--new" datetime="{posted}">
      10 hours ago
          </time>
{extra}
            </div>
        </div>
      </div>
      </li>'''


PAGE = "<!DOCTYPE html>" + card("4480647306", "Monitoring, Evaluation and Learning (MEL) Specialist", "Sydani Group", "Federal Capital Territory, Nigeria")
CARD_WITH_SALARY = card(
    "4463989511", "Credit Risk Analyst", "Moniepoint Group", "Lagos, Nigeria (Remote)",
    host="www.linkedin.com",
    extra='<span class="job-search-card__salary-info">$90,000 - $120,000</span>',
)


# The variant LinkedIn serves for some results: a bare wrapping anchor opened
# before `data-entity-urn`, no inner full-link, a plain-text subtitle and a
# benefits block between the location and the date.
WRAPPED_CARD = '''
      <li>
      <a href="https://in.linkedin.com/jobs/view/hr-generalist-hr-recruitment-manager-4480687258?position=9&amp;pageNum=0&amp;refId=lA37RenkazmmGQe9t7%2BXuQ%3D%3D&amp;trackingId=07NEDM7W2Ga6WEbnmXKDGA%3D%3D" class="base-card">
      <div class="base-card relative w-full job-search-card" data-entity-urn="urn:li:jobPosting:4480687258" data-reference-id="lA37RenkazmmGQe9t7+XuQ==" data-column="1" data-row="9">
        <div class="base-search-card__info">
          <h3 class="base-search-card__title">
        HR Generalist / HR &amp; Recruitment Manager
          </h3>
            <h4 class="base-search-card__subtitle">
          Shreesto
            </h4>
<!---->
            <div class="base-search-card__metadata">
          <span class="job-search-card__location">
            Surat, Gujarat, India
          </span>
      <div class="job-posting-benefits text-sm">
        <span class="job-posting-benefits__text">
          Be an early applicant
<!---->        </span>
      </div>
          <time class="job-search-card__listdate--new" datetime="2026-10-23">
      4 hours ago
          </time>
<!---->
            </div>
        </div>
<!---->
      </div>
      </a>
      </li>'''


def use_transport(collector, handler):
    """Routes a collector's HTTP client through an in-memory handler."""
    collector.create_http_client = lambda *args, **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )
    return collector


def configure(**search_fields) -> AppConfig:
    config = AppConfig()
    config.sources.linkedin.request_delay_seconds = 0  # no pacing in tests
    config.sources.linkedin.searches = [LinkedInSearchConfig(**search_fields)]
    return config


# --- parsing ----------------------------------------------------------------

def test_split_cards_finds_every_posting():
    assert [job_id for job_id, _ in split_cards(PAGE + CARD_WITH_SALARY)] == ["4480647306", "4463989511"]
    assert split_cards("") == []
    assert split_cards("<html>no cards here</html>") == []


def test_parse_card_reads_the_standard_fields():
    job_id, markup = split_cards(PAGE)[0]
    job = parse_card(job_id, markup, "contract")

    assert job.id == "linkedin_4480647306"
    assert job.title == "Monitoring, Evaluation and Learning (MEL) Specialist"
    assert job.company == "Sydani Group"
    assert job.location == "Federal Capital Territory, Nigeria"
    assert job.employment_type == "contract"
    assert job.source == "linkedin"
    assert job.posted_at.date().isoformat() == "2026-10-23"
    assert job.is_remote is False
    assert job.remote_scope == "Unspecified"


def test_parse_card_reads_remote_and_salary_when_present():
    job_id, markup = split_cards(CARD_WITH_SALARY)[0]
    job = parse_card(job_id, markup, "contract")

    assert job.is_remote is True
    assert job.remote_scope == "Lagos, Nigeria (Remote)"
    assert (job.salary_min, job.salary_max) == (90000.0, 120000.0)
    assert job.salary_currency == "USD"


def test_parse_card_skips_markup_without_a_readable_title():
    no_title = PAGE.replace("base-search-card__title", "base-search-card__renamed")
    assert parse_card(*split_cards(no_title)[0], "contract") is None


def test_card_wrapped_in_a_bare_anchor_is_still_parsed():
    """About one card in ten wraps the whole card in an unclassed <a> ahead of
    the urn, and has no inner base-card__full-link."""
    job_id, markup = split_cards(WRAPPED_CARD)[0]
    job = parse_card(job_id, markup, "contract")

    assert job is not None
    assert job.id == "linkedin_4480687258"
    assert job.title == "HR Generalist / HR & Recruitment Manager"
    assert job.company == "Shreesto"  # subtitle without a nested anchor
    assert job.location == "Surat, Gujarat, India"
    assert job.url == canonical_job_url("4480687258")
    assert job.raw_url == "https://in.linkedin.com/jobs/view/hr-generalist-hr-recruitment-manager-4480687258"


def test_a_card_with_no_link_at_all_still_yields_a_posting():
    """`url` comes from the posting id, so a missing anchor is not fatal."""
    stripped = re.sub(r"<a\b[^>]*>", "<span>", PAGE)
    job = parse_card(*split_cards(stripped)[0], "contract")

    assert job is not None
    assert job.url == canonical_job_url("4480647306")
    assert job.raw_url is None


# --- URLs -------------------------------------------------------------------

def test_strip_tracking_removes_click_parameters_and_keeps_the_rest():
    stripped = strip_tracking(
        "https://ng.linkedin.com/jobs/view/analyst-at-acme-123"
        "?position=1&amp;pageNum=0&amp;refId=abc%3D%3D&amp;trackingId=def%3D%3D&amp;currentJobId=123"
    )
    assert stripped == "https://ng.linkedin.com/jobs/view/analyst-at-acme-123?currentJobId=123"
    assert strip_tracking("") == ""


def test_canonical_url_is_identical_across_subdomains_and_slugs():
    """The same posting seen twice must not become two records."""
    first = card("999", "Data Analyst", "Acme", "Lagos, Nigeria", host="ng.linkedin.com")
    second = card("999", "Data Analyst - Contract", "Acme", "Remote", host="uk.linkedin.com")
    a = parse_card(*split_cards(first)[0], "contract")
    b = parse_card(*split_cards(second)[0], "contract")

    assert a.url == b.url == canonical_job_url("999") == "https://www.linkedin.com/jobs/view/999"
    assert "refId" not in a.raw_url and "trackingId" not in a.raw_url
    assert a.raw_url.startswith("https://ng.linkedin.com/jobs/view/")


def test_prepare_canonicalizes_and_fingerprints():
    from src.deduplication import canonicalize_url

    collector = LinkedInCollector()
    job = parse_card(*split_cards(PAGE)[0], "contract")
    collector.prepare([job])

    assert job.url == canonicalize_url(canonical_job_url("4480647306"))
    assert job.fingerprint


# --- requests ---------------------------------------------------------------

def test_disabled_source_makes_no_request_and_reports_disabled():
    config = configure(keywords="data analyst")
    config.sources.linkedin.enabled = False
    collector = LinkedInCollector()
    assert asyncio.run(collector.collect(config)) == []
    asyncio.run(collector.execute(config))
    assert collector.health.status == "disabled"


def test_query_parameters_carry_the_configured_filters():
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(200, text=PAGE)

    config = configure(keywords="data analyst", location="Nigeria", job_type="C", time_posted="r604800", max_results=10)
    jobs = asyncio.run(use_transport(LinkedInCollector(), handler).collect(config))

    assert len(jobs) == 1
    assert seen[0] == {
        "keywords": "data analyst", "location": "Nigeria",
        "f_JT": "C", "f_TPR": "r604800", "start": "0",
    }
    assert jobs[0].employment_type == "contract"


def test_time_window_is_omitted_when_blank_and_remote_filter_is_opt_in():
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(200, text=PAGE)

    config = configure(keywords="ios", time_posted="", remote_only=True, max_results=10)
    asyncio.run(use_transport(LinkedInCollector(), handler).collect(config))

    assert "f_TPR" not in seen[0]
    assert seen[0]["f_WT"] == "2"


def test_remote_filtered_search_marks_postings_remote():
    """f_WT=2 results name the hiring office, not the arrangement, so the
    requested filter is what tells us the role is remote."""
    def handler(request):
        return httpx.Response(200, text=card("777", "HR Generalist", "iSuite", "Charlotte, NC"))

    on_site = asyncio.run(use_transport(LinkedInCollector(), handler).collect(
        configure(keywords="hr", remote_only=False, max_results=10)))
    remote = asyncio.run(use_transport(LinkedInCollector(), handler).collect(
        configure(keywords="hr", remote_only=True, max_results=10)))

    assert on_site[0].is_remote is False and on_site[0].remote_scope == "Unspecified"
    assert remote[0].is_remote is True and remote[0].remote_scope == "Charlotte, NC"


def test_job_type_selects_the_employment_type():
    def handler(request):
        return httpx.Response(200, text=PAGE)

    config = configure(keywords="intern", job_type="I", max_results=10)
    jobs = asyncio.run(use_transport(LinkedInCollector(), handler).collect(config))
    assert jobs[0].employment_type == "internship"


# --- paging and failure modes -----------------------------------------------

def full_page(start: int) -> str:
    return "".join(card(str(start + n), f"Analyst {start + n}", "Acme", "Lagos, Nigeria") for n in range(10))


def test_paging_stops_on_a_short_page():
    starts = []

    def handler(request):
        start = int(request.url.params["start"])
        starts.append(start)
        return httpx.Response(200, text=full_page(start) if start == 0 else PAGE)

    jobs = asyncio.run(use_transport(LinkedInCollector(), handler).collect(configure(keywords="analyst", max_results=30)))

    assert starts == [0, 10]  # the second page returned one card, so paging stopped
    assert len(jobs) == 11


def test_paging_respects_max_results():
    def handler(request):
        return httpx.Response(200, text=full_page(int(request.url.params["start"])))

    jobs = asyncio.run(use_transport(LinkedInCollector(), handler).collect(configure(keywords="analyst", max_results=15)))
    assert len(jobs) == 15


def test_pagination_is_capped_even_for_a_large_max_results():
    starts = []

    def handler(request):
        starts.append(int(request.url.params["start"]))
        return httpx.Response(200, text=full_page(len(starts) * 100))

    asyncio.run(use_transport(LinkedInCollector(), handler).collect(configure(keywords="analyst", max_results=500)))
    assert starts == [0, 10, 20]  # MAX_PAGES


def test_rate_limited_search_keeps_earlier_results_and_degrades():
    def handler(request):
        if int(request.url.params["start"]) == 0:
            return httpx.Response(200, text=full_page(0))
        return httpx.Response(429, text="<html>rate limited</html>")

    collector = use_transport(LinkedInCollector(), handler)
    jobs = asyncio.run(collector.execute(configure(keywords="analyst", max_results=30)))

    assert len(jobs) == 10
    assert collector.health.status == "degraded"
    assert "429" in collector.health.error_message


def test_duplicate_postings_across_searches_are_collected_once():
    def handler(request):
        return httpx.Response(200, text=PAGE)

    config = configure(keywords="first", max_results=10)
    config.sources.linkedin.searches.append(LinkedInSearchConfig(keywords="second", max_results=10))
    jobs = asyncio.run(use_transport(LinkedInCollector(), handler).collect(config))
    assert len(jobs) == 1


def test_search_without_keywords_is_reported_and_sends_nothing():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=PAGE)

    collector = use_transport(LinkedInCollector(), handler)
    jobs = asyncio.run(collector.execute(configure(keywords="   ", name="broken")))

    assert jobs == [] and requests == []
    assert collector.health.status == "degraded"
    assert "no keywords" in collector.health.error_message


def test_empty_result_set_is_not_treated_as_a_failure():
    """A narrow contract search over 24 hours can legitimately return nothing."""
    def handler(request):
        return httpx.Response(200, text="<!DOCTYPE html>\n")

    collector = use_transport(LinkedInCollector(), handler)
    jobs = asyncio.run(collector.execute(configure(keywords="data analyst")))

    assert jobs == []
    assert collector.health.status == "healthy"


# --- configuration validation -----------------------------------------------

def test_job_type_and_time_window_are_validated():
    assert LinkedInSearchConfig(keywords="x", job_type="c").job_type == "C"
    assert LinkedInSearchConfig(keywords="x", time_posted=" r86400 ").time_posted == "r86400"
    with pytest.raises(ValidationError):
        LinkedInSearchConfig(keywords="x", job_type="Z")
    with pytest.raises(ValidationError):
        LinkedInSearchConfig(keywords="x", time_posted="last week")


def test_linkedin_is_registered_in_the_collector_registry():
    from src.collectors import get_all_collectors

    assert "linkedin" in [collector.name for collector in get_all_collectors()]
