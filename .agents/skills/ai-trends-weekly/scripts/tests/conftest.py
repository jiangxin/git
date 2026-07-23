"""Shared fixtures for testing ai-trends-weekly scripts."""

import json
import sys
import pytest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def tmp_weekly_root(tmp_path):
    """创建模拟的 weekly 目录结构，并设置 repo_root 指向其父目录。

    目录布局:
        tmp_path/
          weekly/
    返回 (tmp_path, tmp_path / "weekly")
    """
    weekly = tmp_path / "weekly"
    weekly.mkdir()
    return weekly


@pytest.fixture
def make_archives(tmp_path):
    """创建 weekly/<date>/ai-trends/archives.json 临时结构。

    Returns:
        (weekly_root, archives_path)
    """
    def _make(data=None, end_date="2026-05-10"):
        weekly_root = tmp_path / "weekly"
        week_dir = weekly_root / end_date / "ai-trends"
        week_dir.mkdir(parents=True)

        archives_path = week_dir / "archives.json"
        if data is None:
            data = []
        if isinstance(data, (list, dict)):
            archives_path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            # Raw string for testing malformed JSON
            archives_path.write_text(data)

        return weekly_root, archives_path

    return _make


@pytest.fixture
def sample_entries():
    """返回标准的示例文章列表。"""
    return [
        {
            "original_title": "Test Article One",
            "en_summary": "Summary of article one.",
            "cn_title": "测试文章一",
            "cn_summary": "这是第一篇测试文章的概述。",
            "url": "https://example.com/article-1",
            "publish_date": "2026-05-05",
            "source": "Test Source",
            "collected_at": "2026-05-10T10:00:00",
        },
        {
            "original_title": "Test Article Two",
            "en_summary": "Summary of article two.",
            "cn_title": "测试文章二",
            "cn_summary": "这是第二篇测试文章的概述。",
            "url": "https://example.com/article-2",
            "publish_date": "2026-05-07",
            "source": "Another Source",
            "collected_at": "2026-05-10T11:00:00",
        },
    ]
