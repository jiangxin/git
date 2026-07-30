"""HTTP and Playwright browser fetch backends for discover_and_fetch.

``fetch_html`` selects ``http`` vs ``browser`` and optionally one-shots a
browser retry when HTTP hits a Cloudflare challenge.
``fetch_html_with_backoff`` retries 429/5xx with exponential backoff.
"""

from __future__ import annotations

import fcntl
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Literal

from check_cloudflare import is_cloudflare
from repo_config import load_repo_config

FetchMode = Literal["http", "browser"]
FetchFn = Callable[..., str]

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_RETRYABLE_HTTP = re.compile(r"\bHTTP (429|5\d{2})\b")
DEFAULT_RETRY_MAX = 3
DEFAULT_RETRY_BASE_DELAY = 0.5

STEALTH_JS = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// Override navigator.plugins to appear non-empty
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5]
});

// Override navigator.languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en']
});

// Override WebGL vendor and renderer
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) {
        return 'Intel Inc.';
    }
    if (parameter === 37446) {
        return 'Intel Iris OpenGL Engine';
    }
    return getParameter.call(this, parameter);
};

// Hide automation-related properties
delete navigator.__proto__.webdriver;
"""


class FetchError(Exception):
    """HTTP, browser, or Cloudflare failure while fetching a URL."""

    def __init__(self, url: str, method: str, reason: str):
        super().__init__(reason)
        self.url = url
        self.method = method
        self.reason = reason


def parse_fetch_mode(source: dict[str, Any] | None) -> FetchMode:
    """Read ``fetch`` from a source entry; default ``http``."""
    if not isinstance(source, dict):
        return "http"
    raw = source.get("fetch", "http")
    if raw == "browser":
        return "browser"
    return "http"


def parse_browser_on_cloudflare(source: dict[str, Any] | None) -> bool:
    """Read ``browser_on_cloudflare``; default True."""
    if not isinstance(source, dict):
        return True
    if "browser_on_cloudflare" not in source:
        return True
    return bool(source.get("browser_on_cloudflare"))


def proxy_attempts(use_proxy: Any, proxy: str | None) -> list[bool]:
    """Return ordered list of whether to use proxy for each attempt."""
    has_proxy = bool(proxy)
    if use_proxy is True:
        return [True] if has_proxy else [False]
    if use_proxy is False:
        return [False, True] if has_proxy else [False]
    # "auto" or anything else: direct first, then proxy
    return [False, True] if has_proxy else [False]


def method_label(use_proxy_flag: bool, *, mode: FetchMode = "http") -> str:
    if mode == "browser":
        return "browser(proxy)" if use_proxy_flag else "browser(direct)"
    return "curl(proxy)" if use_proxy_flag else "curl(direct)"


def fetch_http_result(
    url: str,
    *,
    proxy: str | None,
    use_proxy_flag: bool,
    timeout: int = 30,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Fetch URL and return body plus cache validators.

    Returns ``{"body", "etag", "last_modified", "not_modified"}``.
    On HTTP 304, ``body`` is ``""`` and ``not_modified`` is True.
    """
    method = method_label(use_proxy_flag, mode="http")
    handlers = []
    if use_proxy_flag and proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    headers = dict(DEFAULT_HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    try:
        with opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            body = resp.read().decode(charset, errors="replace")
            return {
                "body": body,
                "etag": resp.headers.get("ETag"),
                "last_modified": resp.headers.get("Last-Modified"),
                "not_modified": False,
            }
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return {
                "body": "",
                "etag": e.headers.get("ETag") if e.headers else None,
                "last_modified": (
                    e.headers.get("Last-Modified") if e.headers else None
                ),
                "not_modified": True,
            }
        raise FetchError(url, method, f"HTTP {e.code}") from e
    except Exception as e:  # noqa: BLE001 — surface as fetch failure
        raise FetchError(url, method, str(e) or type(e).__name__) from e


def fetch_http(
    url: str,
    *,
    proxy: str | None,
    use_proxy_flag: bool,
    timeout: int = 30,
) -> str:
    """Fetch URL via urllib with browser-like headers. Raises FetchError."""
    return fetch_http_result(
        url, proxy=proxy, use_proxy_flag=use_proxy_flag, timeout=timeout,
    )["body"]


_HTTP_DATE_FORMATS = [
    "%a, %d %b %Y %H:%M:%S %Z",
    "%a, %d %b %Y %H:%M:%S %z",
    "%A, %d-%b-%y %H:%M:%S %Z",
    "%a %b %d %H:%M:%S %Y",
]


def parse_last_modified(value: str | None) -> str | None:
    """Parse HTTP Last-Modified header to YYYY-MM-DD date string."""
    if not value:
        return None
    text = value.strip()
    for fmt in _HTTP_DATE_FORMATS:
        try:
            from datetime import datetime as _dt
            dt = _dt.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def fetch_http_with_headers(
    url: str,
    *,
    proxy: str | None,
    use_proxy_flag: bool,
    timeout: int = 30,
) -> tuple[str, str | None]:
    """Fetch URL and return (html, last_modified_date_or_None)."""
    method = method_label(use_proxy_flag, mode="http")
    handlers = []
    if use_proxy_flag and proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    try:
        with opener.open(req, timeout=timeout) as resp:
            last_mod = parse_last_modified(resp.headers.get("Last-Modified"))
            charset = resp.headers.get_content_charset() or "utf-8"
            html = resp.read().decode(charset, errors="replace")
            return html, last_mod
    except urllib.error.HTTPError as e:
        raise FetchError(url, method, f"HTTP {e.code}") from e
    except Exception as e:
        raise FetchError(url, method, str(e) or type(e).__name__) from e


def fetch_last_modified(
    url: str,
    *,
    proxy: str | None,
    use_proxy_flag: bool,
    timeout: int = 15,
) -> str | None:
    """HEAD request; return Last-Modified as YYYY-MM-DD or None."""
    method = method_label(use_proxy_flag, mode="http")
    handlers = []
    if use_proxy_flag and proxy:
        handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
    else:
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS, method="HEAD")
    try:
        with opener.open(req, timeout=timeout) as resp:
            return parse_last_modified(resp.headers.get("Last-Modified"))
    except Exception:
        return None


