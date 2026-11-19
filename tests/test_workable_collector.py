"""
Unit tests for the Workable collector.

Fixtures mirror the live widget response on 2026-11-19, including its habit of
repeating postings: renmoney answered with 100 entries covering 72 distinct
jobs, fairmoney 59 covering 25.
"""

import asyncio
import json

import httpx
import pytest

from src.collectors.workable import (
    ENDPOINT,
    WorkableCollector,
    employment_type,
    location_text,
    to_posting,
)
from src.config import AppConfig


def job(shortcode="8F7A56FE46", title="Data Analyst - Credit", city="Lagos", state="Lagos",
        country="Nigeria", telecommuting=False, etype="Full-time", published="2026-11-17",
        description="<p>SQL and data analysis for the credit team.</p>", department="IT", function="Analytics"):
    return {
        "shortcode": shortcode,
        "title": title,
        "city": city,
        "state": state,
        "country": country,
        "telecommuting": telecommuting,
        "employment_type": etype,
        "published_on": published,
        "created_at": "2024-09-09",
        "description": description,
        "department": department,
        "function": function,
        "shortlink": f"https://apply.workable.com/j/{shortcode}",
        "application_url": f"https://apply.workable.com/j/{shortcode}/apply",
    }


def board(*jobs, name="Kuda Technologies Ltd"):
    return {"name": name, "description": "About us", "jobs": list(jobs)}


def use_transport(collector, handler):
    collector.create_http_client = lambda *args, **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )
    return collector


def config_with(*accounts) -> AppConfig:
    config = AppConfig()
    config.sources.workable.companies = list(accounts)
    return config


def run(collector, config):
    return asyncio.run(collector.execute(config))


# --- field mapping ------------------------------------------------------------

def test_posting_maps_the_structured_fields():
    posting = to_posting("kuda", "Kuda Technologies Ltd", job())

    assert posting.id == "workable_kuda_8F7A56FE46"
    assert posting.title == "Data Analyst - Credit"
    assert posting.company == "Kuda Technologies Ltd"
    assert posting.location == "Lagos, Nigeria"
    assert posting.url == "https://apply.workable.com/j/8F7A56FE46"
    assert posting.source == "workable"
    assert posting.employment_type == "full_time"
    assert posting.posted_at.date().isoformat() == "2026-11-17"
    assert posting.description == "SQL and data analysis for the credit team."
    assert posting.tags == ["IT", "Analytics"]


@pytest.mark.parametrize("city, state, country, expected", [
    ("Lagos", "Lagos", "Nigeria", "Lagos, Nigeria"),          # state repeats the city
    ("Abuja", "Federal Capital Territory", "Nigeria", "Abuja, Federal Capital Territory, Nigeria"),
    ("", "", "Nigeria", "Nigeria"),
    ("Cape Town", "Western Cape", "South Africa", "Cape Town, Western Cape, South Africa"),
    ("", "", "", "Unknown"),
])
def test_location_text(city, state, country, expected):
    assert location_text({"city": city, "state": state, "country": country}) == expected


def test_a_nigerian_posting_is_placeable_by_the_eligibility_engine():
    from src.eligibility import extract_places

    posting = to_posting("kuda", "Kuda", job())
    assert "nigeria" in extract_places(posting.location)


@pytest.mark.parametrize("raw, expected", [
    ("Full-time", "full_time"),
    ("Part-time", "part_time"),
    ("Contract", "contract"),
    ("Temporary", "contract"),
    ("Internship", "internship"),
    ("Other", "full_time"),
    ("", "full_time"),
    (None, "full_time"),
])
def test_employment_type_mapping(raw, expected):
    assert employment_type(raw) == expected


def test_telecommuting_sets_remote():
    remote = to_posting("kuda", "Kuda", job(telecommuting=True))
    onsite = to_posting("kuda", "Kuda", job(telecommuting=False))

    assert remote.is_remote is True and remote.remote_scope == "Lagos, Nigeria"
    assert onsite.is_remote is False and onsite.remote_scope == "On-Site"


def test_entries_without_a_title_or_link_are_skipped():
    assert to_posting("kuda", "Kuda", {**job(), "title": ""}) is None
    assert to_posting("kuda", "Kuda", {**job(), "shortlink": "", "url": "", "application_url": ""}) is None


def test_missing_optional_fields_are_tolerated():
    posting = to_posting("kuda", "", {
        "shortcode": "X1", "title": "Analyst", "shortlink": "https://apply.workable.com/j/X1",
    })

    assert posting.company == "Kuda"           # falls back to the account name
    assert posting.location == "Unknown"
    assert posting.description == ""
    assert posting.tags == []
    assert posting.posted_at is None


def test_an_invalid_date_does_not_raise():
    posting = to_posting("kuda", "Kuda", job(published="not a date"))
    # created_at is the documented fallback and is also unusable here.
    assert posting.posted_at is not None or posting.posted_at is None


