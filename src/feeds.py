"""
JobsAlert Feed Parsing.
Shared RSS 2.0 / Atom parser used by the job, income and Twitter/Nitter collectors.
"""

from __future__ import annotations
import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

ATOM = "{http://www.w3.org/2005/Atom}"
DUBLIN_CORE = "{http://purl.org/dc/elements/1.1/}"


@dataclass
class FeedItem:
    title: str
    link: str
    guid: str
    summary: str  # raw text/HTML as published
    published: Optional[datetime]


def strip_html(text: str) -> str:
    """Removes tags and entities and collapses whitespace."""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>|</p>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]*>?", " ", text)
    return " ".join(html.unescape(text).split())


def parse_feed_date(value: Optional[str]) -> Optional[datetime]:
    if not value or not value.strip():
        return None
    value = value.strip()
    parsed: Optional[datetime] = None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _first(item: ET.Element, *tags: str) -> Optional[ET.Element]:
    # Explicit `is not None` checks: a found element with no children is falsy.
    for tag in tags:
        element = item.find(tag)
        if element is not None:
            return element
    return None


def _text(element: Optional[ET.Element]) -> str:
    return "".join(element.itertext()).strip() if element is not None else ""


def _atom_link(item: ET.Element) -> str:
    links = item.findall(f"{ATOM}link")
    for link in links:
        if link.attrib.get("rel", "alternate") == "alternate" and link.attrib.get("href"):
            return link.attrib["href"].strip()
    return links[0].attrib.get("href", "").strip() if links else ""


def parse_feed(xml_text: str) -> List[FeedItem]:
    """Parses an RSS 2.0 or Atom document into FeedItems. Raises ET.ParseError on invalid XML."""
    root = ET.fromstring(xml_text)
    items = root.findall(".//item")
    is_atom = not items
    if is_atom:
        items = root.findall(f".//{ATOM}entry")

    parsed: List[FeedItem] = []
    for item in items:
        title = _text(_first(item, "title", f"{ATOM}title"))
        if is_atom:
            link = _atom_link(item)
        else:
            link_el = _first(item, "link")
            link = _text(link_el) or (link_el.attrib.get("href", "") if link_el is not None else "")
        guid = _text(_first(item, "guid", f"{ATOM}id")) or link
        summary = _text(_first(item, "description", "summary", f"{ATOM}summary", f"{ATOM}content"))
        published = parse_feed_date(
            _text(_first(item, "pubDate", "published", f"{ATOM}published", f"{ATOM}updated", f"{DUBLIN_CORE}date"))
        )
        parsed.append(FeedItem(title=title, link=link, guid=guid, summary=summary, published=published))
    return parsed