def _get_storage_state_path(storage_state: str | None = None) -> Path | None:
    """Read playwright_storage_state from config.json and return expanded path.
    
    If storage_state is provided, use it as a key to look up in the states directory.
    Otherwise, fall back to the global playwright_storage_state config.
    """
    try:
        cfg = load_repo_config(Path(__file__))
        
        # If a specific storage_state key is provided, use the states directory
        if storage_state:
            states_dir = cfg.get("playwright_storage_state_dir", "~/.playwright-cli/states")
            return Path(states_dir).expanduser() / f"{storage_state}.json"
        
        # Otherwise, use the global playwright_storage_state config
        raw = cfg.get("playwright_storage_state")
        if not raw or not isinstance(raw, str):
            return None
        return Path(raw).expanduser()
    except Exception:
        return None


def _load_storage_state(path: Path) -> dict[str, Any] | None:
    """Load storage_state from file, returning None on any error."""
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def _save_storage_state(path: Path, state: dict[str, Any]) -> None:
    """Save storage_state to file with exclusive locking."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(state, f, ensure_ascii=False, indent=2)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


def fetch_browser(
    url: str,
    *,
    proxy: str | None,
    use_proxy_flag: bool,
    timeout: int = 30,
    stealth: bool = False,
    storage_state: str | None = None,
) -> str:
    """Fetch URL via Playwright Chromium. Raises FetchError if unavailable."""
    method = method_label(use_proxy_flag, mode="browser")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise FetchError(
            url,
            method,
            "playwright not installed; pip install playwright && playwright install chromium",
        ) from e

    launch_kwargs: dict[str, Any] = {"headless": True}
    context_kwargs: dict[str, Any] = {"user_agent": USER_AGENT}
    if use_proxy_flag and proxy:
        context_kwargs["proxy"] = {"server": proxy}

    storage_state_path = _get_storage_state_path(storage_state)
    if storage_state_path:
        loaded_state = _load_storage_state(storage_state_path)
        if loaded_state:
            context_kwargs["storage_state"] = loaded_state

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**launch_kwargs)
            try:
                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                
                if stealth:
                    page.add_init_script(STEALTH_JS)
                
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=max(timeout, 1) * 1000,
                )
                html = page.content()
                
                if storage_state_path:
                    try:
                        state = context.storage_state()
                        _save_storage_state(storage_state_path, state)
                    except Exception:
                        pass
                
                context.close()
                return html
            finally:
                browser.close()
    except FetchError:
        raise
    except Exception as e:  # noqa: BLE001 — missing browser / navigation
        reason = str(e).strip() or type(e).__name__
        if "Executable doesn't exist" in reason or "BrowserType.launch" in reason:
            reason = (
                f"playwright chromium missing ({reason}); "
                "run: playwright install chromium"
            )
        raise FetchError(url, method, reason) from e


def _fetch_attempts(
    url: str,
    *,
    mode: FetchMode,
    use_proxy: Any,
    proxy: str | None,
    fetch_fn: FetchFn,
    timeout: int = 30,
) -> tuple[str, str]:
    """Try proxy policy for one backend; reject Cloudflare HTML."""
    last_err: FetchError | None = None
    saw_cloudflare = False
    for flag in proxy_attempts(use_proxy, proxy):
        method = method_label(flag, mode=mode)
        try:
            html = fetch_fn(
                url, proxy=proxy, use_proxy_flag=flag, timeout=timeout
            )
        except FetchError as e:
            last_err = e
            continue
        if is_cloudflare(html):
            saw_cloudflare = True
            last_err = FetchError(url, method, "Cloudflare challenge")
            continue
        return html, method
    if last_err is None:
        last_err = FetchError(url, mode, "fetch failed")
    # Attach flag via attribute for caller (Cloudflare downgrade decision)
    last_err.saw_cloudflare = saw_cloudflare  # type: ignore[attr-defined]
    raise last_err


def fetch_html(
    url: str,
    *,
    mode: FetchMode = "http",
    use_proxy: Any = "auto",
    proxy: str | None = None,
    browser_on_cloudflare: bool = True,
    http_fetch_fn: FetchFn | None = None,
    browser_fetch_fn: FetchFn | None = None,
    timeout: int = 30,
) -> tuple[str, str]:
    """Fetch HTML via ``http`` or ``browser``; optional one CF→browser retry.

    Returns ``(html, method_label)``. Missing Playwright/Chromium raises
    ``FetchError`` (callers log and continue).
    """
    http_fn = http_fetch_fn or fetch_http
    browser_fn = browser_fetch_fn or fetch_browser

    if mode == "browser":
        return _fetch_attempts(
            url,
            mode="browser",
            use_proxy=use_proxy,
            proxy=proxy,
            fetch_fn=browser_fn,
            timeout=timeout,
        )

    try:
        return _fetch_attempts(
            url,
            mode="http",
            use_proxy=use_proxy,
            proxy=proxy,
            fetch_fn=http_fn,
            timeout=timeout,
        )
    except FetchError as e:
        # Only downgrade when HTTP returned a Cloudflare challenge page.
        saw_cf = bool(getattr(e, "saw_cloudflare", False))
        if not (browser_on_cloudflare and saw_cf):
            raise
        # One-shot browser downgrade for the same URL
        return _fetch_attempts(
            url,
            mode="browser",
            use_proxy=use_proxy,
            proxy=proxy,
            fetch_fn=browser_fn,
            timeout=timeout,
        )


def is_retryable_fetch_error(err: FetchError) -> bool:
    """True for HTTP 429 and 5xx responses (safe to back off and retry)."""
    return bool(_RETRYABLE_HTTP.search(err.reason or ""))


def fetch_html_with_backoff(
    url: str,
    *,
    mode: FetchMode = "http",
    use_proxy: Any = "auto",
    proxy: str | None = None,
    browser_on_cloudflare: bool = True,
    http_fetch_fn: FetchFn | None = None,
    browser_fetch_fn: FetchFn | None = None,
    timeout: int = 30,
    max_retries: int = DEFAULT_RETRY_MAX,
    base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    sleep_fn: Callable[[float], None] | None = None,
) -> tuple[str, str]:
    """Like ``fetch_html`` but retries retryable HTTP failures with backoff."""
    sleeper = sleep_fn or time.sleep
    last_err: FetchError | None = None
    attempts = max(0, int(max_retries)) + 1
    for attempt in range(attempts):
        try:
            return fetch_html(
                url,
                mode=mode,
                use_proxy=use_proxy,
                proxy=proxy,
                browser_on_cloudflare=browser_on_cloudflare,
                http_fetch_fn=http_fetch_fn,
                browser_fetch_fn=browser_fetch_fn,
                timeout=timeout,
            )
        except FetchError as e:
            last_err = e
            if not is_retryable_fetch_error(e) or attempt >= attempts - 1:
                raise
            sleeper(base_delay * (2**attempt))
    assert last_err is not None
    raise last_err
