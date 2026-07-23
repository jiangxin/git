"""Restricted site search fallback for list discovery (thin API wrapper)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable
from urllib.parse import urlparse

SearchFn = Callable[..., list[dict[str, Any]]]


class SearchSkipped(Exception):
    """Search fallback cannot run (missing key / unsupported provider)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def resolve_search_config(
    cfg: dict[str, Any] | None,
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Build search API config from repo config + env, or None if unusable.

    Expected ``config.json`` shape (optional)::

        "search_api": {
          "provider": "serper",
          "api_key_env": "SERPER_API_KEY"
        }

    Env ``SEARCH_API_KEY`` / provider-specific env also accepted.
    """
    env_map = env if env is not None else os.environ
    block = (cfg or {}).get("search_api") if isinstance(cfg, dict) else None
    provider = "serper"
    api_key_env = "SERPER_API_KEY"
    if isinstance(block, dict):
        raw_provider = block.get("provider")
        if isinstance(raw_provider, str) and raw_provider.strip():
            provider = raw_provider.strip().lower()
        raw_env = block.get("api_key_env")
        if isinstance(raw_env, str) and raw_env.strip():
            api_key_env = raw_env.strip()
        inline = block.get("api_key")
        if isinstance(inline, str) and inline.strip():
            return {"provider": provider, "api_key": inline.strip()}

    key = (env_map.get(api_key_env) or env_map.get("SEARCH_API_KEY") or "").strip()
    if not key:
        return None
    return {"provider": provider, "api_key": key}


def build_site_query(source_name: str, list_url: str, start_date: str, end_date: str) -> str:
    """Predefined restricted query: site + source name + date window hint."""
    host = urlparse(list_url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    name = " ".join((source_name or "").split()).strip() or host
    # Keep template fixed; providers interpret after:/before: loosely.
    return f'site:{host} "{name}" after:{start_date} before:{end_date}'


def _serper_search(
    query: str,
    *,
    api_key: str,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    payload = json.dumps({"q": query, "num": 10}).encode("utf-8")
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "X-API-KEY": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise SearchSkipped(f"serper HTTP {e.code}") from e
    except Exception as e:  # noqa: BLE001
        raise SearchSkipped(str(e) or type(e).__name__) from e

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise SearchSkipped("serper invalid JSON") from e

    organic = data.get("organic") if isinstance(data, dict) else None
    if not isinstance(organic, list):
        return []
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in organic:
        if not isinstance(row, dict):
            continue
        url = row.get("link")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        url = url.split("#", 1)[0]
        if url in seen:
            continue
        seen.add(url)
        title = row.get("title")
        items.append(
            {
                "url": url,
                "original_title": (
                    " ".join(str(title).split()).strip() if title else url
                ),
                "publish_date": None,
            }
        )
    return items


def restricted_search(
    *,
    source_name: str,
    list_url: str,
    start_date: str,
    end_date: str,
    search_cfg: dict[str, Any] | None,
    search_fn: SearchFn | None = None,
) -> list[dict[str, Any]]:
    """Run restricted search; raises SearchSkipped when unavailable."""
    if search_fn is not None:
        return search_fn(
            source_name=source_name,
            list_url=list_url,
            start_date=start_date,
            end_date=end_date,
            search_cfg=search_cfg,
        )
    if not search_cfg or not search_cfg.get("api_key"):
        raise SearchSkipped("search API key not configured")
    provider = str(search_cfg.get("provider") or "serper").lower()
    query = build_site_query(source_name, list_url, start_date, end_date)
    if provider == "serper":
        return _serper_search(query, api_key=str(search_cfg["api_key"]))
    raise SearchSkipped(f"unsupported search provider: {provider}")
