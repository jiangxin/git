"""Unit tests for fetch_backends (http/browser + Cloudflare downgrade)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetch_backends import (  # noqa: E402
    FetchError,
    _get_storage_state_path,
    _load_storage_state,
    _save_storage_state,
    fetch_browser,
    fetch_html,
    fetch_html_with_backoff,
    is_retryable_fetch_error,
    method_label,
    parse_browser_on_cloudflare,
    parse_fetch_mode,
    parse_last_modified,
)

CF_HTML = """<!DOCTYPE html>
<html><body>
Checking your browser before accessing example.com
cdn-cgi/challenge-platform
</body></html>
"""

OK_HTML = """<!DOCTYPE html>
<html><head><title>OK</title></head>
<body><article><p>Real article body.</p></article></body></html>
"""


class TestParseFetchConfig:
    def test_default_http(self):
        assert parse_fetch_mode({}) == "http"
        assert parse_fetch_mode(None) == "http"
        assert parse_fetch_mode({"fetch": "http"}) == "http"

    def test_browser_mode(self):
        assert parse_fetch_mode({"fetch": "browser"}) == "browser"

    def test_unknown_fetch_falls_back_to_http(self):
        assert parse_fetch_mode({"fetch": "curl"}) == "http"

    def test_browser_on_cloudflare_default_true(self):
        assert parse_browser_on_cloudflare({}) is True
        assert parse_browser_on_cloudflare(None) is True

    def test_browser_on_cloudflare_false(self):
        assert parse_browser_on_cloudflare({"browser_on_cloudflare": False}) is False


class TestMethodLabel:
    def test_http_and_browser_labels(self):
        assert method_label(False, mode="http") == "curl(direct)"
        assert method_label(True, mode="http") == "curl(proxy)"
        assert method_label(False, mode="browser") == "browser(direct)"
        assert method_label(True, mode="browser") == "browser(proxy)"


class TestFetchHtmlBackends:
    def test_http_mode_uses_http_fetch(self):
        calls: list[str] = []

        def http_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            calls.append("http")
            return OK_HTML

        def browser_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            calls.append("browser")
            return OK_HTML

        html, method = fetch_html(
            "https://example.com/a",
            mode="http",
            use_proxy=False,
            proxy=None,
            http_fetch_fn=http_fn,
            browser_fetch_fn=browser_fn,
        )
        assert html == OK_HTML
        assert method == "curl(direct)"
        assert calls == ["http"]

    def test_browser_mode_uses_browser_fetch(self):
        calls: list[str] = []

        def http_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            calls.append("http")
            return OK_HTML

        def browser_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            calls.append("browser")
            return OK_HTML

        html, method = fetch_html(
            "https://example.com/a",
            mode="browser",
            use_proxy=False,
            proxy=None,
            http_fetch_fn=http_fn,
            browser_fetch_fn=browser_fn,
        )
        assert html == OK_HTML
        assert method == "browser(direct)"
        assert calls == ["browser"]

    def test_cloudflare_downgrades_to_browser_once(self):
        calls: list[str] = []

        def http_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            calls.append("http")
            return CF_HTML

        def browser_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            calls.append("browser")
            return OK_HTML

        html, method = fetch_html(
            "https://example.com/cf",
            mode="http",
            use_proxy=False,
            proxy=None,
            browser_on_cloudflare=True,
            http_fetch_fn=http_fn,
            browser_fetch_fn=browser_fn,
        )
        assert html == OK_HTML
        assert method == "browser(direct)"
        assert calls == ["http", "browser"]

    def test_cloudflare_no_downgrade_when_disabled(self):
        def http_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            return CF_HTML

        def browser_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            pytest.fail("browser must not be called")

        with pytest.raises(FetchError) as ei:
            fetch_html(
                "https://example.com/cf",
                mode="http",
                use_proxy=False,
                proxy=None,
                browser_on_cloudflare=False,
                http_fetch_fn=http_fn,
                browser_fetch_fn=browser_fn,
            )
        assert "Cloudflare" in ei.value.reason

    def test_non_cf_http_error_does_not_downgrade(self):
        def http_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            raise FetchError(url, "curl(direct)", "HTTP 500")

        def browser_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            pytest.fail("browser must not be called for non-CF errors")

        with pytest.raises(FetchError) as ei:
            fetch_html(
                "https://example.com/err",
                mode="http",
                use_proxy=False,
                proxy=None,
                browser_on_cloudflare=True,
                http_fetch_fn=http_fn,
                browser_fetch_fn=browser_fn,
            )
        assert ei.value.reason == "HTTP 500"

    def test_missing_playwright_raises_fetch_error(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "playwright" or name.startswith("playwright."):
                raise ImportError("No module named playwright")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        with pytest.raises(FetchError) as ei:
            fetch_browser(
                "https://example.com/x",
                proxy=None,
                use_proxy_flag=False,
            )
        assert "playwright not installed" in ei.value.reason
        assert ei.value.method == "browser(direct)"


class TestBackoffRetry:
    def test_is_retryable_429_and_5xx(self):
        assert is_retryable_fetch_error(FetchError("u", "m", "HTTP 429"))
        assert is_retryable_fetch_error(FetchError("u", "m", "HTTP 503"))
        assert not is_retryable_fetch_error(FetchError("u", "m", "HTTP 404"))
        assert not is_retryable_fetch_error(FetchError("u", "m", "Cloudflare challenge"))

    def test_backoff_retries_then_succeeds(self):
        calls = {"n": 0}
        sleeps: list[float] = []

        def http_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            calls["n"] += 1
            if calls["n"] < 3:
                raise FetchError(url, "curl(direct)", "HTTP 503")
            return OK_HTML

        html, method = fetch_html_with_backoff(
            "https://example.com/retry",
            mode="http",
            use_proxy=False,
            proxy=None,
            browser_on_cloudflare=False,
            http_fetch_fn=http_fn,
            max_retries=3,
            base_delay=0.1,
            sleep_fn=sleeps.append,
        )
        assert "Real article body" in html
        assert calls["n"] == 3
        assert sleeps == [0.1, 0.2]
        assert method.startswith("curl")

    def test_non_retryable_fails_immediately(self):
        calls = {"n": 0}

        def http_fn(url, *, proxy=None, use_proxy_flag=False, timeout=30):
            calls["n"] += 1
            raise FetchError(url, "curl(direct)", "HTTP 404")

        with pytest.raises(FetchError) as ei:
            fetch_html_with_backoff(
                "https://example.com/404",
                mode="http",
                use_proxy=False,
                proxy=None,
                browser_on_cloudflare=False,
                http_fetch_fn=http_fn,
                max_retries=3,
                sleep_fn=lambda _: None,
            )
        assert ei.value.reason == "HTTP 404"
        assert calls["n"] == 1


@pytest.mark.skip(reason="optional live Playwright; enable manually when chromium installed")
def test_playwright_integration_optional():
    html, method = fetch_html(
        "https://example.com/",
        mode="browser",
        use_proxy=False,
        proxy=None,
        browser_on_cloudflare=False,
    )
    assert "Example Domain" in html or "<html" in html.lower()
    assert method.startswith("browser")


class TestParseLastModified:
    def test_rfc_7231_format(self):
        assert parse_last_modified("Sun, 06 Nov 1994 08:49:37 GMT") == "1994-11-06"

    def test_iso_date(self):
        assert parse_last_modified("2026-07-23T14:00:00Z") is None

    def test_none_input(self):
        assert parse_last_modified(None) is None

    def test_empty_input(self):
        assert parse_last_modified("") is None

    def test_invalid_format(self):
        assert parse_last_modified("not a date") is None


class TestStorageState:
    def test_load_nonexistent_file(self, tmp_path):
        """Loading a non-existent file should return None."""
        path = tmp_path / "nonexistent.json"
        assert _load_storage_state(path) is None

    def test_load_valid_file(self, tmp_path):
        """Loading a valid storage_state file should return the data."""
        path = tmp_path / "state.json"
        test_data = {"cookies": [{"name": "test", "value": "123"}]}
        path.write_text(json.dumps(test_data))
        
        result = _load_storage_state(path)
        assert result == test_data

    def test_load_corrupted_file(self, tmp_path):
        """Loading a corrupted file should return None."""
        path = tmp_path / "corrupted.json"
        path.write_text("{ invalid json }")
        
        assert _load_storage_state(path) is None

    def test_save_and_load_roundtrip(self, tmp_path):
        """Saving and loading should preserve the data."""
        path = tmp_path / "state.json"
        test_data = {
            "cookies": [{"name": "session", "value": "abc123"}],
            "origins": []
        }
        
        _save_storage_state(path, test_data)
        loaded = _load_storage_state(path)
        
        assert loaded == test_data

    def test_save_creates_parent_dirs(self, tmp_path):
        """Saving should create parent directories if they don't exist."""
        path = tmp_path / "subdir" / "nested" / "state.json"
        test_data = {"cookies": []}
        
        _save_storage_state(path, test_data)
        
        assert path.exists()
        assert _load_storage_state(path) == test_data

    def test_get_storage_state_path_with_config(self, tmp_path, monkeypatch):
        """Should read path from config.json."""
        config_path = tmp_path / "config.json"
        state_path = tmp_path / "state.json"
        config_path.write_text(json.dumps({
            "playwright_storage_state": str(state_path)
        }))
        
        # Mock the config file location
        import fetch_backends
        original_load = fetch_backends.load_repo_config
        
        def mock_load(*args, **kwargs):
            return json.loads(config_path.read_text())
        
        monkeypatch.setattr(fetch_backends, "load_repo_config", mock_load)
        
        result = _get_storage_state_path()
        assert result == state_path

    def test_get_storage_state_path_without_config(self, monkeypatch):
        """Should return None when config doesn't have the key."""
        import fetch_backends
        
        def mock_load(*args, **kwargs):
            return {}
        
        monkeypatch.setattr(fetch_backends, "load_repo_config", mock_load)
        
        result = _get_storage_state_path()
        assert result is None
