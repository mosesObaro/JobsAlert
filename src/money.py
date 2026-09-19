"""
JobsAlert Money Helpers.
Parses salary text into amount, currency and pay period, and converts pay to
annual or hourly USD so it can be compared with the configured floors.
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Approximate USD value of one unit of each currency. Rates drift: override them with
# `fx_rates_to_usd` in config/jobs.yaml. Currencies missing here get a neutral pay score.
DEFAULT_FX_TO_USD: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.27,
    "CHF": 1.13,
    "CAD": 0.73,
    "AUD": 0.66,
    "NZD": 0.60,
    "SGD": 0.74,
    "SEK": 0.095,
    "NOK": 0.093,
    "DKK": 0.145,
    "PLN": 0.25,
    "INR": 0.012,
    "JPY": 0.0067,
    "BRL": 0.18,
    "MXN": 0.055,
    "ZAR": 0.055,
    "KES": 0.0077,
    "GHS": 0.065,
    "NGN": 0.00065,
}

PERIOD_FACTORS_TO_YEAR: Dict[str, float] = {
    "hourly": 2080.0,
    "daily": 260.0,
    "weekly": 52.0,
    "monthly": 12.0,
    "yearly": 1.0,
}

_SYMBOLS: List[Tuple[str, str]] = [
    ("GH₵", "GHS"),
    ("KSh", "KES"),
    ("A$", "AUD"),
    ("C$", "CAD"),
    ("€", "EUR"),
    ("£", "GBP"),
    ("₦", "NGN"),
    ("₹", "INR"),
    ("¥", "JPY"),
    ("$", "USD"),
]

_DISPLAY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "NGN": "₦", "INR": "₹"}

_PERIOD_PATTERNS: List[Tuple[str, str]] = [
    (r"(per|an|/|a)\s*(hour|hr|h)\b|\bhourly\b|/\s*hr?\b", "hourly"),
    (r"(per|a|/)\s*day\b|\bdaily\b", "daily"),
    (r"(per|a|/)\s*(week|wk)\b|\bweekly\b", "weekly"),
    (r"(per|a|/)\s*(month|mo)\b|\bmonthly\b|\bp\.?m\.?\b", "monthly"),
    (r"(per|a|/)\s*(year|yr|annum)\b|\byearly\b|\bannual(ly)?\b|\bp\.?a\.?\b", "yearly"),
]

_AMOUNT = re.compile(r"(\d+(?:[.,]\d+)*)\s*([kKmM])?(?![a-zA-Z])")


@dataclass
class SalaryInfo:
    min: Optional[float] = None
    max: Optional[float] = None
    currency: str = "USD"
    period: str = "yearly"


def detect_currency(text: str) -> Optional[str]:
    if not text:
        return None
    upper = text.upper()
    for code in DEFAULT_FX_TO_USD:
        if re.search(r"(?<![A-Z])" + code + r"(?![A-Z])", upper):
            return code
    for symbol, code in _SYMBOLS:
        if symbol in text:
            return code
    return None


def detect_period(text: str) -> Optional[str]:
    lower = (text or "").lower()
    for pattern, period in _PERIOD_PATTERNS:
        if re.search(pattern, lower):
            return period
    return None


def normalize_period(value: Optional[str]) -> Optional[str]:
    """Maps API period labels ('1 YEAR', 'annual', 'hour', 'month') to our period names."""
    if not value:
        return None
    lower = str(value).lower()
    for key, period in (("hour", "hourly"), ("day", "daily"), ("week", "weekly"), ("month", "monthly"), ("year", "yearly"), ("annual", "yearly")):
        if key in lower:
            return period
    return None


def _parse_amount(number: str, suffix: Optional[str]) -> float:
    if suffix:
        # "31,2k" and "31.2k" are decimals; "1,500k" is a thousands separator.
        if re.fullmatch(r"\d+[.,]\d{1,2}", number):
            value = float(number.replace(",", "."))
        else:
            value = float(re.sub(r"[.,]", "", number))
        return value * (1_000_000 if suffix.lower() == "m" else 1000)
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", number):
        return float(re.sub(r"[.,]", "", number))
    return float(number.replace(",", ""))


def parse_salary_text(text: str, default_currency: str = "USD") -> SalaryInfo:
    """Parses strings like '$120k - $160k', '€50.000 per year' or '$90 - $150 /hour'."""
    info = SalaryInfo(currency=default_currency)
    if not text or not text.strip():
        return info
    info.currency = detect_currency(text) or default_currency
    values = [_parse_amount(num, suffix) for num, suffix in _AMOUNT.findall(text)]
    values = [v for v in values if v > 0]
    if not values:
        return info
    info.min, info.max = (values[0], values[0]) if len(values) == 1 else (min(values[:2]), max(values[:2]))
    period = detect_period(text)
    if period is None:
        # Bare small numbers ("$45 - $60") are almost always hourly rates.
        period = "hourly" if info.max < 1000 else "yearly"
    info.period = period
    return info


def to_annual_usd(amount: Optional[float], currency: str, period: str, fx: Dict[str, float]) -> Optional[float]:
    if amount is None:
        return None
    rate = fx.get((currency or "USD").upper())
    if rate is None:
        return None
    return amount * PERIOD_FACTORS_TO_YEAR.get(period or "yearly", 1.0) * rate


def to_hourly_usd(amount: Optional[float], currency: str, period: str, fx: Dict[str, float]) -> Optional[float]:
    annual = to_annual_usd(amount, currency, period, fx)
    return None if annual is None else annual / PERIOD_FACTORS_TO_YEAR["hourly"]


def format_money(amount: Optional[float], currency: str = "USD") -> str:
    if amount is None:
        return ""
    code = (currency or "USD").upper()
    number = f"{amount:,.0f}" if amount >= 100 else f"{amount:,.2f}".rstrip("0").rstrip(".")
    symbol = _DISPLAY_SYMBOLS.get(code)
    return f"{symbol}{number}" if symbol else f"{code} {number}"


def format_range(low: Optional[float], high: Optional[float], currency: str = "USD", period: Optional[str] = None) -> str:
    if low is None and high is None:
        return ""
    if low is not None and high is not None and low != high:
        text = f"{format_money(low, currency)} – {format_money(high, currency)}"
    else:
        text = format_money(high if high is not None else low, currency)
    suffix = {"hourly": "/hr", "daily": "/day", "weekly": "/wk", "monthly": "/mo", "yearly": "/yr"}.get(period or "")
    return f"{text}{suffix}" if suffix else text
