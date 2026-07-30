"""HTML and RSS pagination: detect next-page URLs and paginate listing pages."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse


class _NextPageParser(HTMLParser):
    """Extract next-page URL from HTML.

    Priority:
    1. <link rel="next" href="...">
    2. <a rel="next" href="...">
    """

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.link_next: str | None = None
        self.a_next: str | None = None
        self.page_links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "").strip() for k, v in attrs}
        href = ad.get("href")
        rel = ad.get("rel", "").lower()

        if tag == "link" and "next" in rel.split() and href:
            self.link_next = urljoin(self.base_url, href)
            return

        if tag == "a" and href:
            abs_href = urljoin(self.base_url, href)
            if "next" in rel.split():
                self.a_next = abs_href
            self.page_links.append(abs_href)

    def get_result(self) -> str | None:
        if self.link_next:
            return self.link_next
        if self.a_next:
            return self.a_next
        return _detect_by_url_pattern(self.base_url, self.page_links)


def _detect_by_url_pattern(base_url: str, page_links: list[str]) -> str | None:
    """Try to find next page by URL pattern (?page=N, /page/N/)."""
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query, keep_blank_values=True)

    # Try ?page=N, ?p=N patterns
    for param in ("page", "p", "paged", "pg"):
        if param in query:
            try:
                current = int(query[param][0])
                next_val = current + 1
            except (ValueError, IndexError):
                continue
            next_query = dict(query)
            next_query[param] = [str(next_val)]
            next_qs = urlencode(
                {k: v[0] if len(v) == 1 else v for k, v in next_query.items()},
                doseq=True,
            )
            candidate = urlunparse((
                parsed.scheme, parsed.netloc, parsed.path,
                parsed.params, next_qs, parsed.fragment,
            ))
            if candidate in page_links:
                return candidate

    # Try /page/N/ path pattern
    m = re.search(r"/page/(\d+)/?$", parsed.path)
    if m:
        current = int(m.group(1))
        next_path = re.sub(r"/page/\d+/?$", f"/page/{current + 1}/", parsed.path)
        candidate = urlunparse((
            parsed.scheme, parsed.netloc, next_path,
            parsed.params, parsed.query, parsed.fragment,
        ))
        if candidate in page_links:
            return candidate

    return None


def discover_next_page_url(html: str, base_url: str) -> str | None:
    """Detect the next-page URL from an HTML listing page.

    Args:
        html: The HTML content of the listing page.
        base_url: The URL of the listing page (used to resolve relative URLs).

    Returns:
        The absolute URL of the next page, or None if not found.
    """
    parser = _NextPageParser(base_url)
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return None
    return parser.get_result()


def _all_items_older_than(
    items: list[dict[str, Any]], start_date: str
) -> bool:
    """Check if all dated items are older than start_date."""
    dated = [
        item for item in items
        if item.get("publish_date") and item["publish_date"] < start_date
    ]
    return len(dated) > 0 and len(dated) == len([
        item for item in items if item.get("publish_date")
    ])


def _all_items_known(
    items: list[dict[str, Any]], known_urls: set[str] | None,
) -> bool:
    """True when every item URL is already in ``known_urls`` (non-empty page)."""
    if not known_urls or not items:
        return False
    urls = [it.get("url") for it in items if isinstance(it.get("url"), str) and it["url"]]
    return bool(urls) and all(u in known_urls for u in urls)


def paginate_html_discovery(
    list_url: str,
    *,
    fetch_page_fn: Callable[[str], str],
    extract_links_fn: Callable[[str, str], list[dict[str, Any]]],
    max_pages: int,
    start_date: str,
    known_urls: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[tuple[str, str, str]]]:
    """Paginate through HTML listing pages, aggregating all discovered items.

    Args:
        list_url: The URL of the first listing page.
        fetch_page_fn: Callable that fetches a URL and returns HTML content.
            May raise exceptions on failure.
        extract_links_fn: Callable that extracts items from HTML.
            Takes (html, base_url) and returns list of item dicts.
        max_pages: Maximum number of pages to fetch (>= 1).
        start_date: Date string (YYYY-MM-DD). Items older than this trigger
            early-stop when all items on a page are older.
        known_urls: Optional set of already-fetched article URLs. When every
            item on a page is known, pagination stops (resume optimization).

    Returns:
        A tuple of (all_items, errors) where errors is a list of
        (method, url, reason) tuples for failed page fetches.
    """
    all_items: list[dict[str, Any]] = []
    errors: list[tuple[str, str, str]] = []
    seen_urls: set[str] = set()
    current_url = list_url

    for page_num in range(max_pages):
        try:
            html = fetch_page_fn(current_url)
        except Exception as exc:
            errors.append(("pagination", current_url, str(exc)))
            break

        items = extract_links_fn(html, current_url)

        # Dedupe against previously seen URLs
        new_items = []
        for item in items:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                new_items.append(item)
        all_items.extend(new_items)

        # Date early-stop: if all dated items on this page are older than
        # start_date, stop paginating (assuming descending order)
        if _all_items_older_than(new_items, start_date):
            break

        # Resume early-stop: entire page already in url_index
        if _all_items_known(new_items, known_urls):
            break

        # Find next page URL
        if page_num < max_pages - 1:
            next_url = discover_next_page_url(html, current_url)
            if not next_url or next_url in seen_urls:
                break
            current_url = next_url

    return all_items, errors


def _detect_feed_next_url(xml_text: str, feed_url: str) -> str | None:
    """Detect next-page URL from Atom <link rel="next"> tag.

    Returns None if no next link found or if XML is malformed.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None

    tag = root.tag.rsplit("}", 1)[-1].lower() if "}" in root.tag else root.tag.lower()
    if tag != "feed":
        return None  # Not Atom

    for child in root:
        child_tag = child.tag.rsplit("}", 1)[-1].lower() if "}" in child.tag else child.tag.lower()
        if child_tag == "link":
            rel = (child.attrib.get("rel") or "").strip().lower()
            href = (child.attrib.get("href") or "").strip()
            if rel == "next" and href:
                return urljoin(feed_url, href)
    return None


