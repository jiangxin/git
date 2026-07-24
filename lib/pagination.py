"""HTML pagination: detect next-page URLs from listing pages."""

from __future__ import annotations

import re
from html.parser import HTMLParser
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
