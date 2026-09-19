"""
JobsAlert Text Matching.
Whole-phrase matching so short keywords don't match inside other words
("HR" in "Chrome", "intern" in "International", "any" in "Germany").
"""

from __future__ import annotations
import re
from functools import lru_cache
from typing import Iterable, Optional, Set


@lru_cache(maxsize=4096)
def _phrase_pattern(phrase: str) -> re.Pattern:
    escaped = re.escape(phrase.strip().lower())
    escaped = re.sub(r"(\\\s)+", r"\\s+", escaped)  # any run of whitespace matches any whitespace
    # Alphanumeric boundaries work for phrases that start or end with symbols ("C++", ".NET", "L&D").
    # An optional plural suffix keeps "Recruiter" matching "Recruiters".
    return re.compile(r"(?<![a-z0-9])" + escaped + r"(?:e?s)?(?![a-z0-9])")


def contains_phrase(text: str, phrase: str) -> bool:
    """True when `phrase` appears in `text` as whole word(s), case-insensitively."""
    if not text or not phrase or not phrase.strip():
        return False
    return _phrase_pattern(phrase).search(text.lower()) is not None


def find_phrase(text: str, phrases: Iterable[str]) -> Optional[str]:
    """Returns the first phrase contained in `text`, or None."""
    for phrase in phrases:
        if contains_phrase(text, phrase):
            return phrase
    return None


def word_set(text: str) -> Set[str]:
    """Lowercase word tokens, keeping symbols that belong to tech terms (c++, c#, node.js)."""
    return set(re.findall(r"[a-z0-9][a-z0-9+#.]*", (text or "").lower()))
