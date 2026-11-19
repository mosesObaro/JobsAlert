"""
Cross-source identity: recognising one vacancy published on several platforms.

This sits **alongside** `src.deduplication`, which is deliberately source-scoped:
a posting's fingerprint includes the source's own reference id, so the same role
on LinkedIn and on Greenhouse is two records. That stays true. Nothing here
changes a fingerprint, re-keys a record, or rewrites the state file.

What it adds is a second, weaker question — "have we already told the candidate
about this job under another source?" — asked only when choosing what to alert.

Confidence strategy
-------------------
Two postings are treated as the same vacancy only when the evidence is strong.
Measured against live data on 2026-11-19, which shaped these rules:

* "Credit Risk Analyst" at Moniepoint appeared on Greenhouse (Lagos, Nigeria)
  and LinkedIn (Nigeria) — a real duplicate worth suppressing.
* "Analytics Manager" at Moniepoint appeared four times on Greenhouse alone, in
  Portugal, Poland and Spain — genuinely different vacancies that must never be
  merged.
* Company names differ across platforms: "Moniepoint" on Greenhouse,
  "Moniepoint Group" on LinkedIn, so company matching tolerates org suffixes.

So a match requires EITHER:

  A. the same employer application reference (the ATS job id inside the apply
     URL). Titles may differ freely — this is the strongest evidence there is.

  B. all of: different sources, the same normalised company, the same normalised
     title, AND locations that demonstrably overlap.

Anything weaker is left alone. Two postings that are merely *possibly* related
stay separate: a duplicate alert is a small annoyance, a suppressed Nigerian
role is a lost opportunity.

Same-source pairs are never matched here. A source that lists one role twice is
usually listing two genuine openings in different places, and its own ids
already separate them.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set

from src.eligibility import extract_places
from src.models import JobPosting

# Lower sorts first. A direct employer board carries the real application link,
# which is what the candidate should be sent to when a vacancy appears twice.
SOURCE_RANK: Dict[str, int] = {
    "greenhouse": 0, "lever": 0, "ashby": 0, "workable": 0, "smartrecruiters": 0,
    "custom": 1,
    "remotive": 2, "remoteok": 2, "arbeitnow": 2, "jobicy": 2,
    "rss": 3,
    "linkedin": 4, "twitter": 4, "hackernews": 4,
}
DEFAULT_RANK = 3

# Trailing words that differ between platforms for the same employer.
_ORG_SUFFIX = re.compile(
    r"\b(group|limited|ltd|plc|inc|incorporated|llc|co|company|holdings|"
    r"technologies|technology|tech|solutions|services|labs|global|international|hq)\b\s*$"
)

# Employer application references. Only boards whose URL carries the employer's
# own job id are useful across sources; an aggregator's id identifies the
# aggregator's copy, not the vacancy.
_APPLY_REFERENCE_PATTERNS = [
    ("greenhouse", re.compile(r"greenhouse\.io/[^/]+/jobs/(\d+)", re.I)),
    ("lever", re.compile(r"jobs\.lever\.co/[^/]+/([0-9a-f-]{8,})", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/[^/]+/([0-9a-f-]{8,})", re.I)),
    ("workable", re.compile(r"apply\.workable\.com/j/([0-9A-Z]{6,})", re.I)),
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/[^/]+/(\d+)", re.I)),
]


def normalize_company(name: str) -> str:
    """Company name without punctuation or trailing organisational words.

    "Moniepoint Group" and "Moniepoint" both become "moniepoint".
    """
    text = re.sub(r"[^\w\s]", " ", (name or "").lower())
    text = " ".join(text.split())
    previous = None
    while previous != text:
        previous = text
        text = _ORG_SUFFIX.sub("", text).strip()
    return text


def normalize_title(title: str) -> str:
    """Title without bracketed asides or punctuation.

    "Credit Risk Analyst (Lagos)" and "Credit Risk Analyst" both become
    "credit risk analyst".
    """
    text = re.sub(r"\(.*?\)", " ", (title or "").lower())
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def apply_reference(url: str) -> Optional[str]:
    """The employer's own job id inside an application URL, if recognisable."""
    if not url:
        return None
    for board, pattern in _APPLY_REFERENCE_PATTERNS:
        found = pattern.search(url)
        if found:
            return f"{board}:{found.group(1).lower()}"
    return None


