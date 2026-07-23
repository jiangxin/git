"""Tests for check_url.py."""

import sys
from pathlib import Path

import pytest

# Add parent directory to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))
from check_url import get_archives_path, load_archives, check_url, main


class TestLoadArchives:
    """测试 archives.json 加载逻辑。"""

    def test_valid_json(self, make_archives, sample_entries):
        """有效 JSON 正常加载。"""
        tmp_path, archives_path = make_archives(sample_entries)
        data = load_archives(archives_path)
        assert len(data) == 2
        assert data[0]["url"] == "https://example.com/article-1"

    def test_empty_file(self, make_archives, capsys):
        """空文件报错。"""
        tmp_path, archives_path = make_archives("")
        with pytest.raises(SystemExit) as exc_info:
            load_archives(archives_path)
        assert exc_info.value.code == 3
        captured = capsys.readouterr()
        assert "empty" in captured.err.lower()

    def test_malformed_json(self, make_archives, capsys):
        """JSON 格式错误时输出详细错误信息。"""
        tmp_path, archives_path = make_archives('{"bad": json}')
        with pytest.raises(SystemExit) as exc_info:
            load_archives(archives_path)
        assert exc_info.value.code == 3
        captured = capsys.readouterr()
        assert "JSON parse failed" in captured.err
        assert "JSON_REPAIR_NEEDED" in captured.err

    def test_not_a_list(self, make_archives, capsys):
        """根节点不是数组时报错。"""
        tmp_path, archives_path = make_archives({"key": "value"})
        with pytest.raises(SystemExit) as exc_info:
            load_archives(archives_path)
        assert exc_info.value.code == 3
        captured = capsys.readouterr()
        assert "not an array" in captured.err.lower()


class TestCheckUrl:
    """测试 URL 查重逻辑。"""

    def test_url_found(self, sample_entries):
        """已存在的 URL 返回条目。"""
        entry = check_url(sample_entries, "https://example.com/article-1")
        assert entry is not None
        assert entry["cn_title"] == "测试文章一"

    def test_url_not_found(self, sample_entries):
        """不存在的 URL 返回 None。"""
        entry = check_url(sample_entries, "https://example.com/nonexistent")
        assert entry is None

    def test_url_exact_match(self, sample_entries):
        """URL 必须完全匹配。"""
        entry = check_url(sample_entries, "https://example.com/article-1/")
        assert entry is None


class TestMain:
    """测试命令行入口。"""

    @staticmethod
    def _run(argv):
        old_argv = sys.argv
        try:
            sys.argv = argv
            with pytest.raises(SystemExit) as exc_info:
                main()
            return exc_info.value.code
        finally:
            sys.argv = old_argv

    def test_url_found_output(self, make_archives, sample_entries, capsys):
        """FOUND 输出格式正确。"""
        weekly_root, _ = make_archives(sample_entries)
        self._run(
            [
                "check_url.py",
                "--end-date",
                "2026-05-10",
                "--weekly-root",
                str(weekly_root),
                "https://example.com/article-1",
            ]
        )
        captured = capsys.readouterr()
        assert "FOUND" in captured.out
        assert "测试文章一" in captured.out

    def test_url_not_found_output(self, make_archives, sample_entries, capsys):
        """NOT_FOUND 输出格式正确。"""
        weekly_root, _ = make_archives(sample_entries)
        self._run(
            [
                "check_url.py",
                "--end-date",
                "2026-05-10",
                "--weekly-root",
                str(weekly_root),
                "https://example.com/nonexistent",
            ]
        )
        captured = capsys.readouterr()
        assert "NOT_FOUND" in captured.out

    def test_no_arguments(self, capsys):
        """无参数时 argparse 报错退出。"""
        old_argv = sys.argv
        try:
            sys.argv = ["check_url.py"]
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code != 0
        finally:
            sys.argv = old_argv

    def test_batch_mode(self, make_archives, sample_entries, tmp_path, capsys):
        """批量检查多个 URL。"""
        weekly_root, _ = make_archives(sample_entries)

        url_file = tmp_path / "urls.txt"
        url_file.write_text(
            "https://example.com/article-1\n"
            "https://example.com/nonexistent\n"
            "# This is a comment\n"
            "https://example.com/article-2\n"
        )

        self._run(
            [
                "check_url.py",
                "--end-date",
                "2026-05-10",
                "--weekly-root",
                str(weekly_root),
                "--file",
                str(url_file),
            ]
        )
        captured = capsys.readouterr()
        lines = captured.out.strip().splitlines()
        found_lines = [l for l in lines if l.startswith("FOUND:")]
        not_found_lines = [l for l in lines if l.startswith("NOT_FOUND:")]
        assert len(found_lines) == 2
        assert len(not_found_lines) == 1

    def test_missing_week_directory(self, tmp_path, capsys):
        """周目录不存在时报错。"""
        weekly_root = tmp_path / "weekly"
        weekly_root.mkdir()

        with pytest.raises(SystemExit) as exc_info:
            get_archives_path("2026-05-10", root_override=weekly_root)
        assert exc_info.value.code == 2
        captured = capsys.readouterr()
        assert "archives.json" in captured.err

    def test_missing_archives_json(self, tmp_path, capsys):
        """有周目录但无 archives.json 时报错。"""
        weekly_root = tmp_path / "weekly"
        (weekly_root / "2026-05-10" / "ai-trends").mkdir(parents=True)

        with pytest.raises(SystemExit) as exc_info:
            get_archives_path("2026-05-10", root_override=weekly_root)
        assert exc_info.value.code == 2
        assert "archives.json" in capsys.readouterr().err