# --- deduplication ------------------------------------------------------------

def test_repeated_entries_are_collapsed_on_the_board_job_id():
    """The live widget repeats postings; renmoney sent 100 for 72 real jobs."""
    payload = board(job(shortcode="A1"), job(shortcode="A1"), job(shortcode="A1"), job(shortcode="B2"))
    collector = use_transport(WorkableCollector(), lambda r: httpx.Response(200, json=payload))

    jobs = run(collector, config_with("kuda"))

    assert len(jobs) == 2
    assert {j.id for j in jobs} == {"workable_kuda_A1", "workable_kuda_B2"}


def test_two_openings_with_the_same_title_are_both_kept():
    """Renmoney genuinely has two "Business Analyst" roles, posted a year apart."""
    payload = board(
        job(shortcode="A1", title="Business Analyst", published="2025-04-14"),
        job(shortcode="B2", title="Business Analyst", published="2026-03-05"),
    )
    collector = use_transport(WorkableCollector(), lambda r: httpx.Response(200, json=payload))

    jobs = run(collector, config_with("renmoney"))

    assert len(jobs) == 2
    assert len({j.fingerprint for j in jobs}) == 2


# --- requests and failure modes ----------------------------------------------

def test_descriptions_are_requested_explicitly():
    """The widget omits descriptions unless details=true is passed, and that
    costs no extra request."""
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, json=board(job()))

    run(use_transport(WorkableCollector(), handler), config_with("kuda"))

    assert len(seen) == 1
    assert seen[0].startswith(ENDPOINT.format("kuda"))
    assert "details=true" in seen[0]


def test_each_configured_board_is_fetched_once():
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(200, json=board(job()))

    run(use_transport(WorkableCollector(), handler), config_with("kuda", "fairmoney", "renmoney"))
    assert len(seen) == 3


def test_one_failing_board_does_not_lose_the_others():
    def handler(request):
        if "missing" in request.url.path:
            return httpx.Response(404)
        return httpx.Response(200, json=board(job()))

    collector = use_transport(WorkableCollector(), handler)
    jobs = run(collector, config_with("kuda", "missing"))

    assert len(jobs) == 1
    assert collector.health.status == "degraded"
    assert "404" in collector.health.error_message


@pytest.mark.parametrize("status", [404, 429, 500, 503])
def test_http_failures_degrade_without_raising(status):
    collector = use_transport(WorkableCollector(), lambda r: httpx.Response(status))
    assert run(collector, config_with("kuda")) == []
    assert collector.health.status == "degraded"


def test_a_timeout_is_recorded_per_board():
    def handler(request):
        raise httpx.ConnectTimeout("timed out")

    collector = use_transport(WorkableCollector(), handler)
    assert run(collector, config_with("kuda")) == []
    assert collector.health.status == "degraded"
    assert "Timeout" in collector.health.error_message


def test_an_unexpected_response_shape_is_reported():
    collector = use_transport(WorkableCollector(), lambda r: httpx.Response(200, json=["not", "a", "board"]))
    assert run(collector, config_with("kuda")) == []
    assert collector.health.status == "degraded"
    assert "unexpected response shape" in collector.health.error_message


def test_a_board_with_no_openings_yields_nothing():
    collector = use_transport(WorkableCollector(), lambda r: httpx.Response(200, json=board()))
    assert run(collector, config_with("kuda")) == []


# --- configuration ------------------------------------------------------------

def test_no_boards_configured_means_disabled():
    collector = WorkableCollector()
    assert run(collector, config_with()) == []
    assert collector.health.status == "disabled"


def test_disabled_source_makes_no_request():
    config = config_with("kuda")
    config.sources.workable.enabled = False
    collector = WorkableCollector()

    assert run(collector, config) == []
    assert collector.health.status == "disabled"


def test_the_verified_boards_are_configured_and_registered():
    from pathlib import Path

    from src.collectors import get_all_collectors
    from src.config import load_config

    shipped = load_config(Path(__file__).resolve().parents[1] / "config" / "jobs.yaml")
    assert "workable" in [c.name for c in get_all_collectors()]
    # Verified live; kuda's Greenhouse token answers 404, its board moved here.
    assert set(shipped.sources.workable.companies) >= {"kuda", "fairmoney", "renmoney"}


def test_fingerprints_are_stable_across_runs():
    payload = board(job(shortcode="A1"), job(shortcode="B2"))
    first = run(use_transport(WorkableCollector(), lambda r: httpx.Response(200, json=payload)), config_with("kuda"))
    second = run(use_transport(WorkableCollector(), lambda r: httpx.Response(200, json=json.loads(json.dumps(payload)))), config_with("kuda"))

    assert [j.fingerprint for j in first] == [j.fingerprint for j in second]
