"""
Tests for whole-phrase matching, salary parsing/conversion and geographic eligibility.
"""

import pytest

from src.eligibility import CandidateGeo, classify
from src.matching import contains_phrase
from src.money import DEFAULT_FX_TO_USD, format_range, parse_salary_text, to_annual_usd


@pytest.mark.parametrize("text, phrase, expected", [
    ("Chrome Extension Engineer", "HR", False),
    ("HR Generalist", "HR", True),
    ("International Payments Engineer", "intern", False),
    ("Summer Interns", "intern", True),
    ("Remote (Germany)", "any", False),
    ("C++ developer", "C++", True),
    (".NET engineer", ".NET", True),
    ("L&D Specialist", "L&D", True),
    ("Technical Recruiters", "Recruiter", True),
])
def test_contains_phrase(text, phrase, expected):
    assert contains_phrase(text, phrase) is expected


@pytest.mark.parametrize("text, expected", [
    ("$120k - $160k", (120000, 160000, "USD", "yearly")),
    ("$90 - $150 /hour", (90, 150, "USD", "hourly")),
    ("$31,2k- $52k", (31200, 52000, "USD", "yearly")),
    ("€50.000 per year", (50000, 50000, "EUR", "yearly")),
    ("₦300,000 - ₦450,000 per month", (300000, 450000, "NGN", "monthly")),
])
def test_parse_salary_text(text, expected):
    info = parse_salary_text(text)
    assert (info.min, info.max, info.currency, info.period) == expected


def test_currency_conversion_to_annual_usd():
    assert to_annual_usd(100000, "USD", "yearly", DEFAULT_FX_TO_USD) == 100000
    assert to_annual_usd(50, "USD", "hourly", DEFAULT_FX_TO_USD) == 104000
    assert round(to_annual_usd(450000, "NGN", "monthly", DEFAULT_FX_TO_USD)) == 3510
    assert to_annual_usd(1000, "XYZ", "yearly", DEFAULT_FX_TO_USD) is None
    assert format_range(300000, 450000, "NGN", "monthly") == "₦300,000 – ₦450,000/mo"


NIGERIA = CandidateGeo.from_locations(["Remote", "Worldwide", "Nigeria", "Lagos, Nigeria", "Africa"])


@pytest.mark.parametrize("location, detail, expected", [
    ("Remote (Worldwide)", "", "eligible"),
    ("Remote - EMEA", "", "eligible"),
    ("Remote (US or Nigeria)", "", "eligible"),
    ("Remote (US)", "", "ineligible"),
    ("Remote - US Only", "", "ineligible"),
    ("Remote, Europe", "", "ineligible"),
    ("Anywhere in Germany, Berlin", "", "ineligible"),
    ("Worldwide except Nigeria", "", "ineligible"),
    ("Remote", "Candidates must be located in the United States.", "ineligible"),
    ("Remote", "Join us! We are a remote-first company.", "unknown"),
])
def test_eligibility_for_a_candidate_in_nigeria(location, detail, expected):
    assert classify(location, NIGERIA, detail_text=detail).status == expected


def test_restriction_naming_the_candidates_own_country_is_eligible():
    us = CandidateGeo.from_locations(["Remote", "United States"])
    assert classify("Remote", us, detail_text="Must be located in the United States").status == "eligible"
