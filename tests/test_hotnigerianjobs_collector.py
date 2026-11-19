"""
Unit tests for the Hot Nigerian Jobs collector.

Fixtures copy the two entry shapes the live feed used on 2026-11-19: mostly
"Role at Employer", and an employer recruitment drive whose roles are listed in
the description after a colon.
"""

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from src.collectors.hotnigerianjobs import (
    FEED_URL,
    HotNigerianJobsCollector,
    employer_from_recruitment_title,
    extract_state,
    parse_salary,
    postings_from_item,
    roles_from_description,
    split_title,
)
from src.config import AppConfig
from src.money import to_annual_usd


def feed(*items: str) -> str:
    return (
        '<?xml version="1.0"?><rss version="2.0"><channel><title>HotNigerianJobs</title>'
        + "".join(items)
        + "</channel></rss>"
    )


def entry(title, description, link="https://www.hotnigerianjobs.com/hotjobs/1/x",
          pub="Tue, 18 Nov 2026 08:00:00 +0000") -> str:
    return (
        f"<item><title><![CDATA[{title}]]></title><link>{link}</link>"
        f"<description><![CDATA[{description}]]></description><pubDate>{pub}</pubDate></item>"
    )


def use_transport(collector, handler):
    collector.create_http_client = lambda *args, **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )
    return collector


def run(collector, config=None):
    return asyncio.run(collector.execute(config or AppConfig()))


# --- the two entry shapes -----------------------------------------------------

def test_role_at_employer_is_split():
    assert split_title("Night Pharmacist at Kiyix Recruitment Hub") == ("Night Pharmacist", "Kiyix Recruitment Hub")
    # The last " at " wins, so a role containing "at" survives.
    assert split_title("Data Analyst at Work at Acme Ltd") == ("Data Analyst at Work", "Acme Ltd")


def test_a_title_without_an_employer_is_left_whole():
    assert split_title("Graduate Trainee Programme") == ("Graduate Trainee Programme", "")


def test_employer_is_recovered_from_a_recruitment_title():
    assert employer_from_recruitment_title("Techno Real Homes Job Recruitment (4 Positions)") == "Techno Real Homes"
    assert employer_from_recruitment_title("Street Child Recruitment") == "Street Child"


def test_roles_are_read_from_an_aggregate_description():
    description = (
        "Techno Real Homes is recruiting suitably qualified candidates to fill the "
        "following positions in Abuja: Human Resources Manager, Business Development "
        "Manager, and Tele-Sales Manager."
    )
    assert roles_from_description(description) == [
        "Human Resources Manager", "Business Development Manager", "Tele-Sales Manager",
    ]


def test_an_aggregate_entry_becomes_one_posting_per_role():
    description = (
        "Techno Real Homes is recruiting to fill the following positions in Abuja: "
        "Human Resources Manager, Business Development Manager."
    )
    postings = postings_from_item("Techno Real Homes Job Recruitment (2 Positions)",
                                  "https://x/1", description, datetime.now(timezone.utc))

    assert [p.title for p in postings] == ["Human Resources Manager", "Business Development Manager"]
    assert {p.company for p in postings} == {"Techno Real Homes"}
    # One page lists both roles, so both point at it, and they stay distinct.
    assert {p.url for p in postings} == {"https://x/1"}
    assert len({p.fingerprint or p.id for p in postings}) == 2


def test_an_entry_matching_neither_shape_is_still_kept():
    """Dropping it silently could lose a real opening."""
    postings = postings_from_item("Graduate Trainee Programme", "https://x/1",
                                  "Applications are invited.", None)
    assert len(postings) == 1
    assert postings[0].title == "Graduate Trainee Programme"


def test_an_entry_without_a_link_yields_nothing():
    assert postings_from_item("Role at Employer", "", "desc", None) == []


def test_roles_are_capped_per_entry():
    many = ", ".join(f"Officer {n}" for n in range(1, 15))
    roles = roles_from_description(f"X is recruiting to fill the following positions in Lagos: {many}.")
    assert len(roles) == 8


# --- location -----------------------------------------------------------------

@pytest.mark.parametrize("description, expected", [
    ("The position is located in Lagos State.", "Lagos, Nigeria"),
    ("...to fill the following positions in Oyo and Lagos States:", "Oyo, Nigeria"),
    ("Located in Rivers State, Nigeria.", "Rivers, Nigeria"),
    ("No location given here.", "Nigeria"),
    ("", "Nigeria"),
])
def test_state_extraction(description, expected):
    assert extract_state(description) == expected


def test_a_located_posting_is_recognisable_as_nigerian():
    from src.eligibility import extract_places

    posting = postings_from_item("HR Officer at Acme", "https://x/1",
                                 "The position is located in Lagos State.", None)[0]
    assert "nigeria" in extract_places(posting.location)


# --- salary, including the Naira ----------------------------------------------

