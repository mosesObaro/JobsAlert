"""
Hot Nigerian Jobs Collector — Nigerian job board.

Reads the RSS feed the site declares in its own pages
(`<link rel="alternate" type="application/rss+xml" href=".../feed/rss.xml">`).
Its robots.txt allows crawling (`Allow: /`, `Content-Signal: search=yes`), so
unlike MyJobMag these application links are fetched by the link verifier.

Verified live on 2026-11-19: HTTP 200, 600 items, newest one day old.

Two entry shapes, both handled:

  * 500 of 600 read "Role at Employer" — one posting each.
  * 100 are an employer's recruitment drive, "Employer Job Recruitment
    (4 Positions)", whose roles are listed in the description after a colon.
    84 of those yield a clean list, which is worth having: it is where roles
    like "Human Resources Manager" at Techno Real Homes appear. Each role
    becomes its own posting pointing at the same page, which is where the
    candidate actually applies.

Splitting a role list on commas occasionally produces a fragment rather than a
title ("Mental Health" out of "Mental Health, Psychosocial Support Officer").
Those simply score badly and are discarded by the scoring engine, so they are
left in rather than risking the loss of a real role to a stricter filter.

The feed writes salaries as "Salary: N500,000 - N600,000 monthly". The shared
money parser reads a bare "N" as no currency at all and so returns USD, which
would turn ₦600,000 a month into $7.2m a year and flood the digest. Currency is
therefore decided here, local to this collector, rather than by changing the
shared parser that every other source depends on.
"""

from __future__ import annotations
import re
from typing import List, Optional

from src.collectors.base import BaseCollector
from src.config import AppConfig
from src.deduplication import stable_hash
from src.feeds import parse_feed, strip_html
from src.models import JobPosting
from src.money import parse_salary_text

FEED_URL = "https://www.hotnigerianjobs.com/feed/rss.xml"

HOME_COUNTRY = "Nigeria"
MAX_ROLES_PER_ENTRY = 8

_ROLE_LIST = re.compile(r"following\s+positions?[^:]{0,60}:\s*(.+)", re.I)
_ROLE_SPLIT = re.compile(r",\s*(?:and\s+)?|\s+and\s+", re.I)
_RECRUITMENT_SUFFIX = re.compile(r"\s+(?:job\s+)?recruitment\b.*$", re.I)
_STATE = re.compile(r"\bin\s+([A-Z][A-Za-z\- ]{2,24}?)\s+State", re.I)
_SALARY_LINE = re.compile(r"salary[:\s]+([^.]{3,60})", re.I)
# A bare "N" before digits is the Naira on this board; "₦", "NGN" and the other
# currency symbols are already understood by the shared parser.
_NAIRA = re.compile(r"(?:₦|\bN(?=\s?\d))", re.IGNORECASE)
_OTHER_CURRENCY = re.compile(r"[$€£]|\b(usd|eur|gbp|cad|aud|zar|ghs|kes)\b", re.IGNORECASE)
REMOTE_TERMS = ("remote", "work from home", "telecommute")


def extract_state(description: str) -> str:
    """"...located in Lagos State" -> "Lagos, Nigeria"; otherwise "Nigeria"."""
    found = _STATE.search(description or "")
    if not found:
        return HOME_COUNTRY
    state = found.group(1).strip()
    # "Lagos and Ogun" -> the first named state is enough to place the role.
    state = re.split(r"\s+and\s+", state, flags=re.IGNORECASE)[0].strip()
    return f"{state}, {HOME_COUNTRY}" if state else HOME_COUNTRY


def parse_salary(description: str):
    """Salary from the description, with the Naira recognised."""
    line = _SALARY_LINE.search(description or "")
    if not line:
        return None
    raw = line.group(1)
    info = parse_salary_text(raw)
    if info.min is None:
        return None
    if _NAIRA.search(raw) and not _OTHER_CURRENCY.search(raw):
        info.currency = "NGN"
    return info


def split_title(title: str) -> tuple[str, str]:
    """"Night Pharmacist at Kiyix Recruitment Hub" -> (role, employer)."""
    role, separator, employer = title.rpartition(" at ")
    if separator and role.strip() and employer.strip():
        return role.strip(), employer.strip()
    return title.strip(), ""


def employer_from_recruitment_title(title: str) -> str:
    """"Techno Real Homes Job Recruitment (4 Positions)" -> "Techno Real Homes"."""
    return _RECRUITMENT_SUFFIX.sub("", title or "").strip()


def roles_from_description(description: str) -> List[str]:
    """The roles an aggregate entry lists after its colon."""
    found = _ROLE_LIST.search(description or "")
    if not found:
        return []
    roles = []
    for part in _ROLE_SPLIT.split(found.group(1)):
        role = part.strip(" .;:")
        if 3 <= len(role) <= 60 and role.lower() not in {r.lower() for r in roles}:
            roles.append(role)
    return roles[:MAX_ROLES_PER_ENTRY]


def _posting(title: str, company: str, link: str, description: str, published, location: str) -> Optional[JobPosting]:
    if not title or not link:
        return None
    salary = parse_salary(description)
    haystack = f"{title} {location} {description}".lower()
    is_remote = any(term in haystack for term in REMOTE_TERMS)
    return JobPosting(
        id=f"hnj_{stable_hash(link, title)}",
        title=title,
        company=company or "Unknown",
        location=location,
        is_remote=is_remote,
        remote_scope=location if is_remote else "On-Site",
        url=link,
        raw_url=link,
        description=description[:3000],
        salary_min=salary.min if salary else None,
        salary_max=salary.max if salary else None,
        salary_currency=salary.currency if salary else "USD",
        salary_period=salary.period if salary else "yearly",
        source="hotnigerianjobs",
        posted_at=published,
    )


def postings_from_item(title: str, link: str, summary: str, published) -> List[JobPosting]:
    """One feed entry as one or more postings."""
    description = strip_html(summary or "")
    location = extract_state(description)

    role, employer = split_title(title)
    if employer:
        posting = _posting(role, employer, link, description, published, location)
        return [posting] if posting else []

    # An employer's recruitment drive: one posting per role it lists.
    employer = employer_from_recruitment_title(title)
    roles = roles_from_description(description)
    if roles:
        found = [_posting(r, employer, link, description, published, location) for r in roles]
        return [p for p in found if p]

    # Neither shape: keep the entry rather than dropping a possible opening.
    posting = _posting(title.strip(), employer, link, description, published, location)
    return [posting] if posting else []


class HotNigerianJobsCollector(BaseCollector):
    """Collects Nigerian postings from Hot Nigerian Jobs' declared RSS feed."""

    def __init__(self):
        super().__init__(name="hotnigerianjobs")

    def is_enabled(self, config: AppConfig) -> bool:
        return config.sources.hotnigerianjobs.enabled

    async def collect(self, config: AppConfig) -> List[JobPosting]:
        if not config.sources.hotnigerianjobs.enabled:
            return []

        async with self.create_http_client(
            timeout=15.0, accept="application/rss+xml, application/xml, text/xml, */*"
        ) as client:
            response = await client.get(FEED_URL)
        if not self.accept(response, "hotnigerianjobs"):
            return []

        try:
            items = parse_feed(response.text)
        except Exception as exc:  # ElementTree raises several shapes of parse error
            self.note(f"hotnigerianjobs: invalid feed ({type(exc).__name__})")
            return []

        postings: List[JobPosting] = []
        for item in items:
            postings.extend(postings_from_item(item.title, item.link, item.summary, item.published))
        return postings
