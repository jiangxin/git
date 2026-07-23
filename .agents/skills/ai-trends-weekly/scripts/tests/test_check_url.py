"""Tests for check_url.py."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from check_url import get_url_index, check_url, main  # noqa: E402
from site_store import url_index_path  # noqa: E402


@pytest.fixture
def url_env(tmp_path):
    def _make(urls=None, end_date="2026-07-24"):
        weekly_root = tmp_path / "weekly"
        ai_trends = weekly_root / end_date / "ai-trends"
        ai_trends.mkdir(parents=True)
        idx = url_index_path(ai_trends)
        if urls:
            lines = [
                json.dumps({"url": u, "site": "s", "hash": "h", "at": "2026-07-20T00:00:00Z"})
                for u in urls
            ]
            idx.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return weekly_root, ai_trends
    return _make


class TestGetUrlIndex:
    def test_missing_end_date_exits(self):
        with pytest.raises(SystemExit):
            get_url_index("")

    def test_missing_file_exits(self, tmp_path):
        weekly_root = tmp_path / "weekly"
        weekly_root.mkdir()
        with pytest.raises(SystemExit) as exc:
            get_url_index("2026-07-24", root_override=weekly_root)
        assert exc.value.code == 2

    def test_loads_index(self, url_env):
        weekly_root, _ = url_env(urls=["https://e.com/1"])
        idx = get_url_index("2026-07-24", root_override=weekly_root)
        assert "https://e.com/1" in idx


class TestCheckUrl:
    def test_found(self):
        idx = {"https://e.com/1": {"url": "https://e.com/1", "site": "s"}}
        assert check_url(idx, "https://e.com/1") is not None

    def test_not_found(self):
        idx = {"https://e.com/1": {"url": "https://e.com/1", "site": "s"}}
        assert check_url(idx, "https://e.com/2") is None

    def test_exact_match(self):
        idx = {"https://e.com/1": {"url": "https://e.com/1", "site": "s"}}
        assert check_url(idx, "https://e.com/1/") is None


class TestMain:
    @staticmethod
    def _run(argv):
        old_argv = sys.argv
        try:
            sys.argv = argv
            main()
        finally:
            sys.argv = old_argv

    def test_found_output(self, url_env, capsys):
        weekly_root, _ = url_env(urls=["https://e.com/1"])
        self._run([
            "check_url.py", "--end-date", "2026-07-24",
            "--weekly-root", str(weekly_root),
            "https://e.com/1",
        ])
        out = capsys.readouterr().out
        assert "FOUND" in out
        assert "Site:" in out

    def test_not_found_output(self, url_env, capsys):
        weekly_root, _ = url_env(urls=["https://e.com/1"])
        self._run([
            "check_url.py", "--end-date", "2026-07-24",
            "--weekly-root", str(weekly_root),
            "https://e.com/missing",
        ])
        assert "NOT_FOUND" in capsys.readouterr().out

    def test_batch_mode(self, url_env, tmp_path, capsys):
        weekly_root, _ = url_env(urls=["https://e.com/1", "https://e.com/2"])
        url_file = tmp_path / "urls.txt"
        url_file.write_text(
            "https://e.com/1\n"
            "https://e.com/missing\n"
            "# comment\n"
            "https://e.com/2\n"
        )
        self._run([
            "check_url.py", "--end-date", "2026-07-24",
            "--weekly-root", str(weekly_root),
            "--file", str(url_file),
        ])
        out = capsys.readouterr().out
        found = [line for line in out.splitlines() if line.startswith("FOUND:")]
        not_found = [line for line in out.splitlines() if line.startswith("NOT_FOUND:")]
        assert len(found) == 2
        assert len(not_found) == 1