def _places(*texts: Optional[str]) -> Set[str]:
    found: Set[str] = set()
    for text in texts:
        if text:
            found.update(extract_places(text))
    return found


def locations_overlap(left: Optional[str], right: Optional[str]) -> bool:
    """True when both locations name a place and those places intersect.

    An unresolvable location is never treated as compatible. "Nigeria" and
    "Lagos, Nigeria" overlap; "Remote, Portugal" and "Remote, Nigeria" do not;
    an empty or unrecognised location matches nothing, so the postings stay
    separate rather than one being hidden behind the other.
    """
    left_places, right_places = _places(left), _places(right)
    if not left_places or not right_places:
        return False
    return bool(left_places & right_places)


@dataclass(frozen=True)
class CrossSourceMatch:
    """An existing record believed to be the same vacancy from another source."""
    fingerprint: str
    source: str
    reason: str
    alerted: bool


class CrossSourceIndex:
    """Looks up a posting against records from *other* sources.

    Built from the records `StateManager` already holds plus whatever the current
    run has seen. It stores nothing of its own: every field it reads
    (`company`, `title`, `canonical_url`, `source`, `location`, `alerted`) is
    already in the state file, and a record written before `location` was stored
    simply never matches on rule B, which is the safe direction.
    """

    def __init__(self, records: Optional[Dict[str, dict]] = None):
        self._by_reference: Dict[str, List[CrossSourceMatch]] = {}
        self._by_identity: Dict[tuple, List[CrossSourceMatch]] = {}
        self._locations: Dict[str, Optional[str]] = {}
        for fingerprint, entry in (records or {}).items():
            self._index(
                fingerprint=fingerprint,
                company=entry.get("company", ""),
                title=entry.get("title", ""),
                url=entry.get("canonical_url", ""),
                source=entry.get("source", ""),
                location=entry.get("location"),
                alerted=bool(entry.get("alerted")),
            )

    def _index(self, fingerprint, company, title, url, source, location, alerted) -> None:
        match = CrossSourceMatch(fingerprint=fingerprint, source=source, reason="", alerted=alerted)
        self._locations[fingerprint] = location
        reference = apply_reference(url)
        if reference:
            self._by_reference.setdefault(reference, []).append(match)
        identity = (normalize_company(company), normalize_title(title))
        if all(identity):
            self._by_identity.setdefault(identity, []).append(match)

    def add(self, job: JobPosting) -> None:
        """Registers a posting from this run so later postings can match it."""
        self._index(
            fingerprint=job.fingerprint,
            company=job.company,
            title=job.title,
            url=job.raw_url or job.url,
            source=job.source,
            location=job.location,
            alerted=False,
        )

    def find_duplicate(self, job: JobPosting) -> Optional[CrossSourceMatch]:
        """An existing record from another source for the same vacancy, if any."""
        reference = apply_reference(job.raw_url or job.url)
        if reference:
            for candidate in self._by_reference.get(reference, []):
                if candidate.fingerprint != job.fingerprint:
                    return CrossSourceMatch(
                        fingerprint=candidate.fingerprint,
                        source=candidate.source,
                        reason=f"same employer application reference ({reference})",
                        alerted=candidate.alerted,
                    )

        identity = (normalize_company(job.company), normalize_title(job.title))
        if not all(identity):
            return None
        for candidate in self._by_identity.get(identity, []):
            if candidate.fingerprint == job.fingerprint or candidate.source == job.source:
                continue  # a source listing a role twice usually means two real openings
            if locations_overlap(job.location, self._locations.get(candidate.fingerprint)):
                return CrossSourceMatch(
                    fingerprint=candidate.fingerprint,
                    source=candidate.source,
                    reason=f"same company, title and location as the {candidate.source} copy",
                    alerted=candidate.alerted,
                )
        return None


def preferred_copy(jobs: Iterable[JobPosting]) -> Optional[JobPosting]:
    """The copy to alert on: the one most likely to carry the employer's own link."""
    ranked = sorted(jobs, key=lambda j: (SOURCE_RANK.get(j.source, DEFAULT_RANK), j.source, j.id))
    return ranked[0] if ranked else None
