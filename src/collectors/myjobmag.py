"""
MyJobMag Collector — Nigerian job board.

Reads the feed MyJobMag publishes for this purpose. The site has a public feeds
page (https://www.myjobmag.com/feeds/) that lists its feeds for syndication;
`jobsxml_by_categories.xml` is the structured one, an RSS 2.0 document whose
items carry `position`, `company`, `location`, `industry` and `expiryDate`
alongside the usual fields.

That structure is why this has its own collector rather than a line in
`rss_feeds`: the generic RSS collector would set every posting's company to the
feed's name and guess the location from the text, which would break company
matching, the watchlist and cross-source identity. Here the employer and
location arrive as real fields.

Verified against the live feed on 2026-11-19: HTTP 200, 100 items, newest the
same day, descriptions of roughly 800-3,200 characters.

Job links carry a query string, and MyJobMag's robots.txt disallows crawling
URLs with one, so postings from this source are exempt from link verification
(see UNVERIFIABLE_SOURCES in src/pipeline.py). The feed itself is published for
syndication and is the only thing fetched here.
"""

from __future__ import annotations
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import List, Optional

from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.deduplication import stable_hash
from src.feeds import parse_feed_date, strip_html
from src.models import JobPosting

FEED_URL = "https://www.myjobmag.com/jobsxml_by_categories.xml"

REMOTE_TERMS = ("remote", "work from home", "anywhere", "telecommute")

# The feed is the Nigerian edition (MyJobMag runs separate country sites), and
# every location it carried when this was written was a Nigerian state or city:
# Lagos, Rivers, Ekiti, Abuja, Oyo, Borno, Delta, Kwara, Ogun, Abia, Kano, plus
# "All" for nationwide. None of them names a country, which leaves the
# eligibility engine unable to tell that a Lagos role is one the candidate can
# take. Qualifying the country is normalisation, not a thumb on the scale, and
# a location that already names a country is left exactly as it is.
HOME_COUNTRY = "Nigeria"
NATIONWIDE = {"all", "nationwide", "any", ""}


def qualify_location(location: str) -> str:
    """Adds the feed's country when the location names only a city or state."""
    from src.eligibility import extract_places, mentions_worldwide

    text = (location or "").strip()
    if text.lower() in NATIONWIDE:
        return HOME_COUNTRY
    if extract_places(text) or mentions_worldwide(text):
        # Already names a country or region, or is open worldwide. Pinning a
        # country on either would narrow a role that is not actually Nigerian.
        return text
    return f"{text}, {HOME_COUNTRY}"


def _text(item: ET.Element, tag: str) -> str:
    found = item.find(tag)
    return (found.text or "").strip() if found is not None and found.text else ""


def _title_without_company(title: str, company: str) -> str:
    """"Sales Supervisor at Isurf Global Services" -> "Sales Supervisor".

    Used only when the feed omits <position>; the suffix is removed so the
    scoring engine matches a role rather than a sentence.
    """
    if company and title.lower().endswith(f" at {company.lower()}"):
        return title[: -(len(company) + 4)].strip()
    return title.split(" at ")[0].strip() if " at " in title else title.strip()


def parse_items(xml_bytes: bytes) -> List[dict]:
    """Items from the feed, keeping MyJobMag's structured fields.

    Bytes rather than text: the document declares iso-8859-1, and ElementTree
    refuses a str that carries an encoding declaration.
    """
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.iter("item"):
        items.append({
            "title": _text(item, "title"),
            "link": _text(item, "link"),
            "position": _text(item, "position"),
            "company": _text(item, "company"),
            "location": _text(item, "location"),
            "industry": _text(item, "industry"),
            "description": _text(item, "description"),
            "pub_date": _text(item, "pubDate"),
            "expiry_date": _text(item, "expiryDate"),
        })
    return items


def is_expired(expiry: str, now: Optional[datetime] = None) -> bool:
    """True when the feed says the posting has closed."""
    parsed = parse_feed_date(expiry) if expiry else None
    if parsed is None:
        return False
    return parsed < (now or datetime.now(timezone.utc))


def to_posting(item: dict) -> Optional[JobPosting]:
    """One feed item as a posting, or None when it has no usable title or link."""
    link = item.get("link") or ""
    company = item.get("company") or ""
    title = item.get("position") or _title_without_company(item.get("title", ""), company)
    if not title or not link:
        return None

    location = qualify_location(item.get("location", ""))
    description = strip_html(item.get("description", ""))
    haystack = f"{title} {location} {description}".lower()
    is_remote = any(term in haystack for term in REMOTE_TERMS)

    return JobPosting(
        id=f"myjobmag_{stable_hash(link)}",
        title=title,
        company=company or "Unknown",
        location=location,
        is_remote=is_remote,
        remote_scope=location if is_remote else "On-Site",
        url=link,
        raw_url=link,
        description=description[:3000],
        source="myjobmag",
        posted_at=parse_feed_date(item.get("pub_date", "")),
        tags=[item["industry"]] if item.get("industry") else [],
    )


class MyJobMagCollector(BaseCollector):
    """Collects Nigerian postings from MyJobMag's published job feed."""

    def __init__(self):
        super().__init__(name="myjobmag")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.myjobmag.enabled

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.myjobmag.enabled:
            return []

        async with self.create_http_client(
            timeout=15.0, accept="application/rss+xml, application/xml, text/xml, */*"
        ) as client:
            response = await client.get(FEED_URL)
        if not self.accept(response, "myjobmag"):
            return []

        try:
            items = parse_items(response.content)
        except ET.ParseError as exc:
            self.note(f"myjobmag: invalid XML ({exc})")
            return []

        postings: List[JobPosting] = []
        expired = 0
        for item in items:
            if is_expired(item.get("expiry_date", "")):
                expired += 1  # the feed states the closing date, so trust it
                continue
            posting = to_posting(item)
            if posting is not None:
                postings.append(posting)
        if expired:
            print(f"   ℹ️ myjobmag: skipped {expired} posting(s) past their stated closing date.")
        return postings
