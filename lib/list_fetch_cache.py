"""Short-TTL cache for discovery list / RSS page bodies.

Avoids re-downloading the same feed or listing page on repeated runs within
a week. Supports optional ETag / Last-Modified validators for conditional GET.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_CACHE_DIRNAME = "list_fetch_cache"
_WRITE_LOCK = threading.Lock()

DEFAULT_LIST_CACHE_TTL_SECONDS = 1800  # 30 minutes


def _default_cache_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / _CACHE_DIRNAME


def _key_for_url(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


@dataclass
class ListCacheEntry:
    url: str
    body: str
    fetched_at: float
    etag: str | None = None
    last_modified: str | None = None  # raw HTTP header value

    def is_fresh(self, ttl_seconds: int, *, now: float | None = None) -> bool:
        current = time.time() if now is None else now
        return (current - self.fetched_at) <= max(0, ttl_seconds)


class ListFetchCache:
    """Per-URL discovery body cache stored under ``data/list_fetch_cache/``."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir else _default_cache_dir()
        self._mem: dict[str, ListCacheEntry] = {}
        self._mem_lock = threading.Lock()

    def _path_for(self, url: str) -> Path:
        return self.cache_dir / f"{_key_for_url(url)}.json"

    def lookup(self, url: str) -> ListCacheEntry | None:
        with self._mem_lock:
            hit = self._mem.get(url)
            if hit is not None:
                return hit
        path = self._path_for(url)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or data.get("url") != url:
            return None
        body = data.get("body")
        fetched_at = data.get("fetched_at")
        if not isinstance(body, str) or not isinstance(fetched_at, (int, float)):
            return None
        entry = ListCacheEntry(
            url=url,
            body=body,
            fetched_at=float(fetched_at),
            etag=data.get("etag") if isinstance(data.get("etag"), str) else None,
            last_modified=(
                data.get("last_modified")
                if isinstance(data.get("last_modified"), str)
                else None
            ),
        )
        with self._mem_lock:
            self._mem[url] = entry
        return entry

    def store(
        self,
        url: str,
        body: str,
        *,
        etag: str | None = None,
        last_modified: str | None = None,
        fetched_at: float | None = None,
    ) -> ListCacheEntry:
        entry = ListCacheEntry(
            url=url,
            body=body,
            fetched_at=time.time() if fetched_at is None else fetched_at,
            etag=etag,
            last_modified=last_modified,
        )
        payload = {
            "url": entry.url,
            "body": entry.body,
            "fetched_at": entry.fetched_at,
            "etag": entry.etag,
            "last_modified": entry.last_modified,
        }
        path = self._path_for(url)
        with _WRITE_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(payload, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        with self._mem_lock:
            self._mem[url] = entry
        return entry

    def touch(self, url: str, *, fetched_at: float | None = None) -> ListCacheEntry | None:
        """Refresh ``fetched_at`` after a 304 Not Modified response."""
        entry = self.lookup(url)
        if entry is None:
            return None
        return self.store(
            url,
            entry.body,
            etag=entry.etag,
            last_modified=entry.last_modified,
            fetched_at=time.time() if fetched_at is None else fetched_at,
        )


def parse_list_cache_ttl_seconds(
    cfg: dict[str, Any] | None,
    override: int | None = None,
) -> int:
    if override is not None:
        return max(0, int(override))
    if not cfg:
        return DEFAULT_LIST_CACHE_TTL_SECONDS
    raw = cfg.get("list_cache_ttl_seconds")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return max(0, int(raw))
    if isinstance(raw, str) and raw.strip().isdigit():
        return max(0, int(raw.strip()))
    return DEFAULT_LIST_CACHE_TTL_SECONDS


def parse_known_url_streak_stop(
    cfg: dict[str, Any] | None,
    override: int | None = None,
) -> int:
    """Consecutive known/skipped URLs (newest-first) before stopping the candidate loop.

    ``0`` disables streak early-stop.
    """
    default = 5
    if override is not None:
        return max(0, int(override))
    if not cfg:
        return default
    raw = cfg.get("known_url_streak_stop")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return max(0, int(raw))
    if isinstance(raw, str) and raw.strip().isdigit():
        return max(0, int(raw.strip()))
    return default
