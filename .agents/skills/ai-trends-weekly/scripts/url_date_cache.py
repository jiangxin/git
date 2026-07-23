"""Persistent URL date cache for cross-week date deduplication.

Stores date resolution results (including "undated") so that URLs that
were already processed in a prior week don't need to be re-fetched for
date extraction in subsequent weeks.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

_CACHE_FILENAME = "url_date_cache.jsonl"
_WRITE_LOCK = threading.Lock()


def _default_cache_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / _CACHE_FILENAME


def load_cache(path: Path | None = None) -> dict[str, dict]:
    p = Path(path) if path else _default_cache_path()
    if not p.is_file():
        return {}
    cache: dict[str, dict] = {}
    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = entry.get("url")
            if url:
                cache[url] = entry
    except OSError:
        pass
    return cache


def append_cache(
    url: str,
    date: str | None,
    *,
    method: str = "unknown",
    path: Path | None = None,
) -> None:
    p = Path(path) if path else _default_cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "url": url,
        "date": date,
        "method": method,
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with _WRITE_LOCK:
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def lookup_date(url: str, cache: dict[str, dict]) -> tuple[str | None, bool]:
    """Check cache for a URL. Returns (date_or_None, found_in_cache).

    If found and date is a string, the URL has a known date.
    If found and date is None, the URL was previously determined undated.
    If not found, returns (None, False).
    """
    entry = cache.get(url)
    if entry is None:
        return None, False
    return entry.get("date"), True
