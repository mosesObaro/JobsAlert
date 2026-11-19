"""
Unit tests for the MyJobMag collector.

The fixtures mirror the structure of the live feed as it was on 2026-11-19:
RSS 2.0 whose items carry `position`, `company`, `location`, `industry` and
`expiryDate` in addition to the usual fields, declared as iso-8859-1.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from src.collectors.myjobmag import (
    FEED_URL,
    MyJobMagCollector,
    is_expired,
    parse_items,
    qualify_location,
    to_posting,
)
from src.config import AppConfig


def feed(items: str, declare_encoding: bool = True) -> bytes:
    header = '<?xml version="1.0" encoding="iso-8859-1"?>' if declare_encoding else '<?xml version="1.0"?>'
    return (
        f'{header}<rss version="2.0"><channel><title>MyJobMag</title>'
        f"{items}</channel></rss>"
    ).encode("utf-8")


def item(
    title="Talent Acquisition Specialist at Newedge Finance Limited",
    position="Talent Acquisition Specialist",
    company="Newedge Finance Limited",
    location="Lagos",
    industry="Human Resources",
    link="https://www.myjobmag.com/a_fields.php?id=1393508",
    description="<p>Recruitment and onboarding for a finance team.</p>",
    pub="Wed, 19 Nov 2026 09:00:00 +0000",
    expiry="",
) -> str:
    parts = [f"<title><![CDATA[{title}]]></title>", f"<link>{link}</link>"]
    for tag, value in (("position", position), ("company", company), ("location", location),
                       ("industry", industry), ("pubDate", pub), ("expiryDate", expiry)):
        if value:
            parts.append(f"<{tag}>{value}</{tag}>")
    parts.append(f"<description><![CDATA[{description}]]></description>")
    return "<item>" + "".join(parts) + "</item>"


def use_transport(collector, handler):
    collector.create_http_client = lambda *args, **kwargs: httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    )
    return collector


def run(collector, config=None):
    return asyncio.run(collector.execute(config or AppConfig()))


# --- parsing ------------------------------------------------------------------

def test_parses_the_structured_fields():
    parsed = parse_items(feed(item()))
    assert len(parsed) == 1
    assert parsed[0]["position"] == "Talent Acquisition Specialist"
    assert parsed[0]["company"] == "Newedge Finance Limited"
    assert parsed[0]["location"] == "Lagos"
    assert parsed[0]["industry"] == "Human Resources"


def test_an_encoding_declaration_does_not_break_parsing():
    """The live feed declares iso-8859-1, which ElementTree rejects from a str."""
    assert len(parse_items(feed(item()))) == 1
    assert len(parse_items(feed(item(), declare_encoding=False))) == 1


def test_posting_uses_the_structured_position_and_company():
    posting = to_posting(parse_items(feed(item()))[0])

    assert posting.title == "Talent Acquisition Specialist"
    assert posting.company == "Newedge Finance Limited"
    assert posting.source == "myjobmag"
    assert posting.description == "Recruitment and onboarding for a finance team."
    assert posting.posted_at.year == 2026


def test_title_falls_back_to_stripping_the_company_suffix():
    """Some items omit <position>; the role must not keep "at <Company>"."""
    posting = to_posting(parse_items(feed(item(position="")))[0])
    assert posting.title == "Talent Acquisition Specialist"


def test_remote_wording_is_detected():
    remote = to_posting(parse_items(feed(item(location="Lagos", description="Fully remote role.")))[0])
    onsite = to_posting(parse_items(feed(item()))[0])

    assert remote.is_remote is True
    assert onsite.is_remote is False
    assert onsite.remote_scope == "On-Site"


# --- location normalisation ---------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("Lagos", "Lagos, Nigeria"),
    ("Rivers", "Rivers, Nigeria"),
    ("Abuja", "Abuja, Nigeria"),
    ("All", "Nigeria"),
    ("", "Nigeria"),
    # Already names a country or region: left exactly as it is.
    ("Accra, Ghana", "Accra, Ghana"),
    ("Remote, Worldwide", "Remote, Worldwide"),
])
def test_qualify_location_adds_the_country_only_when_missing(raw, expected):
    assert qualify_location(raw) == expected


def test_a_lagos_posting_is_recognisable_as_nigerian():
    """Bare city names left the eligibility engine unable to place the role."""
    from src.eligibility import extract_places

    posting = to_posting(parse_items(feed(item(location="Lagos")))[0])
    assert "nigeria" in extract_places(posting.location)


# --- optional and malformed data ----------------------------------------------

def test_items_without_a_title_or_link_are_skipped():
    assert to_posting(parse_items(feed(item(title="", position="")))[0]) is None
    assert to_posting(parse_items(feed(item(link="")))[0]) is None


def test_missing_optional_fields_are_tolerated():
    posting = to_posting(parse_items(feed(item(company="", industry="", description="", pub="")))[0])

    assert posting is not None
    assert posting.company == "Unknown"
    assert posting.tags == []
    assert posting.posted_at is None


def test_an_invalid_date_does_not_raise():
    posting = to_posting(parse_items(feed(item(pub="not a date")))[0])
    assert posting.posted_at is None


def test_malformed_xml_is_reported_not_raised():
    collector = use_transport(MyJobMagCollector(), lambda r: httpx.Response(200, content=b"<rss><channel>"))
    jobs = run(collector)

    assert jobs == []
    assert collector.health.status == "degraded"
    assert "invalid XML" in collector.health.error_message


# --- expiry -------------------------------------------------------------------

def test_a_posting_past_its_stated_closing_date_is_skipped():
    past = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    future = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%a, %d %b %Y %H:%M:%S +0000")

    collector = use_transport(
        MyJobMagCollector(),
        lambda r: httpx.Response(200, content=feed(item(link="https://x/1", expiry=past) + item(link="https://x/2", expiry=future))),
    )
    jobs = run(collector)

    assert [j.url for j in jobs] == ["https://x/2"]


def test_a_missing_expiry_date_keeps_the_posting():
    assert is_expired("") is False
    assert is_expired("not a date") is False


# --- HTTP behaviour -----------------------------------------------------------

@pytest.mark.parametrize("status", [404, 429, 500, 503])
def test_http_failures_degrade_the_source_without_raising(status):
    collector = use_transport(MyJobMagCollector(), lambda r: httpx.Response(status))
    jobs = run(collector)

    assert jobs == []
    assert collector.health.status == "degraded"
    assert str(status) in collector.health.error_message


def test_a_timeout_is_reported_as_an_error_not_a_crash():
    def handler(request):
        raise httpx.ConnectTimeout("timed out")

    collector = use_transport(MyJobMagCollector(), handler)
    jobs = run(collector)

    assert jobs == []
    assert collector.health.status == "error"
    assert "Timeout" in collector.health.error_message


def test_an_empty_feed_is_reported_rather_than_crashing():
    collector = use_transport(MyJobMagCollector(), lambda r: httpx.Response(200, content=feed("")))
    assert run(collector) == []


def test_the_published_feed_url_is_the_only_thing_fetched():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, content=feed(item()))

    run(use_transport(MyJobMagCollector(), handler))
    assert seen == [FEED_URL]


# --- configuration ------------------------------------------------------------

def test_disabled_source_makes_no_request():
    config = AppConfig()
    config.sources.myjobmag.enabled = False
    collector = MyJobMagCollector()

    assert run(collector, config) == []
    assert collector.health.status == "disabled"


def test_fingerprints_are_stable_and_distinct():
    collector = use_transport(
        MyJobMagCollector(),
        lambda r: httpx.Response(200, content=feed(item(link="https://x/1") + item(link="https://x/2"))),
    )
    first = run(collector)
    second = run(use_transport(MyJobMagCollector(), lambda r: httpx.Response(200, content=feed(item(link="https://x/1") + item(link="https://x/2")))))

    assert len({j.fingerprint for j in first}) == 2
    assert [j.fingerprint for j in first] == [j.fingerprint for j in second]


def test_the_collector_is_registered_and_links_are_not_verified():
    from src.collectors import get_all_collectors
    from src.pipeline import UNVERIFIABLE_SOURCES

    assert "myjobmag" in [c.name for c in get_all_collectors()]
    # Its job links carry a query string, which MyJobMag's robots.txt disallows.
    assert "myjobmag" in UNVERIFIABLE_SOURCES