def test_a_bare_naira_prefix_is_not_read_as_dollars():
    """The regression this guards: the shared parser reads "N500,000" as USD,
    which would turn 600,000 naira a month into 7.2 million dollars a year."""
    info = parse_salary("Salary: N500,000 - N600,000 monthly.")

    assert info.currency == "NGN"
    assert (info.min, info.max) == (500000.0, 600000.0)
    assert info.period == "monthly"
    assert round(to_annual_usd(info.max, info.currency, info.period, {"NGN": 0.00065})) == 4680


@pytest.mark.parametrize("line, currency", [
    ("Salary: ₦300,000 monthly", "NGN"),
    ("Salary: NGN 300,000 monthly", "NGN"),
    ("Salary: N300,000 monthly", "NGN"),
    ("Salary: $4,000 monthly", "USD"),
    ("Salary: £3,000 monthly", "GBP"),
])
def test_currency_detection(line, currency):
    assert parse_salary(line).currency == currency


def test_a_description_without_a_salary_returns_nothing():
    assert parse_salary("No pay stated.") is None
    assert parse_salary("Salary: competitive") is None


def test_salary_reaches_the_posting():
    posting = postings_from_item("Driver at Acme", "https://x/1",
                                 "Salary: N90,000 - N100,000 monthly.", None)[0]
    assert posting.salary_currency == "NGN"
    assert posting.salary_period == "monthly"
    assert posting.salary_max == 100000.0


# --- remote -------------------------------------------------------------------

def test_remote_wording_is_detected():
    remote = postings_from_item("Engineer at Acme", "https://x/1", "This is a remote role.", None)[0]
    onsite = postings_from_item("Engineer at Acme", "https://x/2", "Office based in Lagos State.", None)[0]

    assert remote.is_remote is True
    assert onsite.is_remote is False
    assert onsite.remote_scope == "On-Site"


# --- HTTP behaviour -----------------------------------------------------------

def test_a_successful_feed_produces_postings():
    collector = use_transport(
        HotNigerianJobsCollector(),
        lambda r: httpx.Response(200, text=feed(
            entry("Night Pharmacist at Kiyix Recruitment Hub", "Located in Lagos State. Salary: N170,000 - N200,000 monthly."),
            entry("Techno Real Homes Job Recruitment (2 Positions)",
                  "Recruiting to fill the following positions in Abuja: Human Resources Manager, Sales Manager.",
                  link="https://x/2"),
        )),
    )
    jobs = run(collector)

    assert collector.health.status == "healthy"
    assert [j.title for j in jobs] == ["Night Pharmacist", "Human Resources Manager", "Sales Manager"]
    assert jobs[0].salary_currency == "NGN"


@pytest.mark.parametrize("status", [404, 429, 500, 503])
def test_http_failures_degrade_without_raising(status):
    collector = use_transport(HotNigerianJobsCollector(), lambda r: httpx.Response(status))
    assert run(collector) == []
    assert collector.health.status == "degraded"
    assert str(status) in collector.health.error_message


def test_a_timeout_is_reported_as_an_error():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    collector = use_transport(HotNigerianJobsCollector(), handler)
    assert run(collector) == []
    assert collector.health.status == "error"


def test_a_malformed_feed_is_reported():
    collector = use_transport(HotNigerianJobsCollector(), lambda r: httpx.Response(200, text="<rss><channel>"))
    assert run(collector) == []
    assert collector.health.status == "degraded"
    assert "invalid feed" in collector.health.error_message


def test_an_invalid_date_does_not_raise():
    collector = use_transport(
        HotNigerianJobsCollector(),
        lambda r: httpx.Response(200, text=feed(entry("HR Officer at Acme", "In Lagos State.", pub="never"))),
    )
    jobs = run(collector)
    assert len(jobs) == 1 and jobs[0].posted_at is None


def test_only_the_declared_feed_is_fetched():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, text=feed(entry("HR Officer at Acme", "In Lagos State.")))

    run(use_transport(HotNigerianJobsCollector(), handler))
    assert seen == [FEED_URL]


# --- configuration and wiring -------------------------------------------------

def test_disabled_source_makes_no_request():
    config = AppConfig()
    config.sources.hotnigerianjobs.enabled = False
    collector = HotNigerianJobsCollector()

    assert run(collector, config) == []
    assert collector.health.status == "disabled"


def test_registered_and_links_are_verified_normally():
    from src.collectors import get_all_collectors
    from src.pipeline import UNVERIFIABLE_SOURCES

    assert "hotnigerianjobs" in [c.name for c in get_all_collectors()]
    # Its robots.txt allows crawling, so unlike MyJobMag these links are checked.
    assert "hotnigerianjobs" not in UNVERIFIABLE_SOURCES


def test_fingerprints_are_stable_across_runs():
    payload = feed(entry("HR Officer at Acme", "In Lagos State."))
    first = run(use_transport(HotNigerianJobsCollector(), lambda r: httpx.Response(200, text=payload)))
    second = run(use_transport(HotNigerianJobsCollector(), lambda r: httpx.Response(200, text=payload)))

    assert [j.fingerprint for j in first] == [j.fingerprint for j in second]
