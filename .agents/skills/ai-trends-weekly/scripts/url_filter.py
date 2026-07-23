"""Candidate URL include/exclude filters and built-in path heuristics."""

from __future__ import annotations

import re
from typing import Any, Sequence
from urllib.parse import urlparse

# Path segments that usually mark nav / taxonomy / pagination pages.
JUNK_PATH_SEGMENTS = frozenset(
    {
        "tag",
        "tags",
        "category",
        "categories",
        "author",
        "authors",
        "page",
        "pages",
        "topic",
        "topics",
        "search",
        "login",
        "signup",
        "about",
        "contact",
        "feed",
        "rss",
        "newsletter",
        "events",
        "podcasts",
        "videos",
    }
)

# Host (www-stripped) → conservative article path patterns.
_BUILTIN_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "techcrunch.com": (re.compile(r"/\d{4}/\d{2}/\d{2}/"),),
    "theverge.com": (re.compile(r"/ai-artificial-intelligence/\d+"),),
    "venturebeat.com": (re.compile(r"/\d{4}/\d{2}/\d{2}/"),),
    "wired.com": (re.compile(r"/story/"),),
    "arstechnica.com": (re.compile(r"/\d{4}/\d{2}/"),),
    "bloomberg.com": (re.compile(r"/news/articles/"),),
    "reuters.com": (re.compile(r"/\d{4}/\d{2}/\d{2}/"),),
}


def normalize_host(netloc: str) -> str:
    host = (netloc or "").lower().split("@")[-1]
    if host.startswith("www."):
        host = host[4:]
    # Drop port for matching
    if ":" in host:
        host = host.rsplit(":", 1)[0]
    return host


def path_segments(path: str) -> list[str]:
    return [p for p in (path or "").split("/") if p]


def path_depth(path: str) -> int:
    return len(path_segments(path))


def has_junk_path(path: str) -> bool:
    return any(seg.lower() in JUNK_PATH_SEGMENTS for seg in path_segments(path))


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [str(x) for x in value if x is not None and str(x)]
    return []


def _compile_patterns(patterns: Sequence[str]) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for raw in patterns:
        try:
            compiled.append(re.compile(raw))
        except re.error:
            continue
    return compiled


def matches_any(url: str, patterns: Sequence[re.Pattern[str]]) -> bool:
    return any(p.search(url) for p in patterns)


def builtin_path_ok(url: str, list_url: str) -> bool:
    """Heuristic when source has no url_include: known-domain patterns or same-site depth."""
    parsed = urlparse(url)
    list_parsed = urlparse(list_url)
    if parsed.scheme not in ("http", "https"):
        return False
    if has_junk_path(parsed.path):
        return False

    host = normalize_host(parsed.netloc)
    list_host = normalize_host(list_parsed.netloc)
    builtins = _BUILTIN_PATTERNS.get(host)
    if builtins is not None:
        return matches_any(parsed.path, builtins)

    # Unknown source: same site, path depth >= 2, not junk.
    if host != list_host:
        return False
    return path_depth(parsed.path) >= 2


def url_allowed(
    url: str,
    *,
    list_url: str,
    url_include: Any = None,
    url_exclude: Any = None,
) -> bool:
    """Return True if *url* should be kept as a detail candidate.

    Order: exclude (any hit → drop) → include (if set, must hit one) → else heuristics.
    """
    if not url or not list_url:
        return False

    exclude_pats = _compile_patterns(_as_str_list(url_exclude))
    if exclude_pats and matches_any(url, exclude_pats):
        return False

    include_list = _as_str_list(url_include)
    if include_list:
        include_pats = _compile_patterns(include_list)
        if not include_pats:
            return False
        return matches_any(url, include_pats)

    return builtin_path_ok(url, list_url)
