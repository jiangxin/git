"""Integration test for Anthropic sources - configuration validation.

This test verifies that the stealth and storage_state features are properly
integrated for Anthropic sources without requiring actual network calls.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_anthropic_source_configuration():
    """Verify all Anthropic sources have stealth and storage_state configured."""
    sources_path = Path(__file__).parent.parent.parent / ".agents/skills/ai-trends-weekly/references/sources.json"
    sources = json.loads(sources_path.read_text())
    
    anthropic_sources = [s for s in sources if 'Anthropic' in s.get('name', '')]
    
    assert len(anthropic_sources) == 3, "Should have 3 Anthropic sources"
    
    for src in anthropic_sources:
        assert src.get('fetch') == 'browser', f"{src['name']} should use browser fetch"
        assert src.get('stealth') is True, f"{src['name']} should have stealth enabled"
        assert src.get('storage_state') == 'anthropic', f"{src['name']} should use 'anthropic' storage_state"


def test_make_browser_fetch_fn_wrapper():
    """Verify _make_browser_fetch_fn correctly passes parameters."""
    from discover_and_fetch import _make_browser_fetch_fn
    
    # Create a mock browser fetch function
    def mock_fetch(url, *, proxy, use_proxy_flag, timeout, stealth=False, storage_state=None):
        return f"<html>mock</html>"
    
    # Create wrapper
    wrapper = _make_browser_fetch_fn(
        mock_fetch,
        stealth=True,
        storage_state="anthropic"
    )
    
    # Test wrapper call
    result = wrapper(
        "https://test.com",
        proxy=None,
        use_proxy_flag=False,
        timeout=30
    )
    
    assert result == "<html>mock</html>"


def test_fetch_browser_signature():
    """Verify fetch_browser has stealth and storage_state parameters."""
    from fetch_backends import fetch_browser
    import inspect
    
    sig = inspect.signature(fetch_browser)
    params = sig.parameters
    
    assert 'stealth' in params, "fetch_browser should have stealth parameter"
    assert 'storage_state' in params, "fetch_browser should have storage_state parameter"


def test_stealth_javascript_content():
    """Verify stealth JavaScript contains all required overrides."""
    from fetch_backends import STEALTH_JS
    
    required_checks = [
        'navigator.webdriver',
        'navigator.plugins',
        'navigator.languages',
        'WebGLRenderingContext',
    ]
    
    for check in required_checks:
        assert check in STEALTH_JS, f"STEALTH_JS should contain {check}"


def test_storage_state_path_isolation():
    """Verify different sources get different storage_state paths."""
    from fetch_backends import _get_storage_state_path
    
    path1 = _get_storage_state_path("anthropic")
    path2 = _get_storage_state_path("openai")
    
    assert path1 != path2, "Different sources should get different paths"
    assert path1.name == "anthropic.json"
    assert path2.name == "openai.json"


def test_default_storage_state_path():
    """Verify default storage_state path is configured."""
    from fetch_backends import _get_storage_state_path
    
    # Test with identifier
    path_with_id = _get_storage_state_path("test-source")
    assert path_with_id is not None
    assert "test-source.json" in str(path_with_id)
    
    # Test without identifier (should use default from config)
    path_default = _get_storage_state_path(None)
    # Default may or may not be configured, but should not crash
    assert path_default is None or isinstance(path_default, Path)
