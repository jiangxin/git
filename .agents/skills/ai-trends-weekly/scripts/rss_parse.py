"""Parse RSS 2.0 / Atom feeds into discovery candidate dicts."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

# filter_by_date lives in skills/_shared/scripts
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared" / "scripts"))
from filter_by_date import extract_date  # noqa: E402


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_feed_date(value: str | None) -> str | None:
    """Normalize feed dates (YYYY-MM-DD, ISO, RFC 822) to YYYY-MM-DD."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    day = extract_date(text)
    if day:
        return day
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d")


def _child_text(el: ET.Element, *names: str) -> str | None:
    want = {n.lower() for n in names}
    for child in el:
        if _local(child.tag).lower() in want:
            text = "".join(child.itertext()).strip()
            if text:
                return text
    return None


def _atom_link(entry: ET.Element) -> str | None:
    """Prefer rel=alternate; else first href."""
    fallback: str | None = None
    for child in entry:
        if _local(child.tag).lower() != "link":
            continue
        href = (child.attrib.get("href") or "").strip()
        if not href:
            # RSS-style <link>text</link> inside Atom is unusual; skip
            continue
        rel = (child.attrib.get("rel") or "alternate").strip().lower()
        if rel in ("alternate", ""):
            return href
        if fallback is None:
            fallback = href
    return fallback


def _rss_link(item: ET.Element) -> str | None:
    link = _child_text(item, "link")
    if link:
        return link.strip()
    # guid sometimes holds the permalink
    for child in item:
        if _local(child.tag).lower() != "guid":
            continue
        text = "".join(child.itertext()).strip()
        is_permalink = (child.attrib.get("isPermaLink") or "true").lower() != "false"
        if text.startswith(("http://", "https://")) and is_permalink:
            return text
    return None


def _entry_from_rss_item(item: ET.Element, base_url: str | None) -> dict[str, Any] | None:
    href = _rss_link(item)
    if not href:
        return None
    if base_url:
        href = urljoin(base_url, href)
    if not href.startswith(("http://", "https://")):
        return None
    title = _child_text(item, "title") or href
    pub_raw = _child_text(item, "pubDate", "published", "updated", "date")
    # Dublin Core
    if pub_raw is None:
        for child in item:
            if _local(child.tag).lower() == "date":
                pub_raw = "".join(child.itertext()).strip() or None
                break
    return {
        "url": href.split("#", 1)[0],
        "original_title": " ".join(title.split()).strip(),
        "publish_date": parse_feed_date(pub_raw),
    }


def _entry_from_atom(entry: ET.Element, base_url: str | None) -> dict[str, Any] | None:
    href = _atom_link(entry)
    if not href:
        # Some Atom feeds put URL in <id>
        ident = _child_text(entry, "id")
        if ident and ident.startswith(("http://", "https://")):
            href = ident
    if not href:
        return None
    if base_url:
        href = urljoin(base_url, href)
    if not href.startswith(("http://", "https://")):
        return None
    title = _child_text(entry, "title") or href
    pub_raw = _child_text(entry, "published", "updated")
    return {
        "url": href.split("#", 1)[0],
        "original_title": " ".join(title.split()).strip(),
        "publish_date": parse_feed_date(pub_raw),
    }


def parse_feed(xml_text: str, *, base_url: str | None = None) -> list[dict[str, Any]]:
    """Parse RSS/Atom XML into ``{url, original_title, publish_date}`` items.

    Malformed XML returns an empty list (caller may treat as discovery failure).
    """
    text = (xml_text or "").strip()
    if not text:
        return []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    root_name = _local(root.tag).lower()
    items: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(entry: dict[str, Any] | None) -> None:
        if entry is None:
            return
        url = entry["url"]
        if url in seen:
            return
        seen.add(url)
        items.append(entry)

    if root_name == "feed":
        for child in root:
            if _local(child.tag).lower() == "entry":
                add(_entry_from_atom(child, base_url))
        return items

    # RSS 2.0: <rss><channel><item>… or RDF-ish <rdf:RDF><item>
    candidates = root.iter()
    for el in candidates:
        name = _local(el.tag).lower()
        if name == "item":
            add(_entry_from_rss_item(el, base_url))
        elif name == "entry":
            add(_entry_from_atom(el, base_url))
    return items
