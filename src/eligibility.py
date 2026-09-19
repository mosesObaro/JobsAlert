"""
JobsAlert Geographic Eligibility.
Shared classifier deciding whether a remote posting is open to the candidate's
country, used by both job scoring and income-opportunity scoring.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Set

from src.matching import contains_phrase

WORLDWIDE_TERMS = [
    "worldwide", "anywhere", "global", "globally", "all countries", "any country",
    "any location", "work from anywhere", "location independent",
]

# canonical country -> aliases matched as whole words
COUNTRY_ALIASES: Dict[str, List[str]] = {
    "united states": ["united states", "united states of america", "usa", "us", "u.s.", "u.s.a."],
    "united kingdom": ["united kingdom", "uk", "u.k.", "great britain", "britain", "england", "scotland", "wales"],
    "canada": ["canada"],
    "mexico": ["mexico"],
    "brazil": ["brazil"],
    "argentina": ["argentina"],
    "colombia": ["colombia"],
    "chile": ["chile"],
    "peru": ["peru"],
    "germany": ["germany", "deutschland"],
    "france": ["france"],
    "spain": ["spain"],
    "portugal": ["portugal"],
    "italy": ["italy"],
    "netherlands": ["netherlands", "the netherlands", "holland"],
    "belgium": ["belgium"],
    "ireland": ["ireland"],
    "poland": ["poland"],
    "sweden": ["sweden"],
    "norway": ["norway"],
    "denmark": ["denmark"],
    "finland": ["finland"],
    "switzerland": ["switzerland"],
    "austria": ["austria"],
    "czechia": ["czechia", "czech republic"],
    "romania": ["romania"],
    "ukraine": ["ukraine"],
    "greece": ["greece"],
    "hungary": ["hungary"],
    "estonia": ["estonia"],
    "lithuania": ["lithuania"],
    "latvia": ["latvia"],
    "nigeria": ["nigeria"],
    "ghana": ["ghana"],
    "kenya": ["kenya"],
    "south africa": ["south africa"],
    "egypt": ["egypt"],
    "morocco": ["morocco"],
    "rwanda": ["rwanda"],
    "uganda": ["uganda"],
    "tanzania": ["tanzania"],
    "ethiopia": ["ethiopia"],
    "india": ["india"],
    "pakistan": ["pakistan"],
    "bangladesh": ["bangladesh"],
    "philippines": ["philippines"],
    "singapore": ["singapore"],
    "indonesia": ["indonesia"],
    "malaysia": ["malaysia"],
    "vietnam": ["vietnam"],
    "thailand": ["thailand"],
    "japan": ["japan"],
    "china": ["china"],
    "south korea": ["south korea", "korea"],
    "australia": ["australia"],
    "new zealand": ["new zealand"],
    "united arab emirates": ["united arab emirates", "uae"],
    "saudi arabia": ["saudi arabia"],
    "israel": ["israel"],
    "turkey": ["turkey", "türkiye", "turkiye"],
}

_AFRICA = {"nigeria", "ghana", "kenya", "south africa", "egypt", "morocco", "rwanda", "uganda", "tanzania", "ethiopia"}
_EU = {"germany", "france", "spain", "portugal", "italy", "netherlands", "belgium", "ireland", "poland", "sweden",
       "denmark", "finland", "austria", "czechia", "romania", "greece", "hungary", "estonia", "lithuania", "latvia"}
_EUROPE = _EU | {"united kingdom", "norway", "switzerland", "ukraine"}
_MIDDLE_EAST = {"united arab emirates", "saudi arabia", "israel", "turkey"}
_LATAM = {"mexico", "brazil", "argentina", "colombia", "chile", "peru"}
_ASIA = {"india", "pakistan", "bangladesh", "philippines", "singapore", "indonesia", "malaysia", "vietnam",
         "thailand", "japan", "china", "south korea"}

# canonical region -> (aliases, member countries)
REGIONS: Dict[str, tuple] = {
    "africa": (["africa"], _AFRICA),
    "west africa": (["west africa"], {"nigeria", "ghana"}),
    "east africa": (["east africa"], {"kenya", "rwanda", "uganda", "tanzania", "ethiopia"}),
    "sub-saharan africa": (["sub-saharan africa", "subsaharan africa"], _AFRICA - {"egypt", "morocco"}),
    "europe": (["europe", "european"], _EUROPE),
    "eu": (["eu", "european union"], _EU),
    "emea": (["emea"], _EUROPE | _AFRICA | _MIDDLE_EAST),
    "middle east": (["middle east", "mena"], _MIDDLE_EAST | {"egypt", "morocco"}),
    "north america": (["north america"], {"united states", "canada", "mexico"}),
    "latin america": (["latin america", "latam", "south america"], _LATAM),
    "americas": (["americas"], {"united states", "canada"} | _LATAM),
    "asia": (["asia"], _ASIA),
    "apac": (["apac", "asia pacific", "asia-pacific"], _ASIA | {"australia", "new zealand"}),
    "oceania": (["oceania", "anz"], {"australia", "new zealand"}),
    "dach": (["dach"], {"germany", "austria", "switzerland"}),
    "nordics": (["nordics", "nordic"], {"sweden", "norway", "denmark", "finland"}),
}

_PLACE_TEXT = r"([a-z][a-z .,&/()-]{1,60})"
_RESTRICTION_PATTERNS = [
    re.compile(r"(?:must|need to|needs to|required to|should)\s+(?:be\s+)?(?:located|based|residing|reside|resident|live|living)\s+in\s+(?:the\s+)?" + _PLACE_TEXT),
    re.compile(r"(?:legally\s+)?authori[sz]ed\s+to\s+work\s+in\s+(?:the\s+)?" + _PLACE_TEXT),
    re.compile(r"only\s+(?:open|available)\s+to\s+(?:candidates|applicants|residents|people)\s+(?:in|from|of|based in)\s+(?:the\s+)?" + _PLACE_TEXT),
    re.compile(r"([a-z][a-z .]{1,30}?)\s+(?:residents|citizens)\s+only"),
    re.compile(r"\b(us|usa|u\.s\.|uk|eu|canada|europe)[\s-]only\b"),
]
_EXCLUSION_PATTERN = re.compile(r"\b(?:except|excluding|excludes|not available in|not open to (?:candidates|applicants) in)\b([^.;\n)]{1,80})")


_ACRONYMS = {"eu", "emea", "apac", "dach", "anz", "mena", "latam", "uk", "us", "usa", "uae"}


def display_place(place: str) -> str:
    return place.upper() if place in _ACRONYMS else place.title()


def _named(places: List[str]) -> str:
    return ", ".join(display_place(p) for p in places[:3])


def extract_places(text: str) -> List[str]:
    """Countries and regions named in `text`, as canonical names."""
    if not text:
        return []
    found: List[str] = []
    for country, aliases in COUNTRY_ALIASES.items():
        if any(contains_phrase(text, alias) for alias in aliases):
            found.append(country)
    for region, (aliases, _members) in REGIONS.items():
        if any(contains_phrase(text, alias) for alias in aliases):
            found.append(region)
    return found


_SCOPED_ANYWHERE = re.compile(r"\b(?:anywhere|remote)\s+(?:in|within|across)\s+(?:the\s+)?([a-z][a-z .,&/-]{1,40})")


def mentions_worldwide(text: str) -> bool:
    """True for "worldwide", "anywhere" etc., but not for "anywhere in Germany"."""
    lower = (text or "").lower()
    for match in _SCOPED_ANYWHERE.finditer(lower):
        if extract_places(match.group(1)):
            lower = lower.replace(match.group(0), " ")
    return any(contains_phrase(lower, term) for term in WORLDWIDE_TERMS)


@dataclass
class CandidateGeo:
    """The places a candidate can work from, derived from their preferred locations."""
    countries: Set[str] = field(default_factory=set)
    regions: Set[str] = field(default_factory=set)

    @classmethod
    def from_locations(cls, locations: Iterable[str]) -> "CandidateGeo":
        geo = cls()
        for loc in locations or []:
            for place in extract_places(loc):
                if place in COUNTRY_ALIASES:
                    geo.countries.add(place)
                else:
                    geo.regions.add(place)
        for region, (_aliases, members) in REGIONS.items():
            if geo.countries & members:
                geo.regions.add(region)
        return geo

    @property
    def known(self) -> bool:
        return bool(self.countries or self.regions)

    def accepts(self, place: str) -> bool:
        return place in self.countries or place in self.regions

    def label(self) -> str:
        return ", ".join(sorted(display_place(p) for p in (self.countries or self.regions))) or "your region"


@dataclass
class EligibilityResult:
    status: str  # "eligible" | "ineligible" | "unknown"
    scope: str   # "worldwide" | "region" | "country" | "unknown"
    reason: str
    places: List[str] = field(default_factory=list)


def classify(location_text: str, candidate: CandidateGeo, detail_text: str = "") -> EligibilityResult:
    """Classifies whether a posting located at `location_text` is open to `candidate`.

    `detail_text` (e.g. a description) is only searched for explicit restriction
    phrases such as "must be located in the US", never for bare country names.
    """
    location = (location_text or "").lower()
    detail = (detail_text or "").lower()

    for match in _EXCLUSION_PATTERN.finditer(f"{location} {detail}"):
        excluded = [p for p in extract_places(match.group(1)) if candidate.accepts(p)]
        if excluded:
            return EligibilityResult("ineligible", "region", f"Excludes {display_place(excluded[0])}", excluded)

    if mentions_worldwide(location):
        return EligibilityResult("eligible", "worldwide", "Open worldwide")

    places = extract_places(location)
    if not places:
        for pattern in _RESTRICTION_PATTERNS:
            match = pattern.search(detail)
            if match:
                places = extract_places(match.group(match.lastindex or 1))
                if places:
                    break

    if places:
        accepted = [p for p in places if candidate.accepts(p)]
        if accepted:
            scope = "country" if accepted[0] in COUNTRY_ALIASES else "region"
            return EligibilityResult("eligible", scope, f"Open to {display_place(accepted[0])}", accepted)
        if candidate.known:
            return EligibilityResult("ineligible", "region", f"Restricted to {_named(places)}", places)
        return EligibilityResult("unknown", "region", f"Limited to {_named(places)}", places)

    return EligibilityResult("unknown", "unknown", "Location not specified")