def _build_paged_url(feed_url: str, page: int) -> str:
    """Build a WordPress-style paged URL: feed_url?paged=N."""
    parsed = urlparse(feed_url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["paged"] = [str(page)]
    new_qs = urlencode(
        {k: v[0] if len(v) == 1 else v for k, v in query.items()},
        doseq=True,
    )
    return urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, new_qs, "",
    ))


def paginate_feed_discovery(
    feed_url: str,
    *,
    fetch_feed_fn: Callable[[str], str],
    parse_feed_fn: Callable[[str, str], list[dict[str, Any]]],
    max_pages: int,
    start_date: str,
    known_urls: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[tuple[str, str, str]]]:
    """Paginate through RSS/Atom feeds, aggregating all discovered items.

    Supports two pagination strategies:
    1. Atom <link rel="next"> (detected automatically)
    2. WordPress ?paged=N (tried for RSS feeds without Atom next link)

    Falls back to single-page behavior if neither strategy works.

    Args:
        feed_url: The URL of the first feed page.
        fetch_feed_fn: Callable that fetches a URL and returns XML content.
        parse_feed_fn: Callable that parses XML into items.
            Takes (xml_text, base_url) and returns list of item dicts.
        max_pages: Maximum number of pages to fetch (>= 1).
        start_date: Date string (YYYY-MM-DD). Items older than this trigger
            early-stop when all items on a page are older.
        known_urls: Optional set of already-fetched article URLs. When every
            item on a page is known, pagination stops (resume optimization).

    Returns:
        A tuple of (all_items, errors) where errors is a list of
        (method, url, reason) tuples for failed page fetches.
    """
    all_items: list[dict[str, Any]] = []
    errors: list[tuple[str, str, str]] = []
    seen_urls: set[str] = set()
    current_url = feed_url
    use_paged = False
    page_num = 0

    for page_idx in range(max_pages):
        try:
            xml_text = fetch_feed_fn(current_url)
        except Exception as exc:
            # If we're trying WordPress paged for the first time and it fails,
            # silently stop (the feed just doesn't support paged pagination).
            if use_paged and page_idx == 1:
                break
            errors.append(("pagination", current_url, str(exc)))
            break

        items = parse_feed_fn(xml_text, current_url)

        # Dedupe
        new_items = []
        for item in items:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                new_items.append(item)
        all_items.extend(new_items)

        # Date early-stop
        if _all_items_older_than(new_items, start_date):
            break

        # Resume early-stop: entire page already in url_index
        if _all_items_known(new_items, known_urls):
            break

        # Find next page
        if page_idx < max_pages - 1:
            # Strategy 1: Atom <link rel="next">
            next_url = _detect_feed_next_url(xml_text, current_url)
            if next_url:
                current_url = next_url
                continue

            # Strategy 2: WordPress ?paged=N
            if page_idx == 0:
                # First page: try paged=2 and see if it returns different items
                use_paged = True
            if use_paged:
                page_num = page_idx + 2
                candidate = _build_paged_url(feed_url, page_num)
                if candidate == current_url:
                    break  # No progress
                current_url = candidate
                continue

            break  # No pagination strategy worked

    return all_items, errors
